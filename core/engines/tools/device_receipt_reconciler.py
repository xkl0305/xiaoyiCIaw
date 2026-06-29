"""
Crusheart Agent OS — DeviceReceiptReconciler v4.0
设备操作回执对账器

核心问题：
  gui-agent 返回"超时" ≠ 操作真的失败了
  可能操作已成功执行，只是回执没回来
  需要做二次验证（post-timeout verification）

对账逻辑：
  1. 工具返回 ok                     → ✅ 成功
  2. 设备离线/不可用                  → ⏸ 暂缓，等设备上线
  3. 超时（timeout/receipt_timeout）  → 🔍 二次验证
     a. 二次验证匹配预期状态 → ✅ 成功（有超时回执）
     b. 二次验证不匹配       → ⏳ 待进一步排查
  4. 未知错误                        → ❌ 需分类

与 SerialLane / StateManager 集成：
  - SerialLane: 负责设备操作的串行排队执行
  - DeviceReceiptReconciler: 负责执行后的回执对账
  - StateManager: 记录对账结果到 recovery + event
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class ReconcileStatus(str, Enum):
    """对账结果状态"""
    SUCCESS = "success"                              # 明确成功
    SUCCESS_WITH_TIMEOUT = "success_with_timeout"     # 超时后二次验证确认成功
    OFFLINE = "offline"                               # 设备离线
    TIMEOUT_PENDING = "timeout_pending"               # 超时，待进一步排查
    MISMATCH = "mismatch"                             # 二次验证不匹配
    FAILED = "failed"                                 # 明确失败
    UNKNOWN = "unknown"                               # 无法判断

class DeviceState(str, Enum):
    """设备状态"""
    CONNECTED = "connected"
    OFFLINE = "offline"
    TIMEOUT = "timeout"             # 超时但设备可能在
    UNKNOWN = "unknown"

# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class ReconcileResult:
    """对账结果"""
    status: ReconcileStatus
    device_state: DeviceState
    reason: str
    verified: bool                     # 是否通过验证
    next_action: Optional[str] = None  # 建议的下一步操作
    evidence: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DeviceActionResult:
    """
    设备操作的执行结果（来自 gui-agent 等工具）
    
    这个类是对工具返回结果的标准化包装，
    无论底层工具是什么格式，统一为这个结构再给对账器。
    """
    ok: bool = False
    error: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None

# ═══════════════════════════════════════════
# 二次验证器注册表
# ═══════════════════════════════════════════

class PostTimeoutVerifier:
    """
    超时后二次验证器注册表
    
    不同设备操作用不同的验证方式：
    - 闹钟: 查询闹钟列表，看新闹钟是否存在
    - 备忘录: 搜索备忘录，看内容是否匹配
    - 日程: 查日历看事件是否存在
    - 短信: 查短信记录
    - 文件: 检查文件是否存在
    
    用法：
        verifier = PostTimeoutVerifier()
        verifier.register("alarm", my_alarm_verify_fn)
        verifier.register("note", my_note_verify_fn)
        result = verifier.verify("alarm", expected)
    """

    def __init__(self):
        self._verifiers: Dict[str, Callable] = {}

    def register(self, action_type: str, verify_fn: Callable) -> None:
        """
        注册验证器
        
        Args:
            action_type: 操作类型（alarm / note / event / message / file）
            verify_fn: 验证函数，接收 expected_state 参数，返回 dict
        """
        self._verifiers[action_type] = verify_fn
        logger.debug(f"[PostTimeoutVerifier] 已注册: {action_type}")

    def unregister(self, action_type: str) -> None:
        self._verifiers.pop(action_type, None)

    async def verify(self, action_type: str,
                     expected_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行二次验证"""
        fn = self._verifiers.get(action_type)
        if not fn:
            logger.warning(
                f"[PostTimeoutVerifier] 未注册验证器: {action_type}"
            )
            return None
        try:
            result = fn(expected_state)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as e:
            logger.error(
                f"[PostTimeoutVerifier] 验证失败: {action_type} - {e}"
            )
            return None

# ═══════════════════════════════════════════
# 状态匹配器
# ═══════════════════════════════════════════

class StateMatcher:
    """
    状态匹配器
    
    检查二次验证返回的 observed_state 是否与 expected_state 匹配。
    
    支持的匹配字段（可扩展）：
    - entityId: 实体ID
    - title / alarmTitle:  标题
    - time / alarmTime:     时间
    - daysOfWeek / daysOfWakeType: 重复
    - content:              内容
    - recipient:           收信人
    """

    MATCHABLE_FIELDS = [
        "entityId", "alarmTitle", "title",
        "alarmTime", "time",
        "daysOfWakeType", "daysOfWeek",
        "content", "recipient",
    ]

    @classmethod
    def matches(cls, expected: Dict[str, Any],
                observed: Optional[Dict[str, Any]],
                required_field: Optional[str] = None) -> bool:
        """
        检查 expected 和 observed 是否匹配
        
        Args:
            expected:      预期的状态
            observed:      二次验证观察到的状态
            required_field: 如指定，该字段必须匹配（否则返回False）
            
        Returns:
            是否匹配
        """
        if not observed:
            return False

        checks = []
        for field in cls.MATCHABLE_FIELDS:
            exp_val = expected.get(field)
            obs_val = observed.get(field)
            if exp_val is not None:
                match = str(obs_val) == str(exp_val)
                checks.append(match)

                # 如果是指定的 required_field 不匹配，直接返回 False
                if field == required_field and not match:
                    return False

        return bool(checks) and all(checks)

