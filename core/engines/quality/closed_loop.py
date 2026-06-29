"""
Crusheart Agent OS — 闭环验证器 v1.0
Crusheart Agent OS — 闭环验证引擎
功能：ResultChecker + AuditWriter + RecoveryManager + FinalSummarizer 四合一
集成点：自进化引擎 reflect() 后自动调用，补充验证→恢复→摘要闭环
"""

import os, sys, json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import random
import time
import logging

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
HOOK_DIR = os.path.join(WORKSPACE, ".hooks")


# ================================================================
# 1. ResultChecker — 结果验证
# ================================================================

@dataclass
class VerificationResult:
    verified: bool
    status: str  # success, failed, uncertain
    message: str
    evidence: Dict[str, Any]


class ResultChecker:
    """结果检查器 — 验证执行结果是否达标"""

    @staticmethod
    def verify_platform_result(result: Dict[str, Any]) -> VerificationResult:
        success = result.get("success", False)
        status = result.get("status", "unknown")
        if success and status == "completed":
            return VerificationResult(True, "success", "执行成功", result)
        elif status == "result_uncertain":
            return VerificationResult(False, "uncertain", "结果不确定，需要人工确认", result)
        else:
            return VerificationResult(False, "failed",
                                      f"执行失败: {result.get('error', 'unknown')}", result)

    @staticmethod
    def verify_skill_output(output: Dict[str, Any], schema: Dict[str, Any]) -> VerificationResult:
        required = schema.get("required", [])
        missing = [f for f in required if f not in output]
        if missing:
            return VerificationResult(False, "failed", f"缺少必需字段: {missing}",
                                      {"missing": missing})
        return VerificationResult(True, "success", "输出符合预期", output)


# ================================================================
# 2. AuditWriter — 审计日志
# ================================================================

