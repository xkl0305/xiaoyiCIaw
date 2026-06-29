"""
Crusheart Agent OS — 统一后台任务执行器
合并自 background_scheduler + unified_executor

包含：
  - TaskRecord: 单个后台任务记录
  - BackgroundTaskScheduler: 子代理 session 调度 / 心跳 / 超时恢复 / 取消
  - UnifiedBackgroundExecutor: 桥接 TaskScheduler(拆分/依赖/优先级) 与 BackgroundTaskScheduler

职责链:
auto_engines.TaskScheduler (任务拆分、依赖图、优先级、重试、检查点)
  → BackgroundTaskScheduler (子代理 session、心跳、超时恢复、取消)
    → sessions_spawn runtime=subagent (隔离执行不阻塞主对话)
"""

import os, sys, json, uuid, time, threading, hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)

BEIJING_TZ = timezone(timedelta(hours=8))

HEARTBEAT_INTERVAL = 30   # 每30秒续命一次
DEFAULT_TIMEOUT = 900      # 默认15分钟超时
TASK_STATE_FILE = os.path.join(WORKSPACE, ".background_tasks.json")

def _now():
    return datetime.now(BEIJING_TZ).isoformat()

def _now_ts():
    return datetime.now(BEIJING_TZ).timestamp()

# ============================================================
# 1. TaskRecord — 任务记录
# ============================================================

class TaskRecord:
    """单个后台任务记录"""

    def __init__(self, task_id: str, label: str, description: str,
                 task_type: str = "generic"):
        self.task_id = task_id
        self.label = label
        self.description = description
        self.task_type = task_type
        self.status = "pending"  # pending → running → completed / failed / canceled
        self.subagent_session_id = ""
        self.created_at = _now()
        self.heartbeat_at = _now()
        self.completed_at = None
        self.result = {}
        self.error = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "description": self.description[:200],
            "task_type": self.task_type,
            "status": self.status,
            "subagent_session_id": self.subagent_session_id,
            "created_at": self.created_at,
            "heartbeat_at": self.heartbeat_at,
            "completed_at": self.completed_at,
            "result": json.dumps(self.result, ensure_ascii=False)[:500],
            "error": self.error[:200],
        }

    def is_timeout(self, timeout_s: int = DEFAULT_TIMEOUT) -> bool:
        """检查任务是否超时"""
        if self.status in ("completed", "canceled", "failed"):
            return False
        last = datetime.fromisoformat(self.heartbeat_at).timestamp()
        return (_now_ts() - last) > timeout_s

    def __repr__(self):
        return f"[{self.status}] {self.label} ({self.task_id[:8]}...)"

# ============================================================
# 2. BackgroundTaskScheduler — 子代理调度器
# ============================================================

