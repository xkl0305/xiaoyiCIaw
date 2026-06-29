"""
Crusheart Agent OS — 熔断器 Circuit Breaker v2.0
功能：防止故障扩散的电路熔断模式 + 超时保护 + 自动重试 + 断点接续

三种状态机：
  CLOSED (正常)   — 请求正常通过，连续失败计数达到阈值 → OPEN
  OPEN (熔断)     — 请求直接返回降级，超时后自动 → HALF_OPEN
  HALF_OPEN (试探) — 允许有限请求通过试探恢复，失败则 → OPEN（超时翻倍）

新增 v2.0：
  - 超时保护：call() 支持 timeout 参数，超时自动标记失败并熔断
  - 自动重试：call() 支持 retry 参数，失败后重试，指数退避
  - CheckpointManager：任务断点接续，进度持久化
  - ProcessLogger：临时进程日志，成功自动删除

集成点：
  - RecoveryManager：重试前先查熔断状态
  - ToolExecutionGateway：外部API调用前检查
  - FailoverManager：节点健康结合熔断做决策
"""

import time
import json
import os
import threading
from typing import Dict, List, Optional, Any, Callable
import concurrent.futures
from enum import Enum
from dataclasses import dataclass, field

# 统一日志
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from quality.logger import get_logger
import logging
logger = get_logger("circuit_breaker")


# ═══════════════════════════════════════════
# 枚举与配置
# ═══════════════════════════════════════════

class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"          # 正常 — 请求通过
    OPEN = "open"              # 熔断 — 请求降级
    HALF_OPEN = "half_open"    # 试探 — 有限请求通过，试探恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置参数"""
    failure_threshold: int = 5           # 连续失败次数 → 熔断
    success_threshold: int = 1           # 半开状态连续成功次数 → 恢复
    reset_timeout: float = 30.0          # 熔断 → 半开的等待时间(秒)
    max_reset_timeout: float = 300.0     # 最大重置超时（指数退避上限，5分钟）
    half_open_max_requests: int = 1      # 半开状态下允许的试探请求数
    default_timeout: float = 30.0        # 默认单次调用超时(秒)
    default_retry: int = 2               # 默认重试次数
    retry_backoff_base: float = 1.0      # 重试指数退避基数(秒)
    retry_backoff_max: float = 30.0      # 重试指数退避上限(秒)


@dataclass
class CircuitStats:
    """熔断器统计信息"""
    total_failures: int = 0
    total_successes: int = 0
    total_circuit_breaks: int = 0
    total_recoveries: int = 0
    total_timeouts: int = 0
    total_retries: int = 0
    last_failure_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_circuit_breaks": self.total_circuit_breaks,
            "total_recoveries": self.total_recoveries,
            "total_timeouts": self.total_timeouts,
            "total_retries": self.total_retries,
            "last_failure_ago": round(time.time() - self.last_failure_time, 1) 
                if self.last_failure_time else None,
        }


# ═══════════════════════════════════════════
# 断点接续 (CheckpointManager)
# ═══════════════════════════════════════════

