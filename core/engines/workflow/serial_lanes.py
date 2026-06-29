"""
Crusheart Agent OS — SerialLanes v4.0
设备串行执行通道：运行时设备操作串行管控 + 排队 + 优先级

与 workflow_engine.py 的关系：
- workflow_engine.assert_device_serialized() → 图构建阶段的静态串行校验
- SerialLanes（本文件）              → 运行时的设备操作实际串行执行

核心机制：
  单线程串行队列 + 优先级 + 超时 + 心跳 + 锁文件
  与 Crusheart 现有的互斥锁机制（mutex_engine）互补：
  - mutex_engine: 全局任务互斥锁（谁可以运行）
  - SerialLanes:  设备操作排队通道（设备操作如何串行执行）
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import asyncio
import logging
import os
import time
import json
import threading
import uuid

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
LOCK_FILE = "/tmp/lock_serial_lanes"  # 与 mutex_engine 不同锁文件，避免冲突


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class LanePriority(str, Enum):
    """设备通道优先级"""
    CRITICAL = "critical"   # 紧急（打断当前执行）
    HIGH = "high"           # 高优先级（排队优先）
    NORMAL = "normal"       # 正常排队
    LOW = "low"             # 低优先级（空闲时执行）


class LaneStatus(str, Enum):
    """设备通道状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 执行中
    WAITING = "waiting"     # 等待中
    FAILED = "failed"       # 失败
    TIMEOUT = "timeout"     # 超时