class BackgroundTaskScheduler:
    """
    后台任务调度器。
    通过 sessions_spawn(runtime="subagent") 将任务交给子代理隔离执行。
    主会话聊天不被阻塞。
    """

    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self._heartbeat_thread = None
        self._running = False
        self._load_state()

    # ---------- 任务管理 ----------

    def submit(self, task_spec: str, label: str = "",
               description: str = "",
               task_type: str = "generic",
               timeout_s: int = DEFAULT_TIMEOUT,
               existing_task_id: str = None) -> dict:
        """
        提交一个后台任务。

        task_spec: 子代理要执行的任务描述（自然语言）
        label: 任务标签（简短）
        description: 任务描述
        task_type: 任务类型分类
        timeout_s: 任务超时秒数

        返回: {"task_id": str, "status": str}
        """
        task_id = existing_task_id or (hashlib.md5((label + _now()).encode()).hexdigest()[:16])
        record = TaskRecord(task_id, label, description, task_type)
        record.status = "submitting"

        with self._lock:
            self._tasks[task_id] = record

        try:
            record.status = "pending"
            record.result["task_spec"] = task_spec
            record.result["timeout_s"] = timeout_s
            self._save_state()

            return {
                "task_id": task_id,
                "status": "pending",
                "label": label,
                "note": "任务已注册，需要通过 sessions_spawn 实际提交",
                "spawn_ready": True,
            }

        except Exception as e:
            record.status = "failed"
            record.error = str(e)[:200]
            record.completed_at = _now()
            self._save_state()
            return {"task_id": task_id, "status": "failed", "error": str(e)[:100]}

    def on_spawned(self, task_id: str, subagent_session_id: str):
        """子代理 spawn 成功后回调"""
        with self._lock:
            record = self._tasks.get(task_id)
            if record:
                record.status = "running"
                record.subagent_session_id = subagent_session_id
                record.heartbeat_at = _now()
                self._save_state()

    def on_completed(self, task_id: str, result: dict = None,
                     error: str = ""):
        """子代理完成后的回调"""
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return
            record.completed_at = _now()
            if error:
                record.status = "failed"
                record.error = str(error)[:200]
            else:
                record.status = "completed"
                if result:
                    record.result.update(result)
            self._save_state()
            self._log_to_db(record)

    def cancel(self, task_id: str) -> dict:
        """取消任务"""
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return {"status": "not_found"}
            if record.status in ("completed", "failed", "canceled"):
                return {"status": record.status, "note": "任务已完成或已处于终态"}
            record.status = "canceled"
            record.completed_at = _now()
            record.error = "用户取消"
            self._save_state()

        if record.subagent_session_id:
            try:
                from openclaw import subagents as _sa
                _sa(action="kill", target=record.subagent_session_id)
            except Exception:
                pass

        return {"task_id": task_id, "status": "canceled"}

    def get_status(self, task_id: str = None) -> dict:
        """查询任务状态。不传 task_id 返回全部任务概览"""
        with self._lock:
            if task_id:
                record = self._tasks.get(task_id)
                if not record:
                    return {"status": "not_found"}
                return record.to_dict()

            records = list(self._tasks.values())
            active = [r.to_dict() for r in records if r.status in ("pending", "running", "submitting")]
            recent = [r.to_dict() for r in records[-10:]]

            return {
                "total": len(records),
                "active_count": len(active),
                "active": active,
                "recent": recent,
            }

    def list_timeout_tasks(self, timeout_s: int = DEFAULT_TIMEOUT) -> List[dict]:
        """列出所有超时任务"""
        result = []
        with self._lock:
            for record in self._tasks.values():
                if record.is_timeout(timeout_s):
                    result.append(record.to_dict())
        return result

    # ---------- 心跳 ----------

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            try:
                with self._lock:
                    for record in self._tasks.values():
                        if record.status == "running":
                            record.heartbeat_at = _now()
                    self._save_state_db()
            except Exception:
                pass

    def _save_state_db(self):
        try:
            from core.engines.tools.crusheart_db import get_db
            db = get_db()
            for record in self._tasks.values():
                if record.status in ("running", "pending", "submitting"):
                    row = record.to_dict()
                    db.conn.execute("""
                        INSERT OR REPLACE INTO background_tasks
                        (task_id, label, description, status, subagent_session_id,
                         task_type, created_at, heartbeat_at, completed_at, result, error)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["task_id"], row["label"], row["description"],
                        row["status"], row["subagent_session_id"],
                        record.task_type, row["created_at"], row["heartbeat_at"],
                        row["completed_at"], row["result"], row["error"]
                    ))
                    db.conn.commit()
        except Exception:
            pass

    def _log_to_db(self, record: TaskRecord):
        try:
            from core.engines.tools.crusheart_db import get_db
            db = get_db()
            row = record.to_dict()
            db.conn.execute("""
                INSERT OR REPLACE INTO background_tasks
                (task_id, label, description, status, subagent_session_id,
                 task_type, created_at, heartbeat_at, completed_at, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["task_id"], row["label"], row["description"],
                row["status"], row["subagent_session_id"],
                record.task_type, row["created_at"], row["heartbeat_at"],
                row["completed_at"], row["result"], row["error"]
            ))
            db.conn.commit()
        except Exception:
            pass

    # ---------- 持久化 ----------

    def _save_state(self):
        try:
            data = {}
            for tid, r in self._tasks.items():
                data[tid] = r.to_dict()
            with open(TASK_STATE_FILE, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_state(self):
        if not os.path.exists(TASK_STATE_FILE):
            return
        try:
            with open(TASK_STATE_FILE) as f:
                data = json.load(f)
            with self._lock:
                for tid, d in data.items():
                    r = TaskRecord(tid, d.get("label", ""), d.get("description", ""))
                    r.status = d.get("status", "pending")
                    r.subagent_session_id = d.get("subagent_session_id", "")
                    r.created_at = d.get("created_at", _now())
                    r.heartbeat_at = d.get("heartbeat_at", _now())
                    r.completed_at = d.get("completed_at")
                    try:
                        r.result = json.loads(d.get("result", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        r.result = {}
                    r.error = d.get("error", "")
                    self._tasks[tid] = r
        except Exception:
            pass

    # ---------- 启动/停止 ----------

    def start(self):
        if self._running:
            return {"status": "already_running"}
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True,
            name="crusheart-task-heartbeat"
        )
        self._heartbeat_thread.start()
        return {"status": "started", "heartbeat_interval_s": HEARTBEAT_INTERVAL}

    def stop(self):
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None
        return {"status": "stopped"}

    # ---------- 批量恢复超时任务 ----------

    def recover_timeout_tasks(self, timeout_s: int = DEFAULT_TIMEOUT) -> List[str]:
        recovered = []
        with self._lock:
            for tid, record in self._tasks.items():
                if record.is_timeout(timeout_s) and record.status == "running":
                    record.status = "failed"
                    record.error = f"心跳超时 (>{timeout_s}s)"
                    record.completed_at = _now()
                    self._log_to_db(record)
                    recovered.append(tid)
        if recovered:
            self._save_state()
        return recovered

# ============================================================
# 3. UnifiedBackgroundExecutor — 统一桥接层
# ============================================================

class UnifiedBackgroundExecutor:
    """
    统一后台任务执行器。

    使用方法（在主对话中）:
        1. executor.submit("爬取新闻并总结") → 返回 task_id
        2. executor.spawn_subagent(task_id) → 内部调用 sessions_spawn
        3. executor.get_status(task_id) → 随时查
        4. executor.cancel(task_id) → 随时取消
        5. 子代理完成自动回调 → executor.on_completed(task_id, result)
    """

    def __init__(self):
        self._task_scheduler = None
        self._bg_scheduler = None
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        from core.engines.init.auto_engines import TaskScheduler
        # 同一个文件，直接引用本模块的 get_scheduler
        self._task_scheduler = TaskScheduler()
        self._bg_scheduler = get_scheduler()
        self._initialized = True

    # ---------- 提交任务 ----------

    def submit(self, name: str, description: str = "",
               priority: int = 2, depends_on: List[str] = None,
               break_down: bool = True) -> dict:
        self._ensure_init()

        task = self._task_scheduler.create_task(
            name=name, description=description,
            priority=priority, depends_on=depends_on
        )

        result = {
            "task_id": task.id,
            "subtask_ids": [],
            "status": "pending",
            "spawn_ready": False,
        }

        subtask_names = self._auto_split(description)
        if break_down and subtask_names:
            subtasks = [{"name": n, "description": n, "priority": priority}
                        for n in subtask_names]
            created = self._task_scheduler.split_task(task.id, subtasks)
            result["subtask_ids"] = [t.id for t in created]
            result["note"] = f"已拆分为 {len(created)} 个子任务"
            return result

        bg_result = self._bg_scheduler.submit(
            task_spec=description or name,
            label=name,
            description=description or name,
            task_type="generic",
            timeout_s=self._timeout_for_priority(priority),
            existing_task_id=task.id
        )
        result["task_id"] = task.id
        result["status"] = bg_result["status"]
        result["spawn_ready"] = bg_result.get("spawn_ready", False)
        return result

    # ---------- 子代理执行 ----------

    def spawn_subagent(self, task_id: str, timeout_s: int = 600) -> dict:
        self._ensure_init()
        status = self._bg_scheduler.get_status(task_id)
        if status.get("status") == "not_found":
            return {"status": "not_found", "error": "任务不存在"}

        description = status.get("description", "")
        task_spec = (
            f"你是一个后台子代理，请在独立 session 中执行以下任务：\n\n"
            f"## 任务\n{description}\n\n"
            f"## 要求\n"
            f"1. 不要等待用户确认，直接执行\n"
            f"2. 执行过程中记录关键进度\n"
            f"3. 执行完成后输出完整报告\n"
            f"4. 如果遇到错误请描述问题和已尝试的解决方案\n\n"
            f"请开始执行。"
        )

        return {
            "task_id": task_id,
            "status": "ready_to_spawn",
            "spawn_params": {
                "task": task_spec,
                "runtime": "subagent",
                "label": status.get("label", "后台任务"),
                "runTimeoutSeconds": timeout_s,
                "mode": "run",
            }
        }

    # ---------- 进度回调 ----------

    def on_spawned(self, task_id: str, subagent_session_id: str):
        self._ensure_init()
        self._bg_scheduler.on_spawned(task_id, subagent_session_id)
        self._task_scheduler.start_task(task_id)

    def on_completed(self, task_id: str, result: dict = None, error: str = ""):
        self._ensure_init()
        self._bg_scheduler.on_completed(task_id, result, error)
        if error:
            self._task_scheduler.fail_task(task_id, error)
        else:
            self._task_scheduler.complete_task(task_id, result)

    def on_progress(self, task_id: str, progress_msg: str):
        self._ensure_init()
        self._task_scheduler.add_checkpoint(task_id, progress_msg)

    # ---------- 查询 ----------

    def get_status(self, task_id: str = None) -> dict:
        self._ensure_init()
        return self._bg_scheduler.get_status(task_id)

    def get_task_detail(self, task_id: str) -> dict:
        self._ensure_init()
        bg = self._bg_scheduler.get_status(task_id)
        ts_task = self._task_scheduler.tasks.get(task_id)
        if ts_task is None:
            return bg

        detail = self._task_scheduler.format_task_summary(ts_task)
        detail["checkpoints"] = self._task_scheduler.get_checkpoints(task_id)
        child_ids = ts_task.child_task_ids
        detail["subtasks"] = [
            self._task_scheduler.format_task_summary(
                self._task_scheduler.tasks[cid]
            ) for cid in child_ids if cid in self._task_scheduler.tasks
        ]
        return detail

    def cancel(self, task_id: str) -> dict:
        self._ensure_init()
        self._task_scheduler.cancel_task(task_id)
        return self._bg_scheduler.cancel(task_id)

    def get_queue(self) -> dict:
        self._ensure_init()
        queue = self._task_scheduler.get_queue_status()
        bg = self._bg_scheduler.get_status()
        return {
            "task_queue": queue,
            "background_tasks": {"total": bg["total"], "active": bg["active_count"]},
        }

    # ---------- 辅助 ----------

    def _auto_split(self, description: str) -> List[str]:
        steps = []
        lines = description.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                steps.append(line[2:].strip())
            elif line.startswith(("- 第一步", "- 第二步", "- 第三步", "- 第四步", "- 第五步")):
                steps.append(line[2:].strip())
        return steps[:10] if steps else []

    def _timeout_for_priority(self, priority: int) -> int:
        return {0: 1800, 1: 1200, 2: 900, 3: 600}.get(priority, 900)

# ============================================================
# 4. 单例
# ============================================================

_executor_instance = None
_singleton_lock = threading.Lock()

def get_scheduler() -> BackgroundTaskScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        with _singleton_lock:
            if _scheduler_instance is None:
                _scheduler_instance = BackgroundTaskScheduler()
                _scheduler_instance.start()
    return _scheduler_instance

def get_executor() -> UnifiedBackgroundExecutor:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(UnifiedBackgroundExecutor)

def init_scheduler():
    """BackgroundTaskScheduler 引擎初始化入口"""
    s = get_scheduler()
    recovered = s.recover_timeout_tasks()
    print(f"  📋 后台任务调度器: 已启动（心跳 {HEARTBEAT_INTERVAL}s, 超时 {DEFAULT_TIMEOUT}s）")
    if recovered:
        print(f"    恢复超时任务: {len(recovered)} 个")
    return {"status": "ok", "recovered": recovered}

def init_executor():
    """UnifiedBackgroundExecutor 引擎初始化入口"""
    global _executor_instance
    _executor_instance = UnifiedBackgroundExecutor()
    _executor_instance._ensure_init()
    print("  📋 统一后台执行器: 已就绪（桥接TaskScheduler + BackgroundScheduler）")
    return {"status": "ok"}