class AuditWriter:
    """审计写入器 — 结构化的步骤级审计"""

    def __init__(self, storage_path: str = ""):
        os.makedirs(HOOK_DIR, exist_ok=True)
        self.storage_path = storage_path or os.path.join(HOOK_DIR, "closed_loop_audit.jsonl")

    def write(self, event: Dict[str, Any]):
        event["timestamp"] = datetime.now(BEIJING_TZ).isoformat()
        with open(self.storage_path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def write_execution_start(self, goal: str, plan: Dict[str, Any]):
        self.write({"event": "execution_start", "goal": goal, "plan": plan})

    def write_step_start(self, step_id: int, capability: str, params: Dict[str, Any]):
        self.write({"event": "step_start", "step_id": step_id, "capability": capability, "params": params})

    def write_step_complete(self, step_id: int, result: Dict[str, Any]):
        self.write({"event": "step_complete", "step_id": step_id, "result": result})

    def write_step_failed(self, step_id: int, error: str):
        self.write({"event": "step_failed", "step_id": step_id, "error": error})

    def write_execution_complete(self, goal: str, success: bool, summary: str):
        self.write({"event": "execution_complete", "goal": goal, "success": success, "summary": summary})

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not os.path.exists(self.storage_path):
            return []
        events = []
        with open(self.storage_path, "r") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events[-limit:]


# ═══════════════════════════════════════════
# 3a. 错误分类
# ═══════════════════════════════════════════

class ErrorCategory(str, Enum):
    """错误分类 — 区分可恢复与不可恢复错误"""
    TRANSIENT = "transient"         # 临时故障（网络超时、断连）→ RETRY + 指数退避
    CONFIG = "config"                # 配置错误（缺少配置、格式错误）→ ABORT + 审计
    AUTH = "auth"                    # 鉴权/权限错误 → ASK_USER
    DATA = "data"                    # 数据错误（格式异常、校验失败）→ SKIP + 详记
    RESOURCE = "resource"            # 资源不足（内存、磁盘）→ 降级 + 告警
    NOT_FOUND = "not_found"          # 能力/资源不存在 → FALLBACK/SKIP
    UNKNOWN = "unknown"              # 未知错误 → ASK_USER


@dataclass
class ErrorClassification:
    """错误分类结果"""
    category: ErrorCategory
    confidence: float           # 0.0 ~ 1.0
    matched_pattern: str = ""
    detail: str = ""


class ErrorClassifier:
    """
    错误分类器 — 将错误文本按类型分类。
    
    使用关键词+正则匹配模式，支持自定义分类规则。
    """

    # 分类模式：每个类别的关键词/正则列表
    PATTERNS: Dict[ErrorCategory, List[str]] = {
        ErrorCategory.TRANSIENT: [
            "network", "timeout", "connection", "refused", "unreachable",
            "reset", "broken pipe", "econnreset", "econnrefused",
            "temporarily unavailable", "too many requests", "429",
            "rate limit", "retry later", "transient",
        ],
        ErrorCategory.CONFIG: [
            "configuration", "config", "misconfigured",
            "invalid setting", "env not set", "missing config",
            "schema", "invalid configuration",
        ],
        ErrorCategory.AUTH: [
            "permission", "auth", "unauthorized", "forbidden", "403",
            "401", "access denied", "not authorized", "login",
            "credential", "token expired", "api key",
        ],
        ErrorCategory.DATA: [
            "format error", "parse error", "validation", "schema error",
            "malformed", "corrupt", "unexpected data", "type error",
            "keyerror", "indexerror", "attributeerror",
        ],
        ErrorCategory.RESOURCE: [
            "memory", "disk", "quota", "exhausted", "no space",
            "oom", "too many open files", "resource temporarily",
        ],
        ErrorCategory.NOT_FOUND: [
            "not found", "no such", "does not exist", "unavailable",
            "not supported", "not implemented", "module not",
        ],
    }

    def classify(self, error: str) -> ErrorClassification:
        """
        对错误文本进行分类。

        Args:
            error: 错误描述文本

        Returns:
            ErrorClassification: 分类结果（含置信度）
        """
        el = error.lower()

        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if pattern in el:
                    # 命中模式数越多，置信度越高
                    match_count = sum(1 for p in patterns if p in el)
                    confidence = min(0.5 + match_count * 0.15, 1.0)
                    return ErrorClassification(
                        category=category,
                        confidence=confidence,
                        matched_pattern=pattern,
                        detail=error[:200],
                    )

        return ErrorClassification(
            category=ErrorCategory.UNKNOWN,
            confidence=0.3,
            detail=error[:200],
        )


# ═══════════════════════════════════════════
# 3b. 指数退避重试
# ═══════════════════════════════════════════

class ExponentialBackoff:
    """
    指数退避重试器 — 标准指数退避 + 随机抖动。

    公式：delay = min(base * (2 ** attempt) + jitter, max_delay)

    用法：
        backoff = ExponentialBackoff(base=1.0, max_delay=30.0)
        for delay in backoff(3):  # 最多重试3次
            try:
                result = call()
                break
            except TransientError:
                time.sleep(delay)  # 等待后继续重试
    """

    def __init__(
        self,
        base: float = 1.0,
        max_delay: float = 30.0,
        jitter_factor: float = 0.1,
    ):
        """
        Args:
            base: 基础延迟（秒），第1次重试间隔
            max_delay: 最大延迟（秒）
            jitter_factor: 抖动系数（相对于当前延迟的比例）
        """
        self.base = base
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor

    def get_delay(self, attempt: int) -> float:
        """
        计算第 attempt 次重试的等待时间。

        Args:
            attempt: 重试次数（0开始，第1次重试=0）

        Returns:
            等待时间（秒）
        """
        delay = min(self.base * (2 ** attempt), self.max_delay)
        # 加入随机抖动，防止惊群效应
        jitter = random.uniform(0, delay * self.jitter_factor)
        return round(delay + jitter, 3)

    def __call__(self, max_attempts: int = 3) -> List[float]:
        """返回每次重试的延迟时间列表"""
        return [self.get_delay(i) for i in range(max_attempts)]

    def sleep(self, attempt: int):
        """阻塞等待（非异步环境用）"""
        import time
        delay = self.get_delay(attempt)
        time.sleep(delay)
        return delay

    async def asleep(self, attempt: int) -> float:
        """异步等待"""
        import asyncio
        delay = self.get_delay(attempt)
        await asyncio.sleep(delay)
        return delay


# ═══════════════════════════════════════════
# 3c. 熔断器集成
# ═══════════════════════════════════════════

def _ensure_circuit_breaker():
    """惰性导入熔断器，避免循环依赖"""
    try:
        from circuit_breaker import CircuitBreakerRegistry, CircuitBreakerConfig
        return CircuitBreakerRegistry, CircuitBreakerConfig
    except ImportError:
        return None, None


# ═══════════════════════════════════════════
# 3d. RecoveryManager — 升级版
# ═══════════════════════════════════════════

class RecoveryStrategy(Enum):
    RETRY = "retry"           # 重试（带指数退避）
    FALLBACK = "fallback"      # 降级到备用能力
    SKIP = "skip"              # 跳过当前步骤
    ABORT = "abort"            # 终止整个任务
    ASK_USER = "ask_user"      # 询问用户


@dataclass
class RecoveryDecision:
    strategy: RecoveryStrategy
    reason: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    max_retries: int = 1
    retry_delays: List[float] = None  # 每次重试的延迟（秒）
    fallback_capability: Optional[str] = None
    user_message: Optional[str] = None
    circuit_breaker_name: str = ""     # 关联的熔断器名称
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "reason": self.reason,
            "category": self.category.value,
            "max_retries": self.max_retries,
            "retry_delays": self.retry_delays,
            "fallback_capability": self.fallback_capability,
            "circuit_breaker_name": self.circuit_breaker_name,
            "detail": self.detail[:200],
        }