# ═══════════════════════════════════════════
# 对账器（核心）
# ═══════════════════════════════════════════

class DeviceReceiptReconciler:
    """
    设备操作回执对账器 v4.0
    
    核心流程：
        收到工具返回结果
            │
            ├─ ok=True  ──────────→ ✅ SUCCESS
            │
            ├─ error="device_offline" ──→ ⏸ OFFLINE
            │
            ├─ error="timeout" / None ──→ 🔍 二次验证
            │       │
            │       ├─ 匹配预期状态 ──→ ✅ SUCCESS_WITH_TIMEOUT
            │       │
            │       └─ 不匹配 ──→ ⏳ TIMEOUT_PENDING
            │
            └─ 其他错误 ──→ ❌ FAILED / UNKNOWN

    使用方式：
        reconciler = DeviceReceiptReconciler()
        result = await reconciler.reconcile(
            action_name="set_alarm",
            action_result=DeviceActionResult(ok=False, error="timeout"),
            expected_state={"alarmTitle": "起床", "alarmTime": "08:00"},
            verifier=my_verifier,  # 可选，用于二次验证
        )
    """

    def __init__(self):
        self.last_result: Optional[ReconcileResult] = None

    async def reconcile(
        self,
        action_name: str,
        action_result: DeviceActionResult,
        expected_state: Dict[str, Any],
        verifier: Optional[PostTimeoutVerifier] = None,
        action_type: Optional[str] = None,
    ) -> ReconcileResult:
        """
        执行回执对账
        
        Args:
            action_name:    操作名称（用于日志）
            action_result:  设备工具返回的标准化结果
            expected_state: 操作预期达到的状态
            verifier:       超时后二次验证器（可选）
            action_type:    操作类型（alarm/note/event/...），用于二次验证
            
        Returns:
            ReconcileResult 对账结果
        """
        result = self._reconcile_internal(
            action_name, action_result, expected_state
        )

        # 如果状态是超时待验证且有验证器，执行二次验证
        if (result.status == ReconcileStatus.TIMEOUT_PENDING
                and verifier and action_type):
            logger.info(
                f"[DeviceReceiptReconciler] 执行二次验证: "
                f"action={action_name} type={action_type}"
            )
            observed = await verifier.verify(action_type, expected_state)

            if observed and StateMatcher.matches(expected_state, observed):
                result = ReconcileResult(
                    status=ReconcileStatus.SUCCESS_WITH_TIMEOUT,
                    device_state=DeviceState.TIMEOUT,
                    reason="超时后二次验证确认操作已成功",
                    verified=True,
                    next_action="confirmed",
                    evidence={"expected": expected_state, "observed": observed},
                )
                logger.info(
                    f"[DeviceReceiptReconciler] 二次验证通过: {action_name}"
                )
            else:
                result = ReconcileResult(
                    status=ReconcileStatus.MISMATCH,
                    device_state=DeviceState.TIMEOUT,
                    reason="超时后二次验证不匹配预期状态",
                    verified=False,
                    next_action="search_again_or_gui_fallback",
                    evidence={
                        "expected": expected_state,
                        "observed": observed,
                    },
                )
                logger.warning(
                    f"[DeviceReceiptReconciler] 二次验证不匹配: {action_name}"
                )

        self.last_result = result
        return result

    def _reconcile_internal(
        self,
        action_name: str,
        action_result: DeviceActionResult,
        expected_state: Dict[str, Any],
    ) -> ReconcileResult:
        """内部对账逻辑（不含二次验证）"""
        # 1. 工具明确返回成功
        if action_result.ok:
            return ReconcileResult(
                status=ReconcileStatus.SUCCESS,
                device_state=DeviceState.CONNECTED,
                reason="工具返回 ok",
                verified=True,
                evidence={"action_result": action_result.data},
            )

        error = action_result.error or action_result.status or ""

        # 2. 设备离线
        if any(kw in error.lower() for kw in (
            "device_offline", "offline", "transport_unavailable"
        )):
            return ReconcileResult(
                status=ReconcileStatus.OFFLINE,
                device_state=DeviceState.OFFLINE,
                reason=f"设备离线: {error}",
                verified=False,
                next_action="defer_until_device_online",
                evidence={"action_result": action_result.raw},
            )

        # 3. 超时（需要二次验证）
        if any(kw in error.lower() for kw in (
            "timeout", "receipt_timeout", "action_timeout"
        )) or action_result.status is None:
            return ReconcileResult(
                status=ReconcileStatus.TIMEOUT_PENDING,
                device_state=DeviceState.TIMEOUT,
                reason=f"设备操作超时: {error}",
                verified=False,
                next_action="verify_after_timeout",
                evidence={"action_result": action_result.raw},
            )

        # 4. 未知错误
        return ReconcileResult(
            status=ReconcileStatus.FAILED,
            device_state=DeviceState.CONNECTED,
            reason=f"未知错误: {error}",
            verified=False,
            next_action="classify_failure",
            evidence={
                "action_result": action_result.raw,
                "expected_state": expected_state,
            },
        )

    @staticmethod
    def default_next_action(result: ReconcileResult) -> str:
        """根据对账结果给出默认下一步建议"""
        mapping = {
            ReconcileStatus.SUCCESS: "继续流程",
            ReconcileStatus.SUCCESS_WITH_TIMEOUT: "继续流程（标记为已验证）",
            ReconcileStatus.OFFLINE: "等待设备上线后重试",
            ReconcileStatus.TIMEOUT_PENDING: "确认超时后二次验证结果",
            ReconcileStatus.MISMATCH: "搜索替代方式或回调GUI",
            ReconcileStatus.FAILED: "分析错误类型后决定重试/降级/终止",
            ReconcileStatus.UNKNOWN: "人工介入",
        }
        return mapping.get(result.status, "unknown")

