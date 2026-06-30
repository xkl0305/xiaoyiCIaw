"""AutonomyCycle (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import asdict

from ._common import new_id, now_ts, STATE_DIR
from .json_store import JsonStore
from .constitution_kernel import ConstitutionKernel
from .capability_gap_analyzer import CapabilityGapAnalyzer
from .capability_gap_status import CapabilityGapStatus
from .quality_evaluator import QualityEvaluator
from .strategy_evolver import StrategyEvolver
from .recovery_ledger import RecoveryLedger
from .continuous_task_runner import ContinuousTaskRunner
from .autonomy_cycle_result import AutonomyCycleResult

class AutonomyCycle:
    """7阶段自治周期编排 — 升级自 Orchestrator（原 AutoBrainRouter）"""

    def __init__(self):
        self.constitution = ConstitutionKernel()
        self.gap = CapabilityGapAnalyzer()
        self.quality = QualityEvaluator()
        self.strategy = StrategyEvolver()
        self.recovery = RecoveryLedger()
        self.tasks = ContinuousTaskRunner()
        self._event_store = JsonStore(os.path.join(STATE_DIR, "trace_events.json"))

    def _trace(self, run_id: str, event_type: str, message: str, payload: Dict = None):
        self._event_store.append({
            "id": new_id("trace"),
            "run_id": run_id,
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
            "created_at": now_ts(),
        })

    def _trace_count(self, run_id: str) -> int:
        return sum(1 for x in self._event_store.read() if x.get("run_id") == run_id)

    def _estimate_risk(self, goal: str, required: List[str]) -> str:
        if any(x in goal for x in ["转账", "支付", "删除", "发送邮件",
                                     "发给客户", "安装未知", "隐私导出"]):
            return "L4"
        if any(x in required for x in ["external_action", "connector_management"]):
            return "L3"
        if any(x in goal for x in ["修改", "覆盖", "执行命令", "写入"]):
            return "L2"
        return "L1"

    def run_cycle(self, goal: str, context: Dict = None) -> AutonomyCycleResult:
        """执行完整7阶段自治周期"""
        context = context or {}
        run_id = new_id("cycle")

        # Phase 1: Constitution 评估
        self._trace(run_id, "phase_1_constitution", "规则引擎评估", {"goal": goal[:100]})
        decision = self.constitution.evaluate(goal)

        # Phase 2: Capability Gap 分析
        self._trace(run_id, "phase_2_gap", "能力差距分析", {})
        gap = self.gap.analyze(goal)

        # Phase 3: Risk 判定
        risk = self._estimate_risk(goal, gap.required_capabilities)
        self._trace(run_id, "phase_3_risk", f"风险等级: {risk}", {"risk": risk})

        # Phase 4: Recovery 检查点
        self._trace(run_id, "phase_4_checkpoint", "记录检查点", {})
        self.recovery.record_checkpoint(
            run_id=run_id,
            action=f"autonomy_cycle::{goal[:60]}",
            checkpoint={
                "goal": goal[:200],
                "constitution": decision.status,
                "required_caps": gap.required_capabilities,
                "missing": gap.missing_capabilities,
                "risk": risk,
            },
            rollback_plan="restore before autonomy cycle; discard unapproved actions",
            reversible=decision.status == "allow",
        )

        # Phase 5: Quality 评估
        blocked = decision.status in ("block", "approval_required")
        result_payload = {
            "has_plan": True,
            "has_next_action": True,
            "actionable": not blocked,
            "steps": 7,
            "gap_status": gap.status.value,
        }
        q = self.quality.evaluate(run_id, goal[:100], result_payload, risk_blocked=blocked)
        self._trace(run_id, "phase_5_quality", f"质量: {q.final_score}", {"score": q.final_score, "passed": q.passed})

        # Phase 6: Strategy 演进
        changed = self.strategy.evolve_from_quality(q)
        self._trace(run_id, "phase_6_strategy", f"策略更新: {len(changed)} 条", {})

        # Phase 7: 结果汇总
        recovery_count = len(self.recovery.list_run(run_id))
        trace_count = self._trace_count(run_id)

        if decision.status == "block":
            status = "blocked"
            next_action = "操作被规则阻止，建议修改目标"
        elif decision.status == "approval_required":
            status = "waiting_approval"
            next_action = "需要人工审批后才能继续"
        elif gap.status == CapabilityGapStatus.NEED_EXTENSION:
            status = "need_extension"
            next_action = f"缺少能力: {', '.join(gap.missing_capabilities)}，建议安装对应技能"
        elif q.passed:
            status = "ready"
            next_action = "可进入执行阶段"
        else:
            status = "partial"
            next_action = "质量评分不足，建议调整后重试"

        return AutonomyCycleResult(
            run_id=run_id,
            goal=goal[:200],
            status=status,
            constitution_decision=asdict(decision),
            capability_gap=asdict(gap),
            quality_score=q.final_score,
            trace_events=trace_count,
            next_action=next_action,
            recovery_entries=recovery_count,
            strategy_updates=len(changed),
            details={
                "risk_level": risk,
                "quality_issues": q.issues,
                "strategy_updates": [r.name for r in changed],
                "recovery_count": recovery_count,
            },
        )


_DEFAULT: Optional[AutonomyCycle] = None


def get_cycle() -> AutonomyCycle:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AutonomyCycle()
    return _DEFAULT