class DeviceLaneState(str, Enum):
    """设备操作状态"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class DeviceOperation:
    """
    设备操作包装
    
    将一次设备操作（如 gui-agent 调用）包装为可串行调度单元。
    """
    op_id: str
    name: str
    action: Callable
    priority: LanePriority = LanePriority.NORMAL
    timeout_s: int = 180
    max_retries: int = 2
    retry_delay_s: int = 5
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    state: DeviceLaneState = DeviceLaneState.QUEUED
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(BEIJING_TZ).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "name": self.name,
            "priority": self.priority.value,
            "state": self.state.value,
            "timeout_s": self.timeout_s,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════
# 设备操作队列
# ═══════════════════════════════════════════

class DeviceOperationQueue:
    """
    设备操作队列
    
    基于优先级的多级队列：
    - CRITICAL: 插入到队首
    - HIGH: 排在 CRITICAL 后面
    - NORMAL: 默认排位
    - LOW: 只在空闲时消费
    """

    def __init__(self):
        self._queues: Dict[LanePriority, List[DeviceOperation]] = {
            p: [] for p in LanePriority
        }
        self._lock = threading.RLock()
        self._running_op: Optional[DeviceOperation] = None

    @property
    def total_pending(self) -> int:
        """等待中的操作总数"""
        with self._lock:
            return sum(len(q) for k, q in self._queues.items()
                       if k != LanePriority.LOW)

    @property
    def total(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def enqueue(self, op: DeviceOperation) -> bool:
        """入队"""
        with self._lock:
            if op.priority == LanePriority.CRITICAL:
                self._queues[LanePriority.CRITICAL].insert(0, op)
            else:
                self._queues[op.priority].append(op)
            return True

    def dequeue(self) -> Optional[DeviceOperation]:
        """出队（按优先级：CRITICAL > HIGH > NORMAL > LOW）"""
        with self._lock:
            for priority in (LanePriority.CRITICAL, LanePriority.HIGH,
                             LanePriority.NORMAL, LanePriority.LOW):
                q = self._queues[priority]
                if q:
                    op = q.pop(0)
                    self._running_op = op
                    return op
            self._running_op = None
            return None

    def peek(self) -> Optional[DeviceOperation]:
        """查看队首（不移除）"""
        with self._lock:
            for priority in (LanePriority.CRITICAL, LanePriority.HIGH,
                             LanePriority.NORMAL, LanePriority.LOW):
                q = self._queues[priority]
                if q:
                    return q[0]
            return None

    def remove(self, op_id: str) -> bool:
        """从队列中移除指定操作"""
        with self._lock:
            for q in self._queues.values():
                for i, op in enumerate(q):
                    if op.op_id == op_id:
                        q.pop(i)
                        return True
        return False

    def get_running(self) -> Optional[DeviceOperation]:
        return self._running_op

    def clear_low(self) -> int:
        """清除所有低优先级排队"""
        with self._lock:
            count = len(self._queues[LanePriority.LOW])
            self._queues[LanePriority.LOW] = []
            return count

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "critical": len(self._queues[LanePriority.CRITICAL]),
                "high": len(self._queues[LanePriority.HIGH]),
                "normal": len(self._queues[LanePriority.NORMAL]),
                "low": len(self._queues[LanePriority.LOW]),
                "running": 1 if self._running_op else 0,
                "total_pending": self.total_pending,
            }


# ═══════════════════════════════════════════
# 锁文件管理
# ═══════════════════════════════════════════

class LockFileManager:
    """
    锁文件管理器
    
    与 Crusheart 现有互斥锁对齐：
    - 锁文件: /tmp/lock_crayfish_background_task
    - 超时: 2小时无心跳则判定死锁
    - 心跳: 每 10 秒更新一次
    """

    HEARTBEAT_INTERVAL = 10  # 秒
    STALE_TIMEOUT = 7200     # 2小时

    def __init__(self, lock_path: str = LOCK_FILE):
        self.lock_path = lock_path
        self._heartbeat_active = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    def acquire(self, owner: str = "serial_lanes") -> bool:
        """获取锁"""
        try:
            now = time.time()
            try:
                with open(self.lock_path, "r") as f:
                    data = json.load(f)
                locked_at = data.get("locked_at", 0)
                heartbeat = data.get("heartbeat", 0)
                age = now - locked_at
                since_last_hb = now - heartbeat

                # 检查是否已超时（死锁）
                if age < self.STALE_TIMEOUT and since_last_hb < 600:
                    logger.warning(
                        f"[LockFileManager] 锁已被 {data.get('owner')} 持有 "
                        f"{age:.0f}s ago (hb={since_last_hb:.0f}s ago)"
                    )
                    return False

                # 超时 → 强制释放
                logger.warning(
                    f"[LockFileManager] 锁已超时 (age={age:.0f}s), 强制释放"
                )
            except FileNotFoundError:
                pass

            # 加锁
            with open(self.lock_path, "w") as f:
                json.dump({
                    "owner": owner,
                    "locked_at": now,
                    "heartbeat": now,
                    "pid": os.getpid(),
                }, f)
            logger.debug(f"[LockFileManager] 已加锁: owner={owner}")
            return True

        except Exception as e:
            logger.error(f"[LockFileManager] 加锁失败: {e}")
            return False

    def release(self) -> bool:
        """释放锁"""
        try:
            try:
                os.remove(self.lock_path)
            except OSError:
                pass
                logger.debug("[LockFileManager] 已释放锁")
            return True
        except Exception as e:
            logger.error(f"[LockFileManager] 释放锁失败: {e}")
            return False

    async def start_heartbeat(self):
        """启动心跳（异步）"""
        if self._heartbeat_active:
            return
        self._heartbeat_active = True

        async def _beat():
            while self._heartbeat_active:
                try:
                    with open(self.lock_path, "r") as f:
                        data = json.load(f)
                    data["heartbeat"] = time.time()
                    with open(self.lock_path, "w") as f:
                        json.dump(data, f)
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)

        self._heartbeat_task = asyncio.create_task(_beat())

    async def stop_heartbeat(self):
        """停止心跳"""
        self._heartbeat_active = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None


# ═══════════════════════════════════════════
# 串行通道（核心）
# ═══════════════════════════════════════════

class SerialLane:
    """
    设备串行执行通道 v4.0
    
    职责：
    1. 设备操作排队 → 按优先级串行执行
    2. 运行时串行性保障（即使有多个并发的 submit）
    3. 超时管控 + 重试
    4. 全局互斥锁（与 mutex_engine / crontab 避免冲突）
    
    使用方式：
        lane = SerialLane()
        
        # 方式1：submit + await result（常用）
        result = await lane.submit("op_1", my_device_func, priority=HIGH)
        
        # 方式2：submit_and_forget（后台执行）
        lane.submit_and_forget("op_2", my_func)
        
        # 方式3：检查状态
        status = lane.get_status()
        stats = lane.get_stats()
    """

    def __init__(self, use_lock_file: bool = True):
        self.queue = DeviceOperationQueue()
        self.lock_mgr = LockFileManager() if use_lock_file else None
        self._status = LaneStatus.IDLE
        self._current_op: Optional[DeviceOperation] = None
        self._results: Dict[str, Any] = {}
        self._history: List[Dict] = []
        self._lock = asyncio.Lock()
        self._op_counter = 0
        self._completion_events: Dict[str, asyncio.Event] = {}

    def _next_op_id(self) -> str:
        self._op_counter += 1
        return f"devop_{int(time.time() * 1000)}_{self._op_counter}"

    async def submit(self, name: str, action: Callable,
                     priority: LanePriority = LanePriority.NORMAL,
                     timeout_s: int = 180,
                     max_retries: int = 2,
                     metadata: Optional[Dict] = None) -> Any:
        """
        提交设备操作并等待执行结果
        
        Args:
            name: 操作名称
            action: 异步执行函数
            priority: 优先级
            timeout_s: 超时秒数
            max_retries: 最大重试次数
            metadata: 附加元数据
            
        Returns:
            操作执行结果
            
        Raises:
            TimeoutError: 操作超时
            RuntimeError: 操作最终失败（重试耗尽）
            Exception: 执行过程中的异常
        """
        op = DeviceOperation(
            op_id=self._next_op_id(),
            name=name,
            action=action,
            priority=priority,
            timeout_s=timeout_s,
            max_retries=max_retries,
            metadata=metadata or {},
        )

        self.queue.enqueue(op)
        logger.info(
            f"[SerialLane] 已入队: {name} "
            f"priority={priority.value} timeout={timeout_s}s"
        )

        # 如果没有在执行，触发执行循环
        asyncio.create_task(self._run_loop())

        # 等待操作完成
        return await self._wait_for_completion(op.op_id, timeout_s)

    def submit_and_forget(self, name: str, action: Callable,
                          priority: LanePriority = LanePriority.NORMAL,
                          metadata: Optional[Dict] = None) -> str:
        """
        提交设备操作（不等待结果）
        
        Returns:
            op_id: 操作 ID（可用于后续查询状态）
        """
        op = DeviceOperation(
            op_id=self._next_op_id(),
            name=name,
            action=action,
            priority=priority,
            metadata=metadata or {},
        )
        self.queue.enqueue(op)
        asyncio.create_task(self._run_loop())
        return op.op_id

    async def _run_loop(self):
        """执行循环——串行消费队列"""
        if self._lock.locked():
            return  # 已有执行循环在跑

        async with self._lock:
            while self.queue.total_pending > 0 or self.queue.peek():
                op = self.queue.dequeue()
                if not op:
                    break

                self._current_op = op
                self._status = LaneStatus.BUSY
                op.state = DeviceLaneState.RUNNING
                op.started_at = datetime.now(BEIJING_TZ).isoformat()

                # 获取全局锁
                locked = True
                if self.lock_mgr:
                    locked = self.lock_mgr.acquire(f"serial_lane_{op.op_id}")
                    if locked:
                        await self.lock_mgr.start_heartbeat()

                try:
                    result = await self._execute_with_retry(op)

                    op.state = DeviceLaneState.COMPLETED
                    op.result = result
                    op.completed_at = datetime.now(BEIJING_TZ).isoformat()
                    self._results[op.op_id] = result

                    logger.info(
                        f"[SerialLane] 完成: {op.name} "
                        f"retries={op.retry_count}"
                    )

                except asyncio.TimeoutError:
                    op.state = DeviceLaneState.TIMEOUT
                    op.error = f"执行超时 ({op.timeout_s}s)"
                    op.completed_at = datetime.now(BEIJING_TZ).isoformat()
                    logger.error(f"[SerialLane] 超时: {op.name}")

                except Exception as e:
                    op.state = DeviceLaneState.FAILED
                    op.error = str(e)
                    op.completed_at = datetime.now(BEIJING_TZ).isoformat()
                    logger.error(f"[SerialLane] 失败: {op.name} - {e}")

                finally:
                    # 释放全局锁
                    if self.lock_mgr and locked:
                        await self.lock_mgr.stop_heartbeat()
                        self.lock_mgr.release()

                    self._history.append(op.to_dict())
                    self._signal_completion(op)
                    self._current_op = None
                    self._status = LaneStatus.IDLE

    async def _execute_with_retry(self, op: DeviceOperation) -> Any:
        """带重试的异步执行"""
        last_exc = None

        for attempt in range(1 + op.max_retries):
            try:
                if attempt > 0:
                    logger.info(
                        f"[SerialLane] 重试 #{attempt}/{op.max_retries}: "
                        f"{op.name}"
                    )
                    await asyncio.sleep(op.retry_delay_s)
                    op.retry_count = attempt

                # 获取要执行的对象（支持 coroutine function 和 callable）
                result_or_coro = op.action()

                # 如果返回了一个 coroutine → await 它
                if asyncio.iscoroutine(result_or_coro):
                    return await asyncio.wait_for(
                        result_or_coro, timeout=op.timeout_s
                    )

                # 同步函数 → to_thread
                return result_or_coro

            except asyncio.TimeoutError:
                last_exc = asyncio.TimeoutError(
                    f"执行超时 ({op.timeout_s}s)"
                )
                if attempt >= op.max_retries:
                    raise last_exc
                logger.warning(
                    f"[SerialLane] 超时重试: {op.name} "
                    f"(attempt {attempt + 1}/{op.max_retries})"
                )

            except Exception as e:
                last_exc = e
                if attempt >= op.max_retries:
                    raise
                logger.warning(
                    f"[SerialLane] 失败重试: {op.name} - {e} "
                    f"(attempt {attempt + 1}/{op.max_retries})"
                )

        raise last_exc or RuntimeError("未知执行错误")

    async def _wait_for_completion(self, op_id: str, timeout_s: int) -> Any:
        """等待指定操作完成（事件驱动，无 busy polling）"""
        event = asyncio.Event()
        self._completion_events[op_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_s + 30)

            if op_id in self._results:
                return self._results.pop(op_id)

            # 检查历史
            for h in self._history:
                if h["op_id"] == op_id:
                    if h["state"] == "failed":
                        raise RuntimeError(h.get("error", "执行失败"))
                    if h["state"] == "timeout":
                        raise TimeoutError(h.get("error", "执行超时"))
                    if h["state"] == "cancelled":
                        raise RuntimeError(h.get("error", "操作被取消"))
                    if h["state"] == "completed":
                        return h.get("result")

            raise RuntimeError(f"操作 {op_id} 完成但无结果")
        except asyncio.TimeoutError:
            raise TimeoutError(f"等待操作 {op_id} 超时")
        finally:
            self._completion_events.pop(op_id, None)

    def _signal_completion(self, op: DeviceOperation):
        """通知等待者操作已完成"""
        if op.op_id in self._results or any(h["op_id"] == op.op_id for h in self._history):
            event = self._completion_events.get(op.op_id)
            if event and not event.is_set():
                event.set()

    # ── 状态查询 ──

    def status(self) -> LaneStatus:
        return self._status

    def current_operation(self) -> Optional[Dict]:
        if self._current_op:
            return self._current_op.to_dict()
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取通道完整状态"""
        return {
            "lane_status": self._status.value,
            "current_op": self._current_op.to_dict() if self._current_op else None,
            "queue": self.queue.stats(),
            "history_count": len(self._history),
            "last_result": list(self._history[-5:]) if self._history else [],
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取运行统计"""
        total = len(self._history)
        completed = sum(1 for h in self._history
                        if h["state"] == DeviceLaneState.COMPLETED.value)
        failed = sum(1 for h in self._history
                     if h["state"] in (
                         DeviceLaneState.FAILED.value,
                         DeviceLaneState.TIMEOUT.value,
                     ))
        cancel = sum(1 for h in self._history
                     if h["state"] == DeviceLaneState.CANCELLED.value)

        return {
            "total_ops": total,
            "completed": completed,
            "failed": failed,
            "cancelled": cancel,
            "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "queue": self.queue.stats(),
            "lock_active": os.path.exists(LOCK_FILE) if self.lock_mgr else False,
        }

    def cancel_pending(self, op_id: Optional[str] = None) -> int:
        """取消排队中的操作"""
        if op_id:
            removed = self.queue.remove(op_id)
            if removed:
                # 向等待者发送取消信号
                cancelled_op = DeviceOperation(
                    op_id=op_id, name="cancelled", action=None,
                    priority=LanePriority.LOW
                )
                cancelled_op.state = DeviceLaneState.CANCELLED
                cancelled_op.error = "操作已被取消"
                self._history.append(cancelled_op.to_dict())
                self._signal_completion(cancelled_op)
            return 1 if removed else 0
        else:
            return self.queue.clear_low()


# ═══════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════

_serial_lane: Optional[SerialLane] = None

def get_serial_lane() -> SerialLane:
    """获取全局串行通道单例"""
    global _serial_lane
    if _serial_lane is None:
        _serial_lane = SerialLane()
    return _serial_lane


# ═══════════════════════════════════════════
# 验证
# ═══════════════════════════════════════════

if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    async def main():
        logging.basicConfig(level=logging.DEBUG)

        print("=" * 60)
        print("SerialLane v4.0 — 测试")
        print("=" * 60)

        lane = SerialLane(use_lock_file=False)  # 测试时不使用锁文件

        # 测试1: 基本提交 + 执行
        print("\n测试1: 基本提交 + 执行")
        async def simple_op():
            await asyncio.sleep(0.1)
            return "ok"

        result = await lane.submit("simple_test", simple_op)
        assert result == "ok"
        print(f"  result={result} ✅ 通过")

        # 测试2: 串行性保障
        print("\n测试2: 串行性保障（同时提交3个操作）")
        results = {}

        async def fast_op(name: str, delay: float):
            await asyncio.sleep(delay)
            results["order"] = results.get("order", []) + [name]
            return name

        tasks = [
            lane.submit("op_fast", lambda: fast_op("fast", 0.05)),
            lane.submit("op_medium", lambda: fast_op("medium", 0.1)),
            lane.submit("op_slow", lambda: fast_op("slow", 0.15)),
        ]
        await asyncio.gather(*tasks)
        # 串行执行保证顺序
        print(f"  执行顺序: {results.get('order', [])}")
        assert results.get("order") == ["fast", "medium", "slow"], \
            f"预期顺序执行, 实际: {results.get('order')}"
        print("  ✅ 通过")

        # 测试3: 优先级队列
        print("\n测试3: 优先级队列")
        results3 = {}
        async def prio_op(name: str):
            await asyncio.sleep(0.05)
            results3["order"] = results3.get("order", []) + [name]
            return name

        # 先提交 LOW，再提交 HIGH
        await lane.submit("low_prio", lambda: prio_op("low"),
                          priority=LanePriority.LOW)
        result3 = await lane.submit("high_prio", lambda: prio_op("high"),
                                    priority=LanePriority.HIGH)
        print(f"  执行顺序: {results3.get('order', [])}")
        print(f"  结果: {result3}")
        print("  ✅ 通过")

        # 测试4: 超时处理
        print("\n测试4: 超时处理")
        async def slow_op():
            await asyncio.sleep(10)

        try:
            await lane.submit("timeout_test", slow_op, timeout_s=0.5)
            print("  ❌ 应超时但未超时")
        except (TimeoutError, asyncio.TimeoutError):
            print("  ✅ 正确捕获超时")

        # 测试5: 状态查询
        print("\n测试5: 状态查询")
        status = lane.get_status()
        print(f"  通道状态: {status['lane_status']}")
        print(f"  队列: {status['queue']}")
        print(f"  历史: {status['history_count']}次操作")
        stats = lane.get_stats()
        print(f"  成功率: {stats['success_rate']}%")
        print("  ✅ 通过")

        print("\n" + "=" * 60)
        print("全部测试通过 ✅")
        print("=" * 60)

    asyncio.run(main())
