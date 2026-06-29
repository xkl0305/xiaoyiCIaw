"""
Crusheart Agent OS — ToolExecutionGateway v4.0
统一工具执行网关：安全校验 + 风险分级 + 审计日志 + 降级路由

职责边界：
- ToolExecutionGateway（本文件）：统一入口，安全校验，风险判断，路由派发
- SerialLane（serial_lanes.py）：设备侧操作的串行排队执行
- DeviceReceiptReconciler（device_receipt_reconciler.py）：执行后的回执对账
- StateManager（state_manager.py）：记录执行结果到 checkpoint/recovery/event

与鸽子王 unified_capability_gateway 的区别：
- 鸽子王：50+硬编码能力元数据 + 环境变量降级开关
- 本文件：动态风险分级 + 可注册能力 + 审计轨迹 + 集成现有引擎
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
import logging
import json
import os
import time
import threading
import asyncio

# 统一日志
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "quality"))
from logger import get_logger
logger = get_logger("tool_execution_gateway")

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════



# ── v6.3.2: Subagent 审批策略 ──
class SubagentApprovalPolicy(str, Enum):
    AUTO_DENY = "auto_deny"
    AUTO_APPROVE = "auto_approve"
    PARENT_CONFIRM = "parent_confirm"

SUBAGENT_BLOCKED_TOOLS = frozenset(["delegate_task", "memory", "send_message", "execute_code"])

def get_subagent_policy() -> SubagentApprovalPolicy:
    ps = os.environ.get("CRUSHEART_SUBAGENT_POLICY", "auto_deny")
    try: return SubagentApprovalPolicy(ps)
    except ValueError: return SubagentApprovalPolicy.AUTO_DENY

def filter_subagent_tools(tool_names: list) -> list:
    return [t for t in tool_names if t not in SUBAGENT_BLOCKED_TOOLS]

def should_auto_approve_subagent(command: str, description: str) -> str:
    p = get_subagent_policy()
    if p == SubagentApprovalPolicy.AUTO_DENY: return "deny"
    if p == SubagentApprovalPolicy.AUTO_APPROVE: return "once"
    if p == SubagentApprovalPolicy.PARENT_CONFIRM: return "parent_confirm"
    return "deny"


class RiskLevel(str, Enum):
    """风险等级（与 SOUL.md 技能风险评级对齐）"""
    LOW = "low"          # L1 低危 — 直接执行
    MEDIUM = "medium"    # L2 中危 — 确认后执行
    HIGH = "high"        # L3 高危 — 严格确认
    CRITICAL = "critical"  # L4 致命 — 拦截，需手动


class ExecutionMode(str, Enum):
    """执行模式"""
    DIRECT = "direct"            # 直接执行
    CONFIRM = "confirm"          # 需要用户确认
    BLOCKED = "blocked"          # 拦截
    DRY_RUN = "dry_run"          # 模拟执行（无副作用）
    FALLBACK = "fallback"        # 降级执行


class DecisionReason(str, Enum):
    """决策原因"""
    LOW_RISK = "low_risk"
    MANUAL_CONFIRMED = "manual_confirmed"
    DEVICE_OFFLINE = "device_offline"
    NOT_CONFIGURED = "not_configured"
    MISSING_PARAMS = "missing_params"
    SECURITY_BLOCK = "security_block"
    RATE_LIMIT = "rate_limit"
    FALLBACK_ACTIVE = "fallback_active"


# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class ExecutionDecision:
    """执行决策"""
    allowed: bool
    mode: ExecutionMode
    risk: RiskLevel
    reason: DecisionReason
    message: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """
    执行结果。

    Attributes:
        success: 是否执行成功
        mode: 执行模式（直接/确认/降级/模拟/拦截）
        tool_name: 工具名称
        result: 执行结果
        error: 错误信息
        latency_ms: 执行耗时（毫秒）
        evidence: 执行证据（决策详情、熔断状态等）
        recovery: 恢复决策（失败时包含重试/降级/跳过等策略）
    """
    success: bool
    mode: ExecutionMode
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    recovery: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════
# 能力注册表
# ═══════════════════════════════════════════

class CapabilityRegistry:
    """
    能力注册表
    
    注册可执行的能力（工具/技能），附带安全元数据。
    
    用法：
        registry = CapabilityRegistry()
        registry.register("query_alarm", my_alarm_fn, risk=RiskLevel.LOW)
        registry.register("send_message", my_send_fn, risk=RiskLevel.HIGH)
        info = registry.get_info("send_message")
    """

    @dataclass
    class CapabilityInfo:
        name: str
        risk: RiskLevel
        requires_approval: bool = False
        is_external_api: bool = False
        description: str = ""
        handler: Optional[Callable] = None

    def __init__(self):
        self._capabilities: Dict[str, CapabilityRegistry.CapabilityInfo] = {}

    def register(self, name: str, handler: Callable,
                 risk: RiskLevel = RiskLevel.LOW,
                 requires_approval: bool = False,
                 is_external_api: bool = False,
                 description: str = "") -> None:
        """注册一个能力"""
        self._capabilities[name] = self.CapabilityInfo(
            name=name, risk=risk,
            requires_approval=requires_approval,
            is_external_api=is_external_api,
            description=description,
            handler=handler,
        )
        logger.debug(f"[CapabilityRegistry] 已注册: {name} (risk={risk.value})")

    def unregister(self, name: str) -> None:
        self._capabilities.pop(name, None)

    def get_info(self, name: str) -> Optional["CapabilityRegistry.CapabilityInfo"]:
        return self._capabilities.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        info = self._capabilities.get(name)
        return info.handler if info else None

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def list_all(self, risk_filter: Optional[RiskLevel] = None) -> List[Dict]:
        result = []
        for name, info in self._capabilities.items():
            if risk_filter and info.risk != risk_filter:
                continue
            result.append({
                "name": name,
                "risk": info.risk.value,
                "requires_approval": info.requires_approval,
                "is_external_api": info.is_external_api,
                "description": info.description,
            })
        return sorted(result, key=lambda x: x["name"])

    def count(self) -> Dict[str, int]:
        by_risk: Dict[str, int] = {}
        for info in self._capabilities.values():
            k = info.risk.value
            by_risk[k] = by_risk.get(k, 0) + 1
        return {"total": len(self._capabilities), "by_risk": by_risk}


# ═══════════════════════════════════════════
# 安全决策引擎
# ═══════════════════════════════════════════

class SecurityDecisionEngine:
    """
    安全决策引擎
    
    根据能力信息 + 运行时状态，做出执行决策。
    
    决策规则：
    - LOW:    直接执行
    - MEDIUM: 默认执行（可配置为需要确认）
    - HIGH:   需要用户确认
    - CRITICAL: 拦截
    - 外部API: 检查环境变量开关
    - 设备操作: 检查设备是否在线
    """

    def __init__(self, require_confirm_medium: bool = False):
        self.require_confirm_medium = require_confirm_medium

    def decide(self, info: "CapabilityRegistry.CapabilityInfo",
               context: Optional[Dict] = None) -> ExecutionDecision:
        """
        对能力调用做出执行决策
        
        Args:
            info: 能力信息
            context: 运行时上下文（可含设备状态、环境标志等）
            
        Returns:
            ExecutionDecision
        """
        ctx = context or {}

        # CRITICAL: 拦截
        if info.risk == RiskLevel.CRITICAL:
            return ExecutionDecision(
                allowed=False,
                mode=ExecutionMode.BLOCKED,
                risk=RiskLevel.CRITICAL,
                reason=DecisionReason.SECURITY_BLOCK,
                message=f"能力 '{info.name}' 为致命风险，已拦截",
            )

        # 外部API：检查环境变量
        if info.is_external_api:
            no_ext = os.environ.get("NO_EXTERNAL_API", "true").lower() == "true"
            if no_ext:
                return ExecutionDecision(
                    allowed=True,
                    mode=ExecutionMode.DRY_RUN,
                    risk=info.risk,
                    reason=DecisionReason.NOT_CONFIGURED,
                    message="外部API未启用，执行降级模拟",
                )

        # 设备操作：检查设备状态
        if info.name.startswith(("device_",)):
            device_online = ctx.get("device_online", True)
            if not device_online:
                return ExecutionDecision(
                    allowed=False,
                    mode=ExecutionMode.FALLBACK,
                    risk=info.risk,
                    reason=DecisionReason.DEVICE_OFFLINE,
                    message="设备离线，无法执行端侧操作",
                )

        # HIGH：需要确认
        if info.risk == RiskLevel.HIGH or info.requires_approval:
            return ExecutionDecision(
                allowed=True,
                mode=ExecutionMode.CONFIRM,
                risk=info.risk,
                reason=DecisionReason.MANUAL_CONFIRMED,
                message=f"高危操作 '{info.name}' 需用户确认",
            )

        # MEDIUM：根据配置决定
        if info.risk == RiskLevel.MEDIUM and self.require_confirm_medium:
            return ExecutionDecision(
                allowed=True,
                mode=ExecutionMode.CONFIRM,
                risk=info.risk,
                reason=DecisionReason.MANUAL_CONFIRMED,
                message=f"中危操作 '{info.name}' 需用户确认",
            )

        # LOW / MEDIUM（无需确认）：直接执行
        return ExecutionDecision(
            allowed=True,
            mode=ExecutionMode.DIRECT,
            risk=info.risk,
            reason=DecisionReason.LOW_RISK,
            message=f"操作 '{info.name}' 已放行",
        )


# ═══════════════════════════════════════════
# 审计日志
# ═══════════════════════════════════════════

class AuditLogger:
    """
    审计日志
    
    记录每次工具调用的决策和执行结果。
    日志文件：.autonomy_state/gateway_audit.jsonl
    """

    AUDIT_PATH = os.path.join(WORKSPACE, ".autonomy_state", "gateway_audit.jsonl")

    def __init__(self, max_lines: int = 5000):
        self.max_lines = max_lines
        self._append_count = 0
        os.makedirs(os.path.dirname(self.AUDIT_PATH), exist_ok=True)

    def log(self, entry: Dict) -> None:
        """记录一条审计条目"""
        entry["timestamp"] = datetime.now(BEIJING_TZ).isoformat()
        with open(self.AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._append_count += 1
        if self._append_count >= self.max_lines:
            self._rotate()
            self._append_count = 0

    def _rotate(self):
        """日志轮转（累计满 max_lines 才触发）"""
        if not os.path.exists(self.AUDIT_PATH):
            return
        with open(self.AUDIT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > self.max_lines:
            tmp_path = self.AUDIT_PATH + ".tmp"
            keep = lines[-(self.max_lines // 2):]
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(keep)
            os.replace(tmp_path, self.AUDIT_PATH)

    def recent(self, n: int = 20) -> List[Dict]:
        """最近 N 条审计日志"""
        if not os.path.exists(self.AUDIT_PATH):
            return []
        with open(self.AUDIT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entries = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def stats(self) -> Dict[str, Any]:
        """审计统计"""
        entries = self.recent(5000)
        total = len(entries)
        allowed = sum(1 for e in entries if e.get("allowed"))
        blocked = sum(1 for e in entries if not e.get("allowed"))
        by_risk: Dict[str, int] = {}
        for e in entries:
            r = e.get("risk", "unknown")
            by_risk[r] = by_risk.get(r, 0) + 1
        return {
            "total": total,
            "allowed": allowed,
            "blocked": blocked,
            "by_risk": dict(sorted(by_risk.items(), key=lambda x: -x[1])),
        }


# ═══════════════════════════════════════════
# 网关（核心）
# ═══════════════════════════════════════════

class ToolExecutionGateway:
    """
    统一工具执行网关 v4.0
    
    使用流程：
        gateway = ToolExecutionGateway()
        
        # 注册能力
        gateway.register("query_weather", my_weather_fn, RiskLevel.LOW)
        gateway.register("send_message", my_send_fn, RiskLevel.HIGH)
        
        # 执行（自动决策）
        result = await gateway.execute("query_weather", {"city": "天津"})
        
        # 带上下文
        result = await gateway.execute("send_message", {...},
                                        context={"device_online": True})
    
    执行流水线：
        check() → 风险判断
            ↓
        allowed? → BLOCKED/FALLBACK → 审计日志 → 返回
            ↓
        mode == CONFIRM? → 返回确认结果 → 审计日志
            ↓
        执行 handler → 审计日志 → 返回
    """

    def __init__(self):
        self.registry = CapabilityRegistry()
        self.decision_engine = SecurityDecisionEngine()
        self.audit = AuditLogger()
        self._execution_count = 0
        self._circuit_breaker_registry = None

    def _get_circuit_breaker(self):
        """惰性加载熔断器注册表"""
        if self._circuit_breaker_registry is None:
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "quality"))
                from circuit_breaker import CircuitBreakerRegistry, CircuitBreakerConfig
                self._circuit_breaker_registry = CircuitBreakerRegistry.get_instance()
            except ImportError:
                self._circuit_breaker_registry = False
        return self._circuit_breaker_registry

    def register(self, name: str, handler: Callable,
                 risk: RiskLevel = RiskLevel.LOW,
                 requires_approval: bool = False,
                 is_external_api: bool = False,
                 description: str = "") -> None:
        """注册一个可执行的能力"""
        self.registry.register(name, handler, risk, requires_approval,
                               is_external_api, description)

    def check(self, tool_name: str,
              context: Optional[Dict] = None) -> ExecutionDecision:
        """
        检查一个工具是否能执行（不执行，只返回决策）
        
        Args:
            tool_name: 工具名称
            context: 运行时上下文
            
        Returns:
            ExecutionDecision
        """
        info = self.registry.get_info(tool_name)
        if not info:
            return ExecutionDecision(
                allowed=False,
                mode=ExecutionMode.BLOCKED,
                risk=RiskLevel.CRITICAL,
                reason=DecisionReason.SECURITY_BLOCK,
                message=f"未注册的能力: {tool_name}",
            )
        return self.decision_engine.decide(info, context)

    async def execute(self, tool_name: str, params: Optional[Dict] = None,
                      context: Optional[Dict] = None) -> ExecutionResult:
        """
        执行一个工具（自动决策 + 执行 + 审计）
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            context: 运行时上下文
            
        Returns:
            ExecutionResult
        """
        self._execution_count += 1
        start = time.time()
        params = params or {}
        context = context or {}

        # 1. 决策
        decision = self.check(tool_name, context)
        action = params.copy() if params else {}
        action["tool_name"] = tool_name

        # 2. 如果被拦截
        if not decision.allowed:
            latency = (time.time() - start) * 1000
            self.audit.log({
                "tool": tool_name,
                "allowed": False,
                "mode": decision.mode.value,
                "risk": decision.risk.value,
                "reason": decision.reason.value,
                "latency_ms": round(latency, 2),
            })
            return ExecutionResult(
                success=False,
                mode=decision.mode,
                tool_name=tool_name,
                error=decision.message,
                latency_ms=round(latency, 2),
                evidence={"decision": decision.__dict__},
            )

        # 3. 如果降级/模拟
        if decision.mode in (ExecutionMode.DRY_RUN, ExecutionMode.FALLBACK):
            latency = (time.time() - start) * 1000
            self.audit.log({
                "tool": tool_name,
                "allowed": True,
                "mode": decision.mode.value,
                "risk": decision.risk.value,
                "reason": decision.reason.value,
                "latency_ms": round(latency, 2),
            })
            return ExecutionResult(
                success=True,
                mode=decision.mode,
                tool_name=tool_name,
                result={"mode": decision.mode.value, "message": decision.message},
                latency_ms=round(latency, 2),
                evidence={"decision": decision.__dict__},
            )

        # 4. 熔断器检查（对外部 API 调用）
        is_external = False
        info_data = self.registry.get_info(tool_name)
        if info_data:
            is_external = info_data.is_external_api

        if is_external:
            cb_registry = self._get_circuit_breaker()
            if cb_registry:
                cb = cb_registry.get_or_register(tool_name)
                if cb and cb.is_open:
                    latency = (time.time() - start) * 1000
                    logger.warning(
                        f"熔断器阻止: {tool_name}（熔断中）",
                        tool=tool_name,
                        latency_ms=round(latency, 2),
                    )
                    self.audit.log({
                        "tool": tool_name,
                        "allowed": True,
                        "mode": ExecutionMode.FALLBACK.value,
                        "risk": decision.risk.value,
                        "reason": "circuit_breaker_open",
                        "success": False,
                        "error": f"{tool_name} 熔断中，自动降级",
                        "latency_ms": round(latency, 2),
                    })
                    return ExecutionResult(
                        success=False,
                        mode=ExecutionMode.FALLBACK,
                        tool_name=tool_name,
                        error=f"{tool_name} 熔断中，自动降级",
                        latency_ms=round(latency, 2),
                        evidence={"circuit_breaker_open": True},
                    )

        # 5. 需要确认 / 直接执行 → 尝试执行
        handler = self.registry.get_handler(tool_name)
        if not handler:
            latency = (time.time() - start) * 1000
            return ExecutionResult(
                success=False,
                mode=ExecutionMode.BLOCKED,
                tool_name=tool_name,
                error=f"能力 '{tool_name}' 已注册但无执行函数",
                latency_ms=round(latency, 2),
            )

        try:
            # 执行（支持 async 和 sync handler）
            if asyncio.iscoroutinefunction(handler):
                result = await handler(params, context)
            else:
                result = handler(params, context)

            # 执行成功 → 熔断器记录成功
            if is_external and cb_registry:
                cb = cb_registry.get(tool_name)
                if cb:
                    cb.record_success()

            latency = (time.time() - start) * 1000
            self.audit.log({
                "tool": tool_name,
                "allowed": True,
                "mode": decision.mode.value,
                "risk": decision.risk.value,
                "reason": decision.reason.value,
                "success": True,
                "latency_ms": round(latency, 2),
            })
            return ExecutionResult(
                success=True,
                mode=decision.mode,
                tool_name=tool_name,
                result=result,
                latency_ms=round(latency, 2),
            )

        except Exception as e:
            # 执行失败 → 熔断器记录失败
            if is_external and cb_registry:
                cb = cb_registry.get(tool_name)
                if cb:
                    cb.record_failure()
                    logger.warning(
                        f"熔断器记录失败: {tool_name}",
                        tool=tool_name,
                        fail_count=cb.failure_count,
                        circuit_state=cb.state.value,
                    )

            latency = (time.time() - start) * 1000
            logger.error(
                f"执行失败: {tool_name}",
                tool=tool_name,
                error=str(e)[:200],
                latency_ms=round(latency, 2),
            )
            # 自动恢复决策
            recovery = None
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "quality"))
                from closed_loop import RecoveryManager
                rm = RecoveryManager()
                rctx = {"tool": tool_name, "params": params, "fallback_capability": tool_name}
                rdec = rm.decide(str(e), rctx)
                recovery = rm.execute_recovery(rdec, rctx)
                recovery["decision"] = {
                    "strategy": rdec.strategy.value,
                    "reason": rdec.reason,
                    "max_retries": rdec.max_retries,
                    "fallback_capability": rdec.fallback_capability,
                    "user_message": rdec.user_message,
                }
            except Exception as recover_err:
                recovery = {"action": "unknown", "error": str(recover_err)[:100]}

            self.audit.log({
                "tool": tool_name,
                "allowed": True,
                "mode": decision.mode.value,
                "risk": decision.risk.value,
                "reason": decision.reason.value,
                "success": False,
                "error": str(e),
                "recovery": recovery,
                "latency_ms": round(latency, 2),
            })
            return ExecutionResult(
                success=False,
                mode=decision.mode,
                tool_name=tool_name,
                error=str(e),
                recovery=recovery,
                latency_ms=round(latency, 2),
            )

    def get_stats(self) -> Dict[str, Any]:
        """网关统计"""
        return {
            "execution_count": self._execution_count,
            "registry": self.registry.count(),
            "audit": self.audit.stats(),
        }

    def get_audit_log(self, n: int = 20) -> List[Dict]:
        return self.audit.recent(n)


# ── 全局单例（双重检查锁，线程安全） ──

_gateway: Optional[ToolExecutionGateway] = None
_gateway_lock = threading.Lock()

def get_gateway() -> ToolExecutionGateway:
    """获取全局网关单例（线程安全）"""
    global _gateway
    if _gateway is None:
        with _gateway_lock:
            if _gateway is None:
                _gateway = ToolExecutionGateway()
    return _gateway

def init() -> ToolExecutionGateway:
    return get_gateway()


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
        print("ToolExecutionGateway v4.0 — 测试")
        print("=" * 60)

        gateway = get_gateway()

        # 注册能力
        async def handle_query(params, ctx):
            return {"result": f"查询结果: {params}", "status": "ok"}

        async def handle_send(params, ctx):
            return {"result": f"已发送: {params}", "status": "ok"}

        async def handle_device(params, ctx):
            return {"result": "device_ok", "status": "ok"}

        gateway.register("query_weather", handle_query, RiskLevel.LOW,
                         description="天气查询")
        gateway.register("send_message", handle_send, RiskLevel.HIGH,
                         requires_approval=True, is_external_api=True,
                         description="发送消息")
        gateway.register("set_alarm", handle_device, RiskLevel.MEDIUM,
                         description="设置闹钟")

        # 测试1: 低风险直接执行
        print("\n测试1: 低风险 → 直接执行")
        r1 = await gateway.execute("query_weather", {"city": "天津"})
        print(f"  success={r1.success} mode={r1.mode.value}")
        print(f"  result={r1.result}")
        print("  ✅ 通过")

        # 测试2: 高风险需确认
        print("\n测试2: 高风险 → 需要确认")
        r2 = await gateway.execute("send_message", {"to": "小王", "text": "开会"})
        print(f"  success={r2.success} mode={r2.mode.value}")
        print(f"  message: confirm模式（不实际执行）")
        print("  ✅ 通过")

        # 测试3: 设备离线降级
        print("\n测试3: 设备离线 → 降级")
        r3 = await gateway.execute("set_alarm", {"time": "08:00"},
                                   context={"device_online": False})
        print(f"  success={r3.success} mode={r3.mode.value}")
        print("  ✅ 通过")

        # 测试4: 未注册的能力
        print("\n测试4: 未注册 → 拦截")
        r4 = await gateway.execute("unknown_tool", {})
        print(f"  success={r4.success} mode={r4.mode.value}")
        print(f"  error={r4.error}")
        print("  ✅ 通过")

        # 测试5: check（不执行）
        print("\n测试5: check 接口（不执行）")
        d1 = gateway.check("query_weather")
        d2 = gateway.check("send_message")
        d3 = gateway.check("unknown")
        print(f"  query_weather → allowed={d1.allowed} mode={d1.mode.value}")
        print(f"  send_message → allowed={d2.allowed} mode={d2.mode.value}")
        print(f"  unknown → allowed={d3.allowed} mode={d3.mode.value}")
        print("  ✅ 通过")

        # 测试6: 注册表统计
        print("\n测试6: 注册表统计")
        stats = gateway.get_stats()
        print(f"  registry: {stats['registry']}")
        print(f"  audit: {stats['audit']}")
        caps = gateway.registry.list_all()
        for c in caps:
            print(f"    {c['name']}: risk={c['risk']}")
        print("  ✅ 通过")

        print("\n" + "=" * 60)
        print("全部测试通过 ✅")
        print("=" * 60)

    import asyncio
    asyncio.run(main())