class RecoveryManager:
    """
    恢复管理器 v2.0 — 错误分类 + 指数退避 + 熔断器集成。

    升级内容：
    1. 错误分类器替代简单关键词匹配
    2. 可恢复错误 → RETRY + 指数退避 + 抖动
    3. 熔断器集成 — 重试前检查熔断状态
    4. 默认配置参数化
    """

    # 各类别的默认重试配置
    DEFAULT_CONFIGS: Dict[ErrorCategory, Dict] = {
        ErrorCategory.TRANSIENT: {
            "strategy": RecoveryStrategy.RETRY,
            "max_retries": 3,
            "backoff_base": 1.0,
            "backoff_max": 30.0,
            "reason": "临时故障，自动重试（指数退避）",
        },
        ErrorCategory.CONFIG: {
            "strategy": RecoveryStrategy.ABORT,
            "reason": "配置错误，终止执行，请修复配置后重试",
        },
        ErrorCategory.AUTH: {
            "strategy": RecoveryStrategy.ASK_USER,
            "reason": "鉴权/权限错误，询问用户",
        },
        ErrorCategory.DATA: {
            "strategy": RecoveryStrategy.SKIP,
            "reason": "数据格式错误，跳过并记录详细信息",
        },
        ErrorCategory.RESOURCE: {
            "strategy": RecoveryStrategy.ABORT,
            "reason": "资源不足，终止执行并告警",
        },
        ErrorCategory.NOT_FOUND: {
            "strategy": RecoveryStrategy.SKIP,
            "reason": "能力或资源不存在，跳过",
        },
        ErrorCategory.UNKNOWN: {
            "strategy": RecoveryStrategy.ASK_USER,
            "reason": "未知错误，询问用户处理方式",
        },
    }

    def __init__(self, classifier: Optional[ErrorClassifier] = None):
        self.classifier = classifier or ErrorClassifier()
        self.backoff_by_category: Dict[ErrorCategory, ExponentialBackoff] = {
            ErrorCategory.TRANSIENT: ExponentialBackoff(base=1.0, max_delay=30.0),
        }

    def decide(self, error: str, context: Optional[Dict[str, Any]] = None) -> RecoveryDecision:
        """
        根据错误类型和上下文，自动决策恢复策略。

        Args:
            error: 错误描述文本
            context: 执行上下文（可含 fallback_capability, circuit_breaker, 等）

        Returns:
            RecoveryDecision
        """
        ctx = context or {}

        # 1. 错误分类
        classification = self.classifier.classify(error)
        config = self.DEFAULT_CONFIGS.get(classification.category, self.DEFAULT_CONFIGS[ErrorCategory.UNKNOWN])

        strategy = config["strategy"]
        reason = config["reason"]
        max_retries = config.get("max_retries", 1)

        # 2. 重试延迟（指数退避）
        retry_delays = []
        if strategy == RecoveryStrategy.RETRY:
            backoff = self.backoff_by_category.get(
                classification.category,
                ExponentialBackoff(base=1.0, max_delay=30.0),
            )
            retry_delays = backoff(max_retries)

        # 3. 熔断器检查（如果提供了熔断器名称，检查是否在熔断中）
        circuit_breaker_name = ctx.get("circuit_breaker", "")
        if circuit_breaker_name:
            CircuitBreakerRegistry, _ = _ensure_circuit_breaker()
            if CircuitBreakerRegistry:
                cb = CircuitBreakerRegistry.get_instance().get(circuit_breaker_name)
                if cb and cb.is_open:
                    # 熔断中 → 降级策略
                    strategy = RecoveryStrategy.FALLBACK
                    reason = f"{circuit_breaker_name} 熔断中，直接降级"
                    retry_delays = []

        # 4. 上下文修正：如果提供了 fallback，NOT_FOUND → FALLBACK
        fallback = ctx.get("fallback_capability")
        if classification.category == ErrorCategory.NOT_FOUND and fallback:
            strategy = RecoveryStrategy.FALLBACK
            reason = f"使用备用能力: {fallback}"

        # 5. 严重错误关键词兜底匹配（兼容旧版 ABORT 行为）
        severe_keywords = ["fatal", "critical", "panic", "irrecoverable"]
        for kw in severe_keywords:
            if kw in error.lower() and strategy != RecoveryStrategy.RETRY:
                strategy = RecoveryStrategy.ABORT
                reason = f"严重错误({kw})，终止执行"
                retry_delays = []
                break

        # 6. 用户消息生成
        user_message = None
        if strategy == RecoveryStrategy.ASK_USER:
            user_message = ctx.get(
                "ask_message",
                f"执行出错: {error[:100]}，怎么处理？",
            )

        return RecoveryDecision(
            strategy=strategy,
            reason=reason,
            category=classification.category,
            max_retries=max_retries,
            retry_delays=retry_delays,
            fallback_capability=fallback if strategy == RecoveryStrategy.FALLBACK else None,
            user_message=user_message,
            circuit_breaker_name=circuit_breaker_name,
            detail=f"分类={classification.category.value}({classification.confidence:.0%}), 匹配={classification.matched_pattern}",
        )

    def execute_recovery(self, decision: RecoveryDecision, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        将决策转换为可执行的动作配置。

        返回包含重试延迟、降级目标等详细信息的动作字典。
        """
        ctx = context or {}

        action_map = {
            RecoveryStrategy.RETRY: {
                "action": "retry",
                "max_retries": decision.max_retries,
                "retry_delays": decision.retry_delays,
            },
            RecoveryStrategy.FALLBACK: {
                "action": "fallback",
                "capability": decision.fallback_capability or ctx.get("fallback_capability"),
                "message": decision.reason,
            },
            RecoveryStrategy.SKIP: {
                "action": "skip",
                "message": decision.reason,
                "detail": decision.detail,
            },
            RecoveryStrategy.ABORT: {
                "action": "abort",
                "message": decision.reason,
                "detail": decision.detail,
            },
            RecoveryStrategy.ASK_USER: {
                "action": "ask_user",
                "message": decision.user_message or decision.reason,
            },
        }

        return action_map.get(decision.strategy, {"action": "unknown", "message": decision.reason})

    def calculate_next_retry_delay(self, attempt: int, category: ErrorCategory = ErrorCategory.TRANSIENT) -> float:
        """
        计算下一次重试的等待时间（可在循环中独立调用）。

        Args:
            attempt: 当前重试次数（0开始）
            category: 错误类型，影响默认退避配置

        Returns:
            本次重试前的等待时间（秒）
        """
        backoff = self.backoff_by_category.get(
            category,
            ExponentialBackoff(base=1.0, max_delay=30.0),
        )
        return backoff.get_delay(attempt)


# ================================================================
# 4. FinalSummarizer — 执行总结
# ================================================================

@dataclass
class ExecutionSummary:
    goal: str
    success: bool
    total_steps: int
    completed_steps: int
    failed_steps: int
    elapsed_seconds: int
    message: str
    recommendations: List[str]


class FinalSummarizer:
    """最终总结器 — 生成可读的执行报告"""

    def summarize(self, goal: str, steps: List[Dict[str, Any]],
                  start_time: str, end_time: str) -> ExecutionSummary:
        total = len(steps)
        completed = sum(1 for s in steps if s.get("status") == "completed")
        failed = sum(1 for s in steps if s.get("status") == "failed")
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            elapsed = int((end_dt - start_dt).total_seconds())
        except Exception:
            logging.exception("[closed_loop.py] suppressed")
            elapsed = 0

        success = failed == 0 and completed == total
        if success:
            message = f"✅ 任务完成！共执行 {total} 个步骤，耗时 {elapsed} 秒。"
        elif failed > 0:
            message = f"⚠️ 部分完成。成功 {completed}/{total}，失败 {failed}。"
        else:
            message = f"❌ 任务失败。"

        return ExecutionSummary(goal=goal, success=success, total_steps=total,
                                completed_steps=completed, failed_steps=failed,
                                elapsed_seconds=elapsed, message=message,
                                recommendations=self._gen_recommendations(steps, success))

    def _gen_recommendations(self, steps: List[Dict[str, Any]], success: bool) -> List[str]:
        recs = []
        if not success:
            for s in steps:
                if s.get("status") == "failed":
                    recs.append(f"步骤 {s.get('step_id')} 失败: {s.get('error', '未知')}")
        high_risk = [s for s in steps if s.get("risk_level") in ("L3", "L4")]
        if high_risk:
            recs.append("本次执行包含高风险操作，建议复核结果")
        return recs

    def format_for_user(self, summary: ExecutionSummary) -> str:
        lines = [summary.message, "", f"目标: {summary.goal}",
                 f"步骤: {summary.completed_steps}/{summary.total_steps} 完成",
                 f"耗时: {summary.elapsed_seconds} 秒"]
        if summary.recommendations:
            lines.append("")
            lines.append("建议:")
            for r in summary.recommendations:
                lines.append(f"  • {r}")
        return "\n".join(lines)


# ================================================================
# 5. 统一入口 — 与自进化引擎的集成点
# ================================================================

class ClosedLoopEngine:
    """闭环验证器统一入口 — 供 self_evolution.reflect() 后调用"""

    def __init__(self):
        self.checker = ResultChecker()
        self.audit = AuditWriter()
        self.recovery = RecoveryManager()
        self.summarizer = FinalSummarizer()
        self._judge = None

    def _get_judge(self):
        if self._judge is None:
            try:
                from judge_engine import JudgeEngine
                self._judge = JudgeEngine()
            except ImportError:
                self._judge = None
        return self._judge

    def run_verification_loop(self, goal: str, steps: List[Dict[str, Any]],
                              start_time: str, end_time: str, query: str = "", response: str = "") -> ExecutionSummary:
        """完整的验证→审计→摘要→自评分闭环"""
        # 1. 审计开始
        self.audit.write_execution_start(goal, {"step_count": len(steps)})

        # 2. 验证每步结果
        for step in steps:
            step_id = step.get("step_id", 0)
            step_result = step.get("result", {})
            verification = self.checker.verify_platform_result(step_result)
            if verification.status == "failed":
                self.audit.write_step_failed(step_id, step_result.get("error", "unknown"))
                recovery_decision = self.recovery.decide(
                    step_result.get("error", ""), step)
                step["recovery"] = {
                    "decision": recovery_decision.strategy.value,
                    "reason": recovery_decision.reason,
                }

        # 3. 自评分（新增：回答后异步旁路评分）
        judge = self._get_judge()
        if judge and query and response:
            try:
                scores = judge.score(query, response)
                # 排除LLM失败时的fallback高分(全8分)：有分数且非全8才写verified
                if scores and isinstance(scores, (list, tuple)) and not all(isinstance(s, (int, float)) and s >= 7.9 for s in scores):
                    judge.store_verified(query, response, scores)
            except Exception:
                pass  # 不阻塞主流程

        # 4. 生成摘要
        summary = self.summarizer.summarize(goal, steps, start_time, end_time)
        self.audit.write_execution_complete(goal, summary.success, summary.message)
        return summary

    def quick_verify(self, result: Dict[str, Any]) -> VerificationResult:
        """快速单步验证"""
        return self.checker.verify_platform_result(result)