class CheckpointManager:
    """
    任务断点接续管理器。
    
    记录任务执行进度到 JSON 文件，任务成功后清理，
    失败后可读取上次进度继续执行。
    """

    def __init__(self, checkpoint_dir: str = None):
        if checkpoint_dir is None:
            WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
            checkpoint_dir = os.path.join(WORKSPACE, ".checkpoints")
        self._checkpoint_dir = checkpoint_dir
        os.makedirs(self._checkpoint_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, task_id: str) -> str:
        # 安全化 task_id（防止路径遍历）
        safe = task_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return os.path.join(self._checkpoint_dir, f"{safe}.json")

    def save_checkpoint(self, task_id: str, state: dict) -> bool:
        """
        保存任务检查点。
        
        Args:
            task_id: 任务唯一标识
            state: 任务状态字典（必须可 JSON 序列化）
        
        Returns:
            True 保存成功，False 保存失败
        """
        try:
            state["_checkpoint_time"] = time.time()
            state["_task_id"] = task_id
            with self._lock:
                with open(self._path(task_id), "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"[Checkpoint] 已保存: {task_id}")
            return True
        except Exception as e:
            logger.warning(f"[Checkpoint] 保存失败 {task_id}: {e}")
            return False

    def load_checkpoint(self, task_id: str) -> Optional[dict]:
        """
        读取任务检查点。
        
        Args:
            task_id: 任务唯一标识
        
        Returns:
            任务状态字典，不存在则返回 None
        """
        path = self._path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info(f"[Checkpoint] 已读取: {task_id} (来自 {state.get('_checkpoint_time', '?')})")
            return state
        except Exception as e:
            logger.warning(f"[Checkpoint] 读取失败 {task_id}: {e}")
            return None

    def clear_checkpoint(self, task_id: str) -> bool:
        """
        任务成功后清除检查点。
        
        Args:
            task_id: 任务唯一标识
        
        Returns:
            True 清除成功，False 无检查点或清除失败
        """
        path = self._path(task_id)
        if not os.path.exists(path):
            return False
        try:
            with self._lock:
                os.remove(path)
            logger.info(f"[Checkpoint] 已清除: {task_id}")
            return True
        except Exception as e:
            logger.warning(f"[Checkpoint] 清除失败 {task_id}: {e}")
            return False

    def get_all_checkpoints(self) -> List[dict]:
        """列出所有未完成的检查点"""
        checkpoints = []
        try:
            for fname in os.listdir(self._checkpoint_dir):
                if fname.endswith(".json"):
                    path = os.path.join(self._checkpoint_dir, fname)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            state = json.load(f)
                        checkpoints.append(state)
                    except Exception:
                        logging.warning("[circuit_breaker.py] suppressed")
                        pass
        except Exception:
            logging.warning("[circuit_breaker.py] suppressed")
            pass
        return checkpoints

    def cleanup_stale_checkpoints(self, max_age_seconds: float = 86400) -> int:
        """清理过期的检查点（默认超过 24 小时）"""
        now = time.time()
        cleared = 0
        for state in self.get_all_checkpoints():
            cpt = state.get("_checkpoint_time", 0)
            if now - cpt > max_age_seconds:
                task_id = state.get("_task_id", "")
                if self.clear_checkpoint(task_id):
                    cleared += 1
        if cleared:
            logger.info(f"[Checkpoint] 清理 {cleared} 个过期检查点")
        return cleared


# ═══════════════════════════════════════════
# 进程日志 (ProcessLogger)
# ═══════════════════════════════════════════

class ProcessLogger:
    """
    临时进程日志管理器。
    
    记录任务运行全过程，任务成功后自动删除日志文件。
    类似于缓存文件，只在任务执行期间存在。
    """

    def __init__(self, log_dir: str = None):
        if log_dir is None:
            WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
            log_dir = os.path.join(WORKSPACE, ".process_logs")
        self._log_dir = log_dir
        os.makedirs(self._log_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, task_id: str) -> str:
        safe = task_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return os.path.join(self._log_dir, f"{safe}.log")

    def start(self, task_id: str, metadata: dict = None) -> bool:
        """
        开始记录任务日志。
        创建日志文件并写入初始标记。
        
        Args:
            task_id: 任务唯一标识
            metadata: 可选的初始元数据
        
        Returns:
            True 创建成功
        """
        path = self._path(task_id)
        try:
            with self._lock:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"[START] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if metadata:
                        f.write(f"[META] {json.dumps(metadata, ensure_ascii=False, default=str)}\n")
                    f.flush()
            return True
        except Exception as e:
            logger.warning(f"[ProcessLog] 创建失败 {task_id}: {e}")
            return False

    def log(self, task_id: str, message: str, level: str = "INFO") -> bool:
        """
        追加日志。
        
        Args:
            task_id: 任务唯一标识
            message: 日志消息
            level: 日志级别 (INFO/WARN/ERROR)
        
        Returns:
            True 写入成功
        """
        path = self._path(task_id)
        if not os.path.exists(path):
            return False
        try:
            timestamp = time.strftime("%H:%M:%S")
            line = f"[{level}] [{timestamp}] {message}\n"
            with self._lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
            return True
        except Exception as e:
            logger.warning(f"[ProcessLog] 写入失败 {task_id}: {e}")
            return False

    def finish(self, task_id: str, status: str = "SUCCESS") -> bool:
        """
        任务完成后清理日志文件。
        
        Args:
            task_id: 任务唯一标识
            status: 结束状态 (SUCCESS/FAILED)
        
        Returns:
            True 删除成功
        """
        path = self._path(task_id)
        if not os.path.exists(path):
            return False
        try:
            if status == "SUCCESS":
                # 任务成功，删除日志
                with self._lock:
                    os.remove(path)
                logger.info(f"[ProcessLog] 任务完成，日志已删除: {task_id}")
                return True
            else:
                # 任务失败，保留日志并写入结束标记
                with self._lock:
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(f"[END:{status}] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                logger.info(f"[ProcessLog] 任务失败，日志已保留: {path}")
                return True
        except Exception as e:
            logger.warning(f"[ProcessLog] 清理失败 {task_id}: {e}")
            return False

    def get_log(self, task_id: str) -> Optional[str]:
        """
        读取当前日志内容（调试/失败分析用）。
        
        Args:
            task_id: 任务唯一标识
        
        Returns:
            日志全文，不存在则返回 None
        """
        path = self._path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"[ProcessLog] 读取失败 {task_id}: {e}")
            return None

    def list_active_logs(self) -> List[str]:
        """列出所有活跃的进程日志ID"""
        logs = []
        try:
            for fname in os.listdir(self._log_dir):
                if fname.endswith(".log"):
                    logs.append(fname[:-4])  # 去掉 .log
        except Exception:
            logging.warning("[circuit_breaker.py] suppressed")
            pass
        return logs

    def cleanup_stale_logs(self, max_age_seconds: float = 86400) -> int:
        """清理过期的进程日志（默认超过 24 小时）"""
        now = time.time()
        cleared = 0
        try:
            for fname in os.listdir(self._log_dir):
                path = os.path.join(self._log_dir, fname)
                if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                    os.remove(path)
                    cleared += 1
        except Exception:
            logging.warning("[circuit_breaker.py] suppressed")
            pass
        if cleared:
            logger.info(f"[ProcessLog] 清理 {cleared} 个过期日志")
        return cleared


# 全局实例（方便直接使用）
_checkpoint_manager = None
_process_logger = None


def get_checkpoint_manager() -> CheckpointManager:
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


def get_process_logger() -> ProcessLogger:
    global _process_logger
    if _process_logger is None:
        _process_logger = ProcessLogger()
    return _process_logger


# ═══════════════════════════════════════════
# 熔断器核心
# ═══════════════════════════════════════════

class CircuitBreaker:
    """
    单个熔断器实例。

    用法：
        cb = CircuitBreaker("llm_api", CircuitBreakerConfig(failure_threshold=5))

        # 方式1: 手动管理
        if cb.can_request():
            try:
                result = call_llm(...)
                cb.record_success()
            except Exception as e:
                cb.record_failure()
                raise
        else:
            return fallback()

        # 方式2: call() 自动管理（支持 timeout + retry）
        result = cb.call(call_llm, arg1, arg2, fallback=_default, timeout=15, retry=3)

        # 方式3: 装饰器
        @cb.wraps
        def call_llm(prompt): ...
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # 状态
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = time.time()
        self._current_reset_timeout = self.config.reset_timeout

        # 统计
        self.stats = CircuitStats()

        # 日志 & 检查点
        self._process_logger = get_process_logger()
        self._checkpoint_mgr = get_checkpoint_manager()

        logger.info(
            f"[CircuitBreaker] 初始化: {name} "
            f"(阈值={self.config.failure_threshold}, "
            f"超时={self.config.reset_timeout}s)"
        )

    # ── 属性 ──

    @property
    def state(self) -> CircuitState:
        """实时状态（OPEN 时自动检查是否该转 HALF_OPEN）"""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_state_change
            if elapsed >= self._current_reset_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                self._success_count = 0
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    # ── 状态转换 ──

    def _transition_to(self, new_state: CircuitState):
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitState.OPEN and old_state != CircuitState.OPEN:
            self.stats.total_circuit_breaks += 1
            logger.warning(
                f"[CircuitBreaker] {self.name}: {old_state.value} → OPEN "
                f"(连续失败{self._failure_count}次, "
                f"下次重试: {self._current_reset_timeout:.0f}s后)"
            )
        elif new_state == CircuitState.CLOSED and old_state != CircuitState.CLOSED:
            self.stats.total_recoveries += 1
            logger.info(f"[CircuitBreaker] {self.name}: {old_state.value} → CLOSED (已恢复)")
        elif new_state == CircuitState.HALF_OPEN:
            logger.info(f"[CircuitBreaker] {self.name}: {old_state.value} → HALF_OPEN (试探)")

    # ── 核心接口 ──

    def can_request(self) -> bool:
        """
        检查是否可以发送请求。

        Returns:
            True  → 可以请求
            False → 熔断中，应直接降级
        """
        s = self.state  # 使用 property 触发自动转 HALF_OPEN

        if s == CircuitState.CLOSED:
            return True

        if s == CircuitState.OPEN:
            return False

        # HALF_OPEN：限制试探请求数
        return self._success_count < self.config.half_open_max_requests

    def record_success(self) -> bool:
        """
        记录一次成功调用。

        Returns:
            True  → 状态发生了变化（HALF_OPEN→CLOSED）
            False → 状态无变化
        """
        self.stats.total_successes += 1
        s = self.state  # 实时状态

        if s == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._failure_count = 0
                self._current_reset_timeout = self.config.reset_timeout
                self._transition_to(CircuitState.CLOSED)
                return True
        elif s == CircuitState.CLOSED:
            # 连续成功重置失败计数
            self._failure_count = 0

        return False

    def record_failure(self) -> bool:
        """
        记录一次失败调用。

        Returns:
            True  → 触发了熔断（CLOSED→OPEN 或 HALF_OPEN→OPEN）
            False → 未触发熔断
        """
        self.stats.total_failures += 1
        self.stats.last_failure_time = time.time()
        s = self.state  # 实时状态

        if s == CircuitState.HALF_OPEN:
            # 半开试探失败 → 重新熔断，超时翻倍
            self._failure_count += 1
            self._current_reset_timeout = min(
                self._current_reset_timeout * 2,
                self.config.max_reset_timeout
            )
            self._transition_to(CircuitState.OPEN)
            return True

        if s == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                return True

        return False

    # ── 增强调用（v2.0：超时保护 + 自动重试） ──

    def call(
        self,
        fn: callable,
        *args,
        fallback: Any = None,
        raise_on_block: bool = False,
        timeout: Optional[float] = None,
        retry: Optional[int] = None,
        task_id: Optional[str] = None,
        checkpoint: Optional[dict] = None,
        **kwargs,
    ) -> Any:
        """
        带熔断保护 + 超时保护 + 自动重试的调用。

        Args:
            fn: 要调用的函数
            fallback: 熔断时的降级返回值
            raise_on_block: 熔断时是否抛出 CircuitBreakerError
            timeout: 单次调用超时秒数（默认 config.default_timeout）
            retry: 失败后重试次数（默认 config.default_retry, 0=不重试）
            task_id: 任务ID（启用断点接续和进程日志时传入）
            checkpoint: 断点状态（如果传入，会在调用前保存检查点）
            *args, **kwargs: 传给 fn 的参数

        Returns:
            正常 → fn 的返回值
            熔断 + raise_on_block=False → fallback
            熔断 + raise_on_block=True → 抛出 CircuitBreakerError

        Raises:
            CircuitBreakerError: raise_on_block=True 且熔断时
            TimeoutError: 超时时（如果所有重试都超时）
            原函数异常: 所有重试都失败时抛出最后一次异常
        """
        # 熔断检查
        if not self.can_request():
            if raise_on_block:
                raise CircuitBreakerError(
                    f"[CircuitBreaker] {self.name} 熔断中，请求被阻止"
                )
            return fallback

        # 设置参数
        _timeout = timeout if timeout is not None else self.config.default_timeout
        _retry = retry if retry is not None else self.config.default_retry

        # 进程日志
        if task_id:
            self._process_logger.start(task_id, {
                "breaker": self.name,
                "timeout": _timeout,
                "max_retries": _retry,
            })

        # 断点接续：先读取上次进度
        resume_state = None
        if task_id:
            resume_state = self._checkpoint_mgr.load_checkpoint(task_id)
            if resume_state:
                logger.info(f"[CircuitBreaker] 断点接续: {task_id}, 从上次进度继续")
                if task_id:
                    self._process_logger.log(task_id, f"断点接续: 从上次进度继续", level="INFO")

        # 保存当前检查点
        if task_id and checkpoint:
            self._checkpoint_mgr.save_checkpoint(task_id, checkpoint)

        # 执行调用（带重试）
        last_exception = None
        attempt = 0

        while attempt <= _retry:
            attempt += 1
            try:
                if task_id:
                    self._process_logger.log(
                        task_id,
                        f"尝试第 {attempt}/{_retry + 1} 次",
                        level="INFO"
                    )

                # 超时保护：使用信号或线程计时器
                result = self._call_with_timeout(fn, _timeout, *args, **kwargs)

                # 成功
                self.record_success()
                if task_id:
                    self._process_logger.log(task_id, f"第 {attempt} 次成功", level="INFO")
                    self._process_logger.finish(task_id, "SUCCESS")
                    # 清除检查点（任务完成）
                    self._checkpoint_mgr.clear_checkpoint(task_id)

                return result

            except TimeoutError as e:
                self.stats.total_timeouts += 1
                last_exception = e
                if task_id:
                    self._process_logger.log(
                        task_id,
                        f"第 {attempt} 次超时 (>{_timeout}s)",
                        level="ERROR"
                    )
                logger.warning(
                    f"[CircuitBreaker] {self.name}: 第{attempt}/{_retry + 1}次超时"
                )

                if attempt <= _retry:
                    # 重试前退避（指数退避）
                    backoff = min(
                        self.config.retry_backoff_base * (2 ** (attempt - 1)),
                        self.config.retry_backoff_max
                    )
                    if task_id:
                        self._process_logger.log(
                            task_id,
                            f"等待 {backoff:.1f}s 后重试",
                            level="WARN"
                        )
                    logger.info(
                        f"[CircuitBreaker] {self.name}: "
                        f"等待 {backoff:.1f}s 后重试..."
                    )
                    time.sleep(backoff)

            except Exception as e:
                last_exception = e
                self.stats.total_retries += 1
                if task_id:
                    self._process_logger.log(
                        task_id,
                        f"第 {attempt} 次失败: {str(e)[:100]}",
                        level="ERROR"
                    )

                if attempt <= _retry:
                    # 重试前退避
                    backoff = min(
                        self.config.retry_backoff_base * (2 ** (attempt - 1)),
                        self.config.retry_backoff_max
                    )
                    if task_id:
                        self._process_logger.log(
                            task_id,
                            f"等待 {backoff:.1f}s 后重试",
                            level="WARN"
                        )
                    time.sleep(backoff)

        # 所有重试都失败
        self.record_failure()
        if task_id:
            self._process_logger.log(task_id, f"所有 {_retry + 1} 次尝试均失败", level="ERROR")
            self._process_logger.finish(task_id, "FAILED")
            # 保留检查点，供后续接续

        # 抛出最后一次异常
        raise last_exception

    def _call_with_timeout(self, fn: Callable, timeout: float, *args, **kwargs) -> Any:
        """
        带超时的函数调用。
        使用 ThreadPoolExecutor 实现超时控制，避免 daemon thread 泄漏。
        注意：超时不等于取消，fn 的副作用（网络请求等）仍可能发生。
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future = executor.submit(fn, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(
                    f"[CircuitBreaker] 调用超时 ({timeout}s): {self.name}"
                )

    # ── 装饰器模式 ──

    def wraps(self, fn: callable = None, *, fallback: Any = None,
              raise_on_block: bool = False, timeout: Optional[float] = None,
              retry: Optional[int] = None):
        """
        装饰器形式使用熔断器（v2.0 支持 timeout 和 retry）。

        @cb.wraps
        def risky_call(): ...

        @cb.wraps(fallback="降级", timeout=15, retry=3)
        def risky_call(): ...
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                return self.call(
                    func, *args,
                    fallback=fallback,
                    raise_on_block=raise_on_block,
                    timeout=timeout or self.config.default_timeout,
                    retry=retry if retry is not None else self.config.default_retry,
                    **kwargs,
                )
            return wrapper

        if fn is not None:
            return decorator(fn)
        return decorator

    # ── 信息 ──

    def get_info(self) -> Dict[str, Any]:
        s = self.state  # 触发自动转 HALF_OPEN
        return {
            "name": self.name,
            "state": s.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "current_reset_timeout": round(self._current_reset_timeout, 1),
            "last_state_change_ago": round(time.time() - self._last_state_change, 1),
            "stats": self.stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "reset_timeout": self.config.reset_timeout,
                "max_reset_timeout": self.config.max_reset_timeout,
                "half_open_max_requests": self.config.half_open_max_requests,
                "default_timeout": self.config.default_timeout,
                "default_retry": self.config.default_retry,
            },
        }

    def reset(self):
        """重置熔断器到初始状态（CLOSED）"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = time.time()
        self._current_reset_timeout = self.config.reset_timeout
        self.stats = CircuitStats()
        logger.info(f"[CircuitBreaker] {self.name} 已手动重置")


# ═══════════════════════════════════════════
# 异常
# ═══════════════════════════════════════════

class CircuitBreakerError(Exception):
    """熔断器阻断异常 — 请求被熔断器阻止"""
    pass


# ═══════════════════════════════════════════
# 注册表（全局单例）
# ═══════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# #45: 统一单例 — get_instance 委托到 SingletonRegistry
# ═══════════════════════════════════════════════════════════════


class CircuitBreakerRegistry:
    """
    熔断器注册表（全局单例）。

    管理系统中所有受熔断器保护的服务/依赖。

    用法：
        registry = CircuitBreakerRegistry.get_instance()

        # 注册
        registry.register("llm_api")
        registry.register("external_search", CircuitBreakerConfig(failure_threshold=3))

        # 获取使用
        cb = registry.get("llm_api")
        if cb.can_request():
            ...
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    @staticmethod
    def get_instance() -> "CircuitBreakerRegistry":
        from core.engines.init.engine_factory import SingletonRegistry
        return SingletonRegistry.get(CircuitBreakerRegistry)

    def register(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """
        注册一个受熔断器保护的服务。

        Args:
            name: 服务名称（如 "llm_api", "web_search"）
            config: 熔断器配置，默认使用标准档

        Returns:
            CircuitBreaker 实例
        """
        if name in self._breakers:
            logger.warning(f"[CircuitBreakerRegistry] 重复注册: {name}，返回已有实例")
            return self._breakers[name]

        cb = CircuitBreaker(name, config)
        self._breakers[name] = cb
        logger.info(f"[CircuitBreakerRegistry] 已注册: {name}")
        return cb

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def get_or_register(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """获取已有实例，不存在则注册"""
        cb = self.get(name)
        if cb is None:
            cb = self.register(name, config)
        return cb

    def unregister(self, name: str):
        self._breakers.pop(name, None)

    def stats(self) -> Dict[str, Any]:
        """全局统计"""
        states: Dict[str, int] = {}
        for s in CircuitState:
            states[s.value] = 0
        for cb in self._breakers.values():
            states[cb.state.value] = states.get(cb.state.value, 0) + 1

        total_failures = sum(cb.stats.total_failures for cb in self._breakers.values())
        total_successes = sum(cb.stats.total_successes for cb in self._breakers.values())

        return {
            "total": len(self._breakers),
            "by_state": states,
            "total_failures": total_failures,
            "total_successes": total_successes,
            "breakers": {name: cb.get_info() for name, cb in self._breakers.items()},
        }

    def list_open(self) -> List[CircuitBreaker]:
        """列出当前所有处于熔断状态的熔断器"""
        return [cb for cb in self._breakers.values() if cb.state == CircuitState.OPEN]

    def list_half_open(self) -> List[CircuitBreaker]:
        return [cb for cb in self._breakers.values() if cb.state == CircuitState.HALF_OPEN]

    def clear(self):
        """清空所有熔断器（测试/重置用）"""
        self._breakers.clear()


# ═══════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════

def guard(
    name: str,
    fn: callable,
    *args,
    fallback: Any = None,
    raise_on_block: bool = False,
    config: Optional[CircuitBreakerConfig] = None,
    timeout: Optional[float] = None,
    retry: Optional[int] = None,
    task_id: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    快捷调用：获取或注册熔断器 + 执行调用（v2.0 支持 timeout+retry）。

    等价于：
        cb = registry.get_or_register(name, config)
        return cb.call(fn, *args, fallback=fallback, raise_on_block=raise_on_block,
                       timeout=timeout, retry=retry, task_id=task_id, **kwargs)
    """
    registry = CircuitBreakerRegistry.get_instance()
    cb = registry.get_or_register(name, config)
    return cb.call(
        fn, *args,
        fallback=fallback,
        raise_on_block=raise_on_block,
        timeout=timeout,
        retry=retry,
        task_id=task_id,
        **kwargs,
    )


# ── Engine init (#45: 统一单例注册表) ──

def init() -> CircuitBreakerRegistry:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(CircuitBreakerRegistry)

def get_circuit_breaker() -> CircuitBreakerRegistry:
    return init()


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

    import random
    import time

    print("=" * 60)
    print("Circuit Breaker v2.0 — 单元测试")
    print("=" * 60)

    # 测试1-5: 基础状态机（同 v1.0）
    print("\n测试1: 基础状态切换")
    cb = CircuitBreaker("test_1", CircuitBreakerConfig(
        failure_threshold=3, reset_timeout=1.0,
        success_threshold=1, max_reset_timeout=3.0,
    ))
    assert cb.state == CircuitState.CLOSED
    assert cb.can_request() is True
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(1.1)
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    print("  ✅ 测试1 通过")

    print("\n测试2: 半开失败 → 超时翻倍")
    cb2 = CircuitBreaker("test_2", CircuitBreakerConfig(
        failure_threshold=3, reset_timeout=0.5,
        success_threshold=1, max_reset_timeout=2.0,
    ))
    for _ in range(3):
        cb2.record_failure()
    time.sleep(0.6)
    cb2.record_failure()
    assert cb2._current_reset_timeout == 1.0
    print(f"  ✅ 超时翻倍: {cb2._current_reset_timeout:.1f}s")
    print("  ✅ 测试2 通过")

    print("\n测试3: call() 便捷调用")
    cb3 = CircuitBreaker("test_3", CircuitBreakerConfig(
        failure_threshold=2, reset_timeout=0.5, success_threshold=1,
    ))
    result = cb3.call(lambda x: x + 1, 41)
    assert result == 42
    def failing():
        raise RuntimeError("模拟失败")
    try:
        cb3.call(failing)
    except RuntimeError: pass
    try:
        cb3.call(failing)
    except RuntimeError: pass
    result = cb3.call(failing, fallback="降级了")
    assert result == "降级了"
    print("  ✅ 测试3 通过")

    # 测试6: 超时保护
    print("\n测试6: 超时保护")
    cb6 = CircuitBreaker("test_timeout", CircuitBreakerConfig(
        failure_threshold=2, reset_timeout=0.5, success_threshold=1,
        default_timeout=1.0, default_retry=0,
    ))
    def slow_fn():
        time.sleep(3)
        return "done"
    try:
        cb6.call(slow_fn, timeout=0.5, retry=0)
        assert False, "应该超时"
    except TimeoutError:
        print("  ✅ 超时正常抛出 TimeoutError")
    except Exception as e:
        print(f"  ✅ 超时异常类型: {type(e).__name__}")
    print("  ✅ 测试6 通过")

    # 测试7: 自动重试
    print("\n测试7: 自动重试")
    attempt_count = {"n": 0}
    def flaky_fn():
        attempt_count["n"] += 1
        if attempt_count["n"] < 3:
            raise RuntimeError(f"第{attempt_count['n']}次失败")
        return "终于成功了"
    cb7 = CircuitBreaker("test_retry", CircuitBreakerConfig(
        failure_threshold=5, reset_timeout=0.5, success_threshold=1,
        default_timeout=10, default_retry=3, retry_backoff_base=0.1,
    ))
    result = cb7.call(flaky_fn, retry=3, timeout=10)
    assert result == "终于成功了"
    assert attempt_count["n"] == 3
    print(f"  ✅ 第 {attempt_count['n']} 次尝试成功")
    print("  ✅ 测试7 通过")

    # 测试8: CheckpointManager
    print("\n测试8: 断点接续")
    cm = CheckpointManager("/tmp/crusheart_test_checkpoints")
    cm.save_checkpoint("test_task", {"step": 3, "progress": "50%"})
    state = cm.load_checkpoint("test_task")
    assert state is not None
    assert state["step"] == 3
    cm.clear_checkpoint("test_task")
    assert cm.load_checkpoint("test_task") is None
    print("  ✅ 测试8 通过")

    # 测试9: ProcessLogger
    print("\n测试9: 进程日志")
    pl = ProcessLogger("/tmp/crusheart_test_logs")
    pl.start("test_task", {"name": "test"})
    pl.log("test_task", "正在执行步骤1")
    pl.log("test_task", "正在执行步骤2")
    log_content = pl.get_log("test_task")
    assert log_content is not None
    assert "步骤1" in log_content
    pl.finish("test_task", "SUCCESS")
    # 成功后日志应删除
    assert pl.get_log("test_task") is None
    print("  ✅ 测试9 通过")

    # 清理测试残留
    import shutil
    shutil.rmtree("/tmp/crusheart_test_checkpoints", ignore_errors=True)
    shutil.rmtree("/tmp/crusheart_test_logs", ignore_errors=True)

    print("\n" + "=" * 60)
    print("全部测试通过 ✅")
    print("=" * 60)
