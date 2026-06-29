"""
Crusheart Agent OS — 全局互斥锁 + 任务调度引擎（统一版）
整合：ToolMutex + PriorityScheduler + DeadlockDetector
补充：Watchdog + Crash Recovery + State Persistence + Timeout Rollback
"""

import os, json, time, threading, uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import IntEnum
from dataclasses import dataclass, field
import logging

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
LOCK_DIR = os.path.join(WORKSPACE, ".locks")
CHECKPOINT_DIR = os.path.join(WORKSPACE, ".checkpoints")
os.makedirs(LOCK_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def now_ts() -> float:
    return time.time()


def now_str() -> str:
    return datetime.now(BEIJING_TZ).isoformat()


# ====================================================================
# 优先级定义
# ====================================================================
class Priority(IntEnum):
    EMERGENCY = 0   # P0: 用户主动指令、安全告警 — 可打断低优先级
    HIGH = 1        # P1: 定时推送、重要通知 — 按计划执行
    NORMAL = 2      # P2: 日常检查、数据整理 — 空闲时执行
    BACKGROUND = 3  # P3: 记忆维护、归档清理 — 每日23:00批量


# ====================================================================
# 任务数据结构
# ====================================================================
@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    priority: Priority = Priority.NORMAL
    description: str = ""
    status: str = "pending"  # pending/running/completed/failed/rolled_back
    created_at: float = field(default_factory=now_ts)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    checkpoint: Optional[Dict] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_s: int = 180  # 超时秒数
    dependencies: List[str] = field(default_factory=list)  # 依赖任务ID列表

    def is_expired(self) -> bool:
        if self.status == "running" and self.started_at:
            return (now_ts() - self.started_at) > self.timeout_s
        return False


# ====================================================================
# 全局互斥锁 (ToolMutex)
# ====================================================================
class ToolMutex:
    """工具级互斥锁 + 文件持久化"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        from core.engines.init.engine_factory import SingletonRegistry
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    SingletonRegistry.register(cls, cls._instance)
        return cls._instance

    # 统一后台任务锁路径
    BACKGROUND_LOCK = '/tmp/lock_crayfish_background_task'
    # 后台任务锁超时阈值（2小时，单位：秒）
    BACKGROUND_LOCK_TIMEOUT = 7200
    # 后台任务锁心跳间隔（10分钟，单位：秒）
    BACKGROUND_LOCK_HEARTBEAT = 600
    # 后台任务锁文件描述符（保持打开以持有 flock）
    # 使用 dict 以支持多线程场景
    _background_lock_fds: Dict[str, int] = {}

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._locks: Dict[str, str] = {}  # tool_name -> task_id
        self._lock_file = os.path.join(LOCK_DIR, "tool_mutex.json")
        self._load()

    @classmethod
    def acquire_background_lock(cls) -> bool:
        """获取后台任务全局锁（文件锁）
        同一时刻只允许一个后台定时任务执行
        通过保持 fd 打开来持有 flock，不会释放
        使用线程独立 fd 存储以支持多线程并发测试
        """
        import threading
        tid = threading.get_ident()
        try:
            fd = os.open(cls.BACKGROUND_LOCK, os.O_CREAT | os.O_WRONLY, 0o644)
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # 写入心跳
            os.lseek(fd, 0, os.SEEK_SET)
            os.truncate(fd, 0)
            heart = str(time.time())  # 写当前时间戳，非6小时后的
            os.write(fd, heart.encode())
            cls._background_lock_fds[tid] = fd
            return True
        except (BlockingIOError, PermissionError, FileNotFoundError, OSError):
            # 清理本线程可能的残留
            if tid in cls._background_lock_fds:
                try:
                    os.close(cls._background_lock_fds[tid])
                except OSError:
                    pass
                del cls._background_lock_fds[tid]
            return False

    @classmethod
    def release_background_lock(cls):
        """释放后台任务全局锁"""
        import threading
        tid = threading.get_ident()
        try:
            fd = cls._background_lock_fds.pop(tid, None)
            if fd is not None:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            if os.path.exists(cls.BACKGROUND_LOCK):
                os.remove(cls.BACKGROUND_LOCK)
        except (FileNotFoundError, PermissionError, OSError):
            cls._background_lock_fds.pop(tid, None)

    @classmethod
    def is_background_lock_alive(cls) -> bool:
        """检查后台任务锁是否存活（心跳检测）"""
        try:
            if not os.path.exists(cls.BACKGROUND_LOCK):
                return False
            # 先尝试通过flock判断锁是否存活（比时间戳更可靠）
            try:
                test_fd = os.open(cls.BACKGROUND_LOCK, os.O_RDONLY)
                import fcntl
                try:
                    fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # 能加锁成功 → 无人持有锁 → 可以获取
                    fcntl.flock(test_fd, fcntl.LOCK_UN)
                    os.close(test_fd)
                    return False
                except BlockingIOError:
                    # 锁被持有 → 检查心跳时间戳
                    os.lseek(test_fd, 0, os.SEEK_SET)
                    content = os.read(test_fd, 64).decode().strip()
                    os.close(test_fd)
                    if not content:
                        return False
                    heartbeat_time = float(content)
                    if time.time() - heartbeat_time > cls.BACKGROUND_LOCK_TIMEOUT:
                        # 超过2小时无心跳，视为死锁
                        try:
                            os.remove(cls.BACKGROUND_LOCK)
                        except Exception:
                            pass
                        return False
                    return True
            except (ValueError, FileNotFoundError, PermissionError):
                return False
        except (ValueError, FileNotFoundError, PermissionError):
            return False

    @classmethod
    def update_background_lock_heartbeat(cls):
        """更新后台任务锁心跳时间（通过保持的 fd 写入，不释放锁）"""
        import threading
        tid = threading.get_ident()
        try:
            fd = cls._background_lock_fds.get(tid)
            if fd is not None:
                os.lseek(fd, 0, os.SEEK_SET)
                os.truncate(fd, 0)
                os.write(fd, str(time.time()).encode())
                return True
            # 兜底：尝试通过文件路径打开（可能不是本进程持有的锁）
            if os.path.exists(cls.BACKGROUND_LOCK):
                with open(cls.BACKGROUND_LOCK, 'w') as f:
                    f.write(str(time.time()))
                return True
            return False
        except (FileNotFoundError, PermissionError, OSError):
            return False

    def _load(self):
        if os.path.exists(self._lock_file):
            try:
                with open(self._lock_file) as f:
                    self._locks = json.load(f)
            except Exception:
                logging.exception("[mutex_engine.py] suppressed")
                self._locks = {}

    def _persist(self):
        with open(self._lock_file, "w") as f:
            json.dump(self._locks, f, indent=2)

    def acquire(self, tool_name: str, task_id: str, timeout_ms: int = 30000) -> bool:
        """获取锁，返回是否成功"""
        deadline = now_ts() + timeout_ms / 1000
        while now_ts() < deadline:
            if tool_name not in self._locks:
                self._locks[tool_name] = task_id
                self._persist()
                return True
            # 检查锁是否已过期（持有者超时）
            owner = self._locks.get(tool_name)
            if owner and not self._is_task_alive(owner):
                del self._locks[tool_name]
                self._persist()
                continue
            time.sleep(0.5)
        return False

    def release(self, tool_name: str) -> bool:
        if tool_name in self._locks:
            del self._locks[tool_name]
            self._persist()
            return True
        return False

    def is_locked(self, tool_name: str) -> bool:
        return tool_name in self._locks

    def _is_task_alive(self, task_id: str) -> bool:
        """检查任务是否还在运行（通过checkpoint心跳）"""
        cp_file = os.path.join(CHECKPOINT_DIR, f"{task_id}.json")
        if os.path.exists(cp_file):
            try:
                with open(cp_file) as f:
                    cp = json.load(f)
                last_heartbeat = cp.get("heartbeat", 0)
                return (now_ts() - last_heartbeat) < 7200  # 2小时无心跳视为死亡
            except Exception:
                logging.exception("[mutex_engine.py] suppressed")
                pass
        return False


# ====================================================================
# 任务调度器 (TaskScheduler)
# ====================================================================
class TaskScheduler:
    """任务调度器：拆分/依赖/优先级/资源管理/失败重试/回滚"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._queue_file = os.path.join(CHECKPOINT_DIR, "task_queue.json")
        self._watchdog_interval = 30  # 每30秒检查一次超时
        self._running = False
        self._load()

    def _load(self):
        if os.path.exists(self._queue_file):
            try:
                with open(self._queue_file) as f:
                    data = json.load(f)
                for t in data:
                    task = Task(**{k: v for k, v in t.items()
                                   if k in Task.__dataclass_fields__})
                    self.tasks[task.id] = task
            except Exception:
                logging.exception("[mutex_engine.py] suppressed")
                self.tasks = {}

    def _persist(self):
        data = []
        for t in self.tasks.values():
            d = {k: v for k, v in t.__dict__.items()
                 if k in Task.__dataclass_fields__}
            data.append(d)
        with open(self._queue_file, "w") as f:
            json.dump(data, f, indent=2)

    def submit(self, task: Task) -> str:
        """提交任务"""
        self.tasks[task.id] = task
        self._persist()
        return task.id

    def submit_batch(self, tasks: List[Task]) -> List[str]:
        """批量提交任务"""
        ids = []
        for t in tasks:
            self.tasks[t.id] = t
            ids.append(t.id)
        self._persist()
        return ids

    def get_ready_tasks(self, priority_max: Priority = Priority.BACKGROUND) -> List[Task]:
        """获取所有可执行任务（依赖已满足）"""
        ready = []
        for t in self.tasks.values():
            if t.status != "pending":
                continue
            if t.priority > priority_max:
                continue
            # 检查依赖
            deps_met = all(
                self.tasks.get(d, Task(id=d)).status == "completed"
                for d in t.dependencies
            )
            if deps_met:
                ready.append(t)
        # 按优先级排序
        ready.sort(key=lambda x: (x.priority.value, x.created_at))
        return ready

    def start_task(self, task_id: str) -> bool:
        """开始执行任务"""
        t = self.tasks.get(task_id)
        if not t:
            return False
        t.status = "running"
        t.started_at = now_ts()
        # 创建心跳 checkpoint
        self._update_heartbeat(task_id)
        self._persist()
        return True

    def complete_task(self, task_id: str, result: Any = None):
        """完成任务"""
        t = self.tasks.get(task_id)
        if not t:
            return
        t.status = "completed"
        t.completed_at = now_ts()
        t.result = result
        self._persist()

    def fail_task(self, task_id: str, error: str):
        """任务失败（含重试逻辑）"""
        t = self.tasks.get(task_id)
        if not t:
            return
        t.retry_count += 1
        if t.retry_count <= t.max_retries:
            t.status = "pending"
            t.started_at = None
            t.error = error
        else:
            t.status = "failed"
            t.error = error
            t.completed_at = now_ts()
        self._persist()

    def rollback_task(self, task_id: str):
        """回滚任务（通过checkpoint恢复）"""
        t = self.tasks.get(task_id)
        if not t:
            return
        cp = self.load_checkpoint(task_id)
        t.status = "rolled_back"
        t.result = cp
        t.completed_at = now_ts()
        self._persist()

    def _update_heartbeat(self, task_id: str):
        """更新任务心跳"""
        cp = self.load_checkpoint(task_id) or {}
        cp["heartbeat"] = now_ts()
        if "status" not in cp:
            cp["status"] = "running"
        self.save_checkpoint(task_id, cp)

    def save_checkpoint(self, task_id: str, state: Dict):
        """保存检查点"""
        cp_file = os.path.join(CHECKPOINT_DIR, f"{task_id}.json")
        with open(cp_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_checkpoint(self, task_id: str) -> Optional[Dict]:
        """加载检查点"""
        cp_file = os.path.join(CHECKPOINT_DIR, f"{task_id}.json")
        if os.path.exists(cp_file):
            try:
                with open(cp_file) as f:
                    return json.load(f)
            except Exception:
                logging.exception("[mutex_engine.py] suppressed")
                return None
        return None

    # ====================================================================
    # Watchdog — 超时检测与自动恢复
    # ====================================================================
    def watchdog_check(self) -> List[str]:
        """检查所有运行中的任务是否超时，返回超时任务ID列表"""
        expired = []
        for t in self.tasks.values():
            if t.status == "running" and t.is_expired():
                expired.append(t.id)
                self.fail_task(t.id, f"Timeout after {t.timeout_s}s")
                # 自动回滚
                if self.load_checkpoint(t.id):
                    self.rollback_task(t.id)
        if expired:
            self._persist()
        return expired

    def start_watchdog(self, interval_s: int = 30):
        """启动看门狗（后台线程）"""
        if self._running:
            return
        self._running = True

        def _run():
            while self._running:
                try:
                    self.watchdog_check()
                except Exception:
                    logging.exception("[mutex_engine.py] suppressed")
                    pass
                time.sleep(interval_s)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def stop_watchdog(self):
        self._running = False

    # ====================================================================
    # Crash Recovery — 启动时恢复未完成任务
    # ====================================================================
    def recover_crashed_tasks(self) -> List[Task]:
        """系统启动时恢复上次崩溃时运行中的任务"""
        recovered = []
        for t in self.tasks.values():
            if t.status == "running":
                # 检查心跳
                cp = self.load_checkpoint(t.id)
                if cp:
                    last_heartbeat = cp.get("heartbeat", 0)
                    if (now_ts() - last_heartbeat) > 7200:
                        # 真的崩溃了
                        t.status = "failed"
                        t.error = "Crashed - recovered on restart"
                        t.completed_at = now_ts()
                        recovered.append(t)
                else:
                    # 无 checkpoint，标记失败
                    t.status = "failed"
                    t.error = "Crashed (no checkpoint)"
                    t.completed_at = now_ts()
                    recovered.append(t)
            elif t.status == "pending" and t.started_at:
                # 奇怪的中间状态，恢复为 pending
                t.started_at = None
                recovered.append(t)
        if recovered:
            self._persist()
        return recovered

    def clear_all(self):
        """清空所有任务和checkpoint"""
        task_ids = list(self.tasks.keys())
        self.tasks.clear()
        self._persist()
        for task_id in task_ids:
            for task_id in list(self.tasks.keys()):
                cp_path = os.path.join(CHECKPOINT_DIR, f"{task_id}.json")
                if os.path.exists(cp_path):
                    try:
                        os.remove(cp_path)
                    except Exception:
                        pass

    @property
    def stats(self) -> Dict:
        """任务统计"""
        stats = {"total": 0, "pending": 0, "running": 0,
                 "completed": 0, "failed": 0, "rolled_back": 0}
        for t in self.tasks.values():
            stats["total"] += 1
            stats[t.status] = stats.get(t.status, 0) + 1
        stats["ready"] = len(self.get_ready_tasks())
        return stats


# ====================================================================
# 死锁检测器
# ====================================================================
class DeadlockDetector:
    """循环依赖检测 + 死锁兜底"""

    def __init__(self, scheduler: TaskScheduler = None):
        self.scheduler = scheduler

    def detect_cycle(self) -> List[List[str]]:
        """检测任务依赖中是否存在循环"""
        tasks = self.scheduler.tasks if self.scheduler else {}
        # 构建有向图
        graph = {}
        for tid, t in tasks.items():
            graph[tid] = [d for d in t.dependencies if d in tasks]

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    cycle = dfs(neighbor, path + [neighbor])
                    if cycle:
                        cycles.append(cycle)
                elif neighbor in rec_stack:
                    # 找到环
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            rec_stack.discard(node)
            return None

        for tid in graph:
            if tid not in visited:
                dfs(tid, [tid])

        return cycles

    def resolve_deadlocks(self):
        """检测并解除死锁"""
        cycles = self.detect_cycle()
        for cycle in cycles:
            if len(cycle) >= 2:
                # 打破环：将环中优先级最低的任务设为失败（value越大=优先级越低）
                worst_task = max(
                    cycle,
                    key=lambda tid: (
                        self.scheduler.tasks[tid].priority.value
                        if tid in self.scheduler.tasks
                        else -1
                    )
                )
                if worst_task in self.scheduler.tasks:
                    self.scheduler.fail_task(worst_task,
                                             f"Deadlock resolved: removed from cycle")