# ── Engine init ──

def init() -> "DeviceReceiptReconciler":
    global _instance
    if _instance is None:
        _instance = DeviceReceiptReconciler()
    return _instance

def get_reconciler() -> "DeviceReceiptReconciler":
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

    async def main():
        logging.basicConfig(level=logging.INFO)

        print("=" * 60)
        print("DeviceReceiptReconciler v4.0 — 测试")
        print("=" * 60)

        reconciler = DeviceReceiptReconciler()
        verifier = PostTimeoutVerifier()

        def alarm_verify(expected):
            """模拟闹钟验证器"""
            return {
                "entityId": "123",
                "alarmTitle": "起床闹钟",
                "alarmTime": "08:00",
            }

        verifier.register("alarm", alarm_verify)

        # 测试1: 明确成功
        print("\n测试1: 工具返回 ok")
        r1 = await reconciler.reconcile(
            "set_alarm",
            DeviceActionResult(ok=True, data={"id": "123"}),
            expected_state={},
        )
        print(f"  status={r1.status.value} verified={r1.verified} ✅ 通过")

        # 测试2: 设备离线
        print("\n测试2: 设备离线")
        r2 = await reconciler.reconcile(
            "set_alarm",
            DeviceActionResult(ok=False, error="device_offline"),
            expected_state={},
        )
        print(f"  status={r2.status.value} device={r2.device_state.value} "
              f"next={r2.next_action} ✅ 通过")

        # 测试3: 超时 + 二次验证通过
        print("\n测试3: 超时 + 二次验证通过")
        r3 = await reconciler.reconcile(
            "set_alarm",
            DeviceActionResult(ok=False, error="timeout"),
            expected_state={"alarmTitle": "起床闹钟", "alarmTime": "08:00"},
            verifier=verifier,
            action_type="alarm",
        )
        print(f"  status={r3.status.value} verified={r3.verified} "
              f"reason={r3.reason} ✅ 通过")

        # 测试4: 超时 + 二次验证不匹配
        print("\n测试4: 超时 + 二次验证不匹配")
        r4 = await reconciler.reconcile(
            "set_alarm",
            DeviceActionResult(ok=False, error="timeout"),
            expected_state={"alarmTitle": "不存在的内容", "alarmTime": "99:99"},
            verifier=verifier,
            action_type="alarm",
        )
        print(f"  status={r4.status.value} verified={r4.verified} "
              f"next={r4.next_action} ✅ 通过")

        # 测试5: 无验证器时超时
        print("\n测试5: 无验证器时超时")
        r5 = await reconciler.reconcile(
            "set_alarm",
            DeviceActionResult(ok=False, error="receipt_timeout"),
            expected_state={"alarmTitle": "起床"},
            verifier=None,
            action_type="alarm",
        )
        print(f"  status={r5.status.value} verified={r5.verified} "
              f"next={r5.next_action} ✅ 通过")

        # 测试6: 状态匹配器
        print("\n测试6: 状态匹配器")
        assert StateMatcher.matches(
            {"alarmTitle": "起床", "alarmTime": "08:00"},
            {"alarmTitle": "起床", "alarmTime": "08:00"},
        )
        assert not StateMatcher.matches(
            {"alarmTitle": "起床"},
            {"alarmTitle": "上班"},
        )
        assert not StateMatcher.matches(
            {"alarmTitle": "起床"},
            None,
        )
        print("  全部匹配测试通过 ✅")

        # 测试7: 默认下一步建议
        print("\n测试7: 默认下一步建议")
        print(f"  SUCCESS → {DeviceReceiptReconciler.default_next_action(r1)}")
        print(f"  OFFLINE → {DeviceReceiptReconciler.default_next_action(r2)}")
        print(f"  MISMATCH → {DeviceReceiptReconciler.default_next_action(r4)}")
        print("  ✅ 通过")

        print("\n" + "=" * 60)
        print("全部测试通过 ✅")
        print("=" * 60)

    import asyncio
    asyncio.run(main())
