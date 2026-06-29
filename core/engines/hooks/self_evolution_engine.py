"""
Crusheart Agent OS — SelfEvolutionEngine v5 · Unified
自进化引擎 v5：合并 v3+v4+tracker+MASA+xiaoyi-skill 规则 + PatternMiner + SkillGenerator

版本描述: Unified SelfEvolutionEngine v5 — Crusheart v7.0.0

合并来源:
  - self_evolution_engine.py (v4) → 意图合约 / 预算 / 隐私 / 模拟 / 漂移 / 提案 / 可观测
  - self_evolution_v3.py (v3)    → 反射 / 路由 / 效果追踪 / MASA / 隐式偏好 / 参数调优
  - evolution_tracker.py          → RegisteredRule / RuleStore
  - masa_engine.py                → MASAPredictor / MASAAliener
  - xiaoyi-self-evolution SKILL   → should_run_evaluate_turn / ConflictDetector / QualityGate / TargetFileMapper
  新增模块: PatternMiner, SkillGenerator
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
import glob
import math
import shutil
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)

_BEIJING = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

def _now() -> str:
    dt = datetime.now()
    if _BEIJING:
        dt = dt.astimezone(_BEIJING)
    return dt.isoformat()

def _utc_now() -> float:
    return time.time()

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

# ============================================================
# 枚举
# ============================================================

class ContractStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSAFE = "unsafe"

class BudgetStatus(str, Enum):
    WITHIN_BUDGET = "within_budget"
    NEEDS_DOWNGRADE = "needs_downgrade"
    BLOCKED_OVER_BUDGET = "blocked_over_budget"

class PrivacyLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"

class CircuitStatus(str, Enum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"

class SimulationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

class DriftStatus(str, Enum):
    STABLE = "stable"
    WATCH = "watch"
    DRIFTING = "drifting"

class ImprovementStatus(str, Enum):
    PROPOSED = "proposed"
    SAFE_TO_APPLY = "safe_to_apply"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class DifficultyLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

class BiasPattern(str, Enum):
    CONSISTENT = "consistent"
    OVERESTIMATE_DIFFICULTY = "overestimate_difficulty"
    UNDERESTIMATE_DIFFICULTY = "underestimate_difficulty"
    OVERCONFIDENCE = "overconfidence"
    UNDERCONFIDENCE = "underconfidence"
    TIME_OVERESTIMATE = "time_overestimate"
    TIME_UNDERESTIMATE = "time_underestimate"

# ============================================================
# RegisteredRule + RuleStore（自 evolution_tracker.py）
# ============================================================

class RegisteredRule:
    def __init__(self, rule_id: str, content: str, source: str,
                 category: str, tags: list = None):
        self.id = rule_id
        self.content = content
        self.source = source
        self.category = category
        self.tags = tags or []
        self.registered_at = datetime.now(_BEIJING).isoformat()
        self.total_hits = 0
        self.violations = 0
        self.last_hit_at = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict):
        r = cls(d["id"], d["content"], d["source"], d["category"], d.get("tags", []))
        r.registered_at = d.get("registered_at", r.registered_at)
        r.total_hits = d.get("total_hits", 0)
        r.violations = d.get("violations", 0)
        r.last_hit_at = d.get("last_hit_at")
        return r

    def record_hit(self):
        self.total_hits += 1
        self.last_hit_at = datetime.now(_BEIJING).isoformat()

    def record_violation(self):
        self.violations += 1
        self.last_hit_at = datetime.now(_BEIJING).isoformat()

TRACKER_DIR = os.path.join(WORKSPACE, ".evolution_tracker")
RULES_FILE = os.path.join(TRACKER_DIR, "registered_rules.json")
HIT_LOG_FILE = os.path.join(TRACKER_DIR, "hit_log.jsonl")

class RuleStore:
    def __init__(self):
        os.makedirs(TRACKER_DIR, exist_ok=True)
        self._rules: Dict[str, RegisteredRule] = {}
        self._load()

    def _load(self):
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "r") as f:
                data = json.load(f)
                for r_data in data.get("rules", []):
                    rule = RegisteredRule.from_dict(r_data)
                    self._rules[rule.id] = rule

    def _save(self):
        os.makedirs(TRACKER_DIR, exist_ok=True)
        with open(RULES_FILE, "w") as f:
            json.dump({"rules": [r.to_dict() for r in self._rules.values()]},
                      f, ensure_ascii=False, indent=2)

    def check_rules(self, context: str) -> List[RegisteredRule]:
        context_lower = context.lower()
        matched = []
        for rule in self._rules.values():
            keywords = []
            for m in re.finditer(r'(?:必须|禁止|不得|不能|需要|应该|建议)\s*(\S+)', rule.content):
                keywords.append(m.group(1))
            for m in re.finditer(r'(\S+?)(?:前|后|时|之前|之后|之时)', rule.content):
                keywords.append(m.group(1))
            for kw in keywords:
                if len(kw) > 1 and kw.lower() in context_lower:
                    matched.append(rule)
                    break
        return matched

    def register(self, rule: RegisteredRule):
        self._rules[rule.id] = rule
        self._save()

    def get(self, rule_id: str) -> Optional[RegisteredRule]:
        return self._rules.get(rule_id)

    def list_all(self) -> List[RegisteredRule]:
        return list(self._rules.values())

    def record_hit(self, rule_id: str):
        rule = self._rules.get(rule_id)
        if rule:
            rule.record_hit()
            self._save()

    def record_violation(self, rule_id: str):
        rule = self._rules.get(rule_id)
        if rule:
            rule.record_violation()
            self._save()

# ============================================================
# MASAPredictor + MASAAliener（自 masa_engine.py）
# ============================================================

class MASAPredictor:
    DIFFICULTY_BASE_TIME = {
        DifficultyLevel.L1: 5,
        DifficultyLevel.L2: 15,
        DifficultyLevel.L3: 45,
        DifficultyLevel.L4: 120,
    }

    def predict(self, task_context: dict) -> dict:
        text = task_context.get("text", "")
        tool_count = task_context.get("tool_count", 0)
        text_length = task_context.get("text_length", len(text))
        has_uncertainty = task_context.get("has_uncertainty", False)
        is_complex = task_context.get("is_complex", False)
        requires_judgment = task_context.get("requires_judgment", False)
        score = 0.0
        factors = []
        if tool_count >= 5: score += 35; factors.append("多工具(>=5)")
        elif tool_count >= 3: score += 20; factors.append("多工具(>=3)")
        elif tool_count >= 1: score += 5
        if text_length > 500: score += 15; factors.append("长文本(>500字)")
        elif text_length > 200: score += 8
        if is_complex: score += 20; factors.append("标记为复杂")
        if requires_judgment: score += 15; factors.append("需要判断")
        if has_uncertainty: score += 15; factors.append("存在不确定性")
        complexity_signals = ["为什么", "如何", "对比", "分析", "评估", "判断",
                              "综合", "所有", "全部", "每个", "逐一"]
        signal_count = sum(1 for s in complexity_signals if s in text)
        if signal_count >= 3:
            score += signal_count * 5
            factors.append(f"复杂查询信号x{signal_count}")
        if score >= 70: difficulty = DifficultyLevel.L4
        elif score >= 40: difficulty = DifficultyLevel.L3
        elif score >= 15: difficulty = DifficultyLevel.L2
        else: difficulty = DifficultyLevel.L1
        base_time = self.DIFFICULTY_BASE_TIME[difficulty]
        extra_time = tool_count * 5 + text_length // 100 * 2
        time_cost = base_time + extra_time
        confidence_factors = [not has_uncertainty, not requires_judgment,
                              tool_count > 0, text_length > 20, not is_complex]
        confidence = sum(0.2 for f in confidence_factors if f)
        confidence = max(0.3, min(0.95, confidence))
        return {
            "difficulty": difficulty.value,
            "time_cost_s": time_cost,
            "confidence": round(confidence, 2),
            "key_factors": factors[:8],
            "difficulty_score": round(score, 1),
        }

class MASAAliener:
    _BIAS_LABELS = {
        BiasPattern.CONSISTENT: "预判与执行一致",
        BiasPattern.OVERESTIMATE_DIFFICULTY: "预判难度偏高",
        BiasPattern.UNDERESTIMATE_DIFFICULTY: "预判难度偏低",
        BiasPattern.OVERCONFIDENCE: "预判过于自信",
        BiasPattern.UNDERCONFIDENCE: "预判信心不足",
        BiasPattern.TIME_OVERESTIMATE: "时间预估偏长",
        BiasPattern.TIME_UNDERESTIMATE: "时间预估偏短",
    }

    def align(self, prediction: dict, actual: dict) -> dict:
        if not prediction or not actual:
            return self._empty("缺少预判或实际数据")
        level_map = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
        pred_level = level_map.get(prediction.get("difficulty", "L2"), 2)
        actual_level = level_map.get(actual.get("difficulty", "L2"), 2)
        diff_diff = actual_level - pred_level
        difficulty_match = diff_diff == 0
        pred_time = prediction.get("time_cost_s", 30)
        actual_time = actual.get("time_cost_s", pred_time)
        time_error = actual_time - pred_time
        time_error_rate = (time_error / max(pred_time, 1)) * 100
        predicted_conf = prediction.get("confidence", 0.5)
        success = actual.get("success", False)
        error_present = bool(actual.get("error", ""))
        if diff_diff > 0:
            if predicted_conf > 0.7 and not success:
                bias = BiasPattern.OVERCONFIDENCE
            else:
                bias = BiasPattern.UNDERESTIMATE_DIFFICULTY
        elif diff_diff < 0:
            bias = BiasPattern.OVERESTIMATE_DIFFICULTY
        elif abs(time_error_rate) > 100 and time_error > 0:
            bias = BiasPattern.TIME_UNDERESTIMATE
        elif abs(time_error_rate) > 100 and time_error < 0:
            bias = BiasPattern.TIME_OVERESTIMATE
        elif predicted_conf < 0.4 and success:
            bias = BiasPattern.UNDERCONFIDENCE
        else:
            bias = BiasPattern.CONSISTENT
        alignment_score = 1.0
        if not difficulty_match: alignment_score -= 0.3 * abs(diff_diff)
        if abs(time_error_rate) > 50: alignment_score -= 0.15
        if abs(time_error_rate) > 200: alignment_score -= 0.15
        if not success: alignment_score -= 0.2
        if error_present: alignment_score -= 0.1
        alignment_score = max(0.0, min(1.0, alignment_score))
        return {
            "alignment_score": round(alignment_score, 2),
            "difficulty_match": difficulty_match,
            "difficulty_diff": diff_diff,
            "time_error_s": time_error,
            "time_error_rate": round(time_error_rate, 1),
            "confidence_calibration": round(predicted_conf * (0.8 if not difficulty_match else 1.0), 2),
            "bias_pattern": bias.value,
            "bias_label": self._BIAS_LABELS.get(bias, "未知"),
            "confidence_overestimated": predicted_conf >= 0.7 and (not success or not difficulty_match),
            "details": {"pred_level": prediction.get("difficulty"), "actual_level": actual.get("difficulty"),
                        "pred_time": pred_time, "actual_time": actual_time,
                        "pred_confidence": predicted_conf, "success": success, "has_error": error_present},
        }

    def _empty(self, reason: str) -> dict:
        return {"alignment_score": 0.0, "difficulty_match": False, "difficulty_diff": 0,
                "time_error_s": 0, "time_error_rate": 0.0, "confidence_calibration": 0.0,
                "bias_pattern": "no_data", "bias_label": reason,
                "confidence_overestimated": False, "details": {"error": reason}}

# ============================================================
# 数据结构 (Dataclasses)
# ============================================================

@dataclass
class IntentContract:
    id: str
    goal: str
    objective: str
    acceptance_criteria: List[str]
    constraints: List[str]
    non_goals: List[str]
    risk_notes: List[str]
    status: ContractStatus
    created_at: float = field(default_factory=_utc_now)

@dataclass
class BudgetDecision:
    id: str
    task_type: str
    token_budget: int
    cost_budget: float
    time_budget_seconds: int
    status: BudgetStatus
    recommended_model_group: str
    reason: str

@dataclass
class RedactionReport:
    id: str
    privacy_level: PrivacyLevel
    original_length: int
    redacted_length: int
    replacements: Dict[str, int]
    safe_text: str

@dataclass
class SimulationResult:
    id: str
    scenario: str
    status: SimulationStatus
    score: float
    failures: List[str]
    recommendations: List[str]

@dataclass
class DriftReport:
    id: str
    status: DriftStatus
    drift_score: float
    changed_preferences: List[str]
    suggest_actions: List[str]

@dataclass
class ReliabilityDecision:
    tool_name: str
    circuit_status: CircuitStatus
    max_retries: int
    retry_allowed: bool
    fallback_tool: Optional[str] = None
    reason: str = ""

@dataclass
class FallbackPlan:
    id: str
    unavailable_capability: str
    fallback_mode: str
    steps: List[str]
    quality_expected: float
    needs_user_notice: bool

@dataclass
class ContextPack:
    id: str
    goal: str
    selected_context: List[Dict[str, Any]]
    omitted_context: List[str]
    confidence: float
    token_estimate: int
    created_at: float = field(default_factory=_utc_now)

@dataclass
class ObservabilityReport:
    id: str
    runs: int
    success_rate: float
    avg_quality: float
    budget_violations: int
    privacy_events: int
    open_circuits: int
    summary: str

@dataclass
class ImprovementPlan:
    id: str
    title: str
    status: ImprovementStatus
    target_modules: List[str]
    proposed_changes: List[str]
    expected_gain: float
    risk_level: str
    rollback_plan: str

@dataclass
class EnginePatchProposal:
    id: str
    title: str
    target_engine_path: str
    target_function: str
    patch_type: str
    patch_content: str
    reason: str
    expected_benefit: str
    rollback_method: str
    risk_level: str
    simulated_score: float
    status: str = "pending"

@dataclass
class EvolutionCycleResult:
    run_id: str
    goal: str
    contract_status: ContractStatus
    context_confidence: float
    budget_status: BudgetStatus
    privacy_level: PrivacyLevel
    reliability_status: CircuitStatus
    fallback_mode: str
    simulation_status: SimulationStatus
    drift_status: DriftStatus
    observability_summary: str
    improvement_status: ImprovementStatus
    final_status: str
    next_action: str
    details: Dict[str, Any] = field(default_factory=dict)
    engine_patches: List[EnginePatchProposal] = field(default_factory=list)
    evolved: bool = False
    precipitated: bool = False
    experience_count: int = 0

# ============================================================
# JSON 存储 (JsonStore)
# ============================================================

class JsonStore:
    def __init__(self, root: str = ".evolution_state/self_evolution"):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self._root / name

    def read(self, name: str, default: Any = None):
        path = self._path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def write(self, name: str, data: Any) -> None:
        path = self._path(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        self._root.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def append(self, name: str, item: Any) -> None:
        data = self.read(name, [])
        if not isinstance(data, list):
            data = []
        data.append(item)
        self.write(name, data)

# ============================================================
# v4 子模块: IntentContractCompiler / BudgetGovernor / PrivacyRedactor / SimulationLab
# ============================================================

class IntentContractCompiler:
    @staticmethod
    def compile(goal: str) -> IntentContract:
        constraints: List[str] = []
        risk_notes: List[str] = []
        non_goals: List[str] = ["不执行不可逆的外部操作（未经审批）"]
        if any(x in goal for x in ["直接", "一次性", "批量", "不要一点点"]):
            constraints.append("优先一次性完整交付，非增量修补")
        if any(x in goal for x in ["压缩包", "覆盖包", "命令"]):
            constraints.append("生成可直接应用的产物包+命令")
        high_risk = ["发送", "转账", "删除", "安装", "密钥", "token", "支付", "签署", "发布", "外发"]
        if any(x in goal for x in high_risk):
            risk_notes.append("包含高风险或敏感操作")
        if any(x in goal for x in ["不确定", "随便", "可能", "也许"]):
            status = ContractStatus.NEEDS_CLARIFICATION
        elif any(x in goal for x in ["导出密钥", "密码发给", "token 发到", "API_KEY", "api_key"]) \
                or ("密钥" in goal and "导出" in goal) \
                or (("发送" in goal or "发给" in goal) and any(k in goal for k in ["key", "token", "密钥", "密码"])):
            status = ContractStatus.UNSAFE
        else:
            status = ContractStatus.READY
        acceptance = ["目标已分解为可验证的交付项", "风险边界已明确", "结果有确定性的验证方式"]
        if "压缩包" in goal or "覆盖包" in goal:
            acceptance.append("产物包已生成并可应用")
        return IntentContract(id=_new_id("contract"), goal=goal, objective=goal.strip(),
                              acceptance_criteria=acceptance, constraints=constraints,
                              non_goals=non_goals, risk_notes=risk_notes, status=status)

class BudgetGovernor:
    @staticmethod
    def decide(task_type: str, complexity: str = "medium",
               cost_preference: str = "balanced") -> BudgetDecision:
        base_tokens = {"low": 3000, "medium": 9000, "high": 24000, "very_high": 64000}.get(complexity, 9000)
        base_cost = {"low": 0.03, "medium": 0.20, "high": 1.20, "very_high": 4.00}.get(complexity, 0.20)
        time_budget = {"low": 20, "medium": 60, "high": 180, "very_high": 420}.get(complexity, 60)
        if cost_preference == "low":
            token_budget = max(1500, int(base_tokens * 0.45))
            cost_budget = round(base_cost * 0.35, 4)
            model_group = "fast_low_cost"
            status = BudgetStatus.NEEDS_DOWNGRADE if complexity in {"high", "very_high"} else BudgetStatus.WITHIN_BUDGET
            reason = "低成本偏好"
        elif cost_preference == "quality":
            token_budget = int(base_tokens * 1.4)
            cost_budget = round(base_cost * 1.8, 4)
            model_group = "reasoning_high"
            status = BudgetStatus.WITHIN_BUDGET
            reason = "高质量偏好"
        else:
            token_budget = base_tokens
            cost_budget = base_cost
            model_group = "balanced"
            status = BudgetStatus.WITHIN_BUDGET
            reason = "均衡预算"
        if cost_budget > 5.0:
            status = BudgetStatus.BLOCKED_OVER_BUDGET
            reason = "预估成本超出硬上限"
        return BudgetDecision(id=_new_id("budget"), task_type=task_type,
                              token_budget=token_budget, cost_budget=cost_budget,
                              time_budget_seconds=time_budget, status=status,
                              recommended_model_group=model_group, reason=reason)

class PrivacyRedactor:
    """隐私脱敏器 — 自动检测 API key/手机号/邮箱/身份证/银行卡"""
    def __init__(self):
        import re
        self._patterns = [
            ("api_key", re.compile(r"(?i)(?:api[_-]?key|secret|token|auth)\s*[:=]\s*[A-Za-z0-9_\-]{12,}")),
            ("phone",   re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
            ("email",   re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")),
            ("id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
            ("bank_card", re.compile(r"(?<!\d)(?:62|60|58|56|55|54|53|52|51|50|49|48|47|46|45|44|43|42|41|40|39|38|37|36|35|34|33|32|31|30|9)\d{14,17}(?!\d)")),
        ]
    def redact(self, text: str) -> RedactionReport:
        safe = text
        replacements = {}
        for name, pat in self._patterns:
            safe, count = pat.subn(f"[REDACTED_{name.upper()}]", safe)
            if count:
                replacements[name] = count
        if "api_key" in replacements or "bank_card" in replacements:
            level = PrivacyLevel.SECRET
        elif "id_card" in replacements:
            level = PrivacyLevel.SECRET
        elif replacements:
            level = PrivacyLevel.SENSITIVE
        else:
            level = PrivacyLevel.PUBLIC
        return RedactionReport(id=_new_id("redact"), privacy_level=level,
                               original_length=len(text), redacted_length=len(safe),
                               replacements=replacements, safe_text=safe)

class SimulationLab:
    @staticmethod
    def simulate(scenario: str, planned_steps: List[str],
                 risk_flags: Optional[List[str]] = None) -> SimulationResult:
        risk_flags = risk_flags or []
        failures: List[str] = []
        recommendations: List[str] = []
        if not planned_steps:
            failures.append("empty_plan")
            recommendations.append("先在 WorkflowEngine 构建 DAG 任务图")
        high_risk_keywords = ["secret", "payment", "external_send", "发送", "支付", "外发", "删除"]
        has_high_risk = any(x in risk_flags or any(kw in scenario for kw in high_risk_keywords) for x in risk_flags)
        has_approval_gate = any("approval" in s.lower() or "审批" in s or "确认" in s for s in planned_steps)
        if has_high_risk and not has_approval_gate:
            failures.append("missing_approval_gate")
            recommendations.append("在外部/敏感操作前插入审批中断")
        if len(planned_steps) > 20:
            recommendations.append("将计划拆分为分段执行批次")
        if failures:
            status = SimulationStatus.FAIL; score = 0.35
        elif recommendations:
            status = SimulationStatus.WARN; score = 0.72
        else:
            status = SimulationStatus.PASS; score = 0.93
        return SimulationResult(id=_new_id("sim"), scenario=scenario, status=status,
                                score=score, failures=failures, recommendations=recommendations)

class ToolReliabilityManager:
    def __init__(self, store_root: str = ".evolution_state/self_evolution"):
        self._store = JsonStore(store_root)
    def record_result(self, tool_name: str, success: bool) -> None:
        data = self._store.read(f"tool_reliability_{tool_name}.json", {})
        if success: data["success"] = data.get("success", 0) + 1
        else: data["failure"] = data.get("failure", 0) + 1
        self._store.write(f"tool_reliability_{tool_name}.json", data)
    def decide(self, tool_name: str, fallback_tool: Optional[str] = None) -> ReliabilityDecision:
        data = self._store.read(f"tool_reliability_{tool_name}.json", {})
        success = int(data.get("success", 0))
        failure = int(data.get("failure", 0))
        if failure >= 5 and failure > success * 2:
            status = CircuitStatus.OPEN; max_retries = 0; retry_allowed = False
            reason = "工具熔断已打开（连续失败过多）"
        elif failure >= 2 and failure >= success:
            status = CircuitStatus.HALF_OPEN; max_retries = 1; retry_allowed = True
            reason = "工具不稳定，允许一次探针重试"
        else:
            status = CircuitStatus.CLOSED; max_retries = 2; retry_allowed = True
            reason = "工具状态健康"
        return ReliabilityDecision(tool_name=tool_name, circuit_status=status, max_retries=max_retries,
                                    retry_allowed=retry_allowed, fallback_tool=fallback_tool, reason=reason)

class LocalFallbackPlanner:
    @staticmethod
    def plan(unavailable_capability: str) -> FallbackPlan:
        uc = unavailable_capability.lower()
        if "web_search" in uc or "search" in uc:
            return FallbackPlan(id=_new_id("fallback"), unavailable_capability=uc,
                fallback_mode="degraded_static_knowledge",
                steps=["声明当前搜索不可用", "仅使用缓存/本地知识", "标记结果后续需验证"],
                quality_expected=0.55, needs_user_notice=True)
        elif "llm" in uc or "model" in uc or "推理" in uc:
            return FallbackPlan(id=_new_id("fallback"), unavailable_capability=uc,
                fallback_mode="local_rule_based",
                steps=["切换到确定性规则", "避免高风险执行", "将任务排队等待模型恢复"],
                quality_expected=0.45, needs_user_notice=True)
        elif "image" in uc or "video" in uc or "图片" in uc:
            return FallbackPlan(id=_new_id("fallback"), unavailable_capability=uc,
                fallback_mode="script_only",
                steps=["仅生成 Prompt/脚本描述", "不声称生成了媒体产物", "保存请求供后续执行"],
                quality_expected=0.50, needs_user_notice=True)
        else:
            return FallbackPlan(id=_new_id("fallback"), unavailable_capability=uc,
                fallback_mode="manual_handoff",
                steps=["告知缺失的能力", "提供安全的手动替代方案", "记录能力缺口"],
                quality_expected=0.40, needs_user_notice=True)

class PreferenceDriftMonitor:
    def __init__(self, store_root: str = ".evolution_state/self_evolution"):
        self._store = JsonStore(store_root)
    def snapshot(self, preferences: Dict[str, str]) -> None:
        self._store.append("preference_snapshots.json", {"timestamp": _now(), "preferences": preferences})
    def check(self, current: Dict[str, str]) -> DriftReport:
        snapshots = self._store.read("preference_snapshots.json", [])
        if not snapshots:
            self.snapshot(current)
            return DriftReport(id=_new_id("drift"), status=DriftStatus.STABLE, drift_score=0.0,
                               changed_preferences=[], suggest_actions=["基线已创建"])
        previous = snapshots[-1].get("preferences", {})
        changed = []
        keys = set(previous) | set(current)
        for k in keys:
            if previous.get(k) != current.get(k): changed.append(k)
        drift_score = round(len(changed) / max(1, len(keys)), 4)
        if drift_score >= 0.5:
            status = DriftStatus.DRIFTING; actions = ["在覆写长期偏好前需用户确认"]
        elif drift_score >= 0.2:
            status = DriftStatus.WATCH; actions = ["暂记为试探性偏好"]
        else:
            status = DriftStatus.STABLE; actions = ["可安全更新偏好记忆"]
        self.snapshot(current)
        return DriftReport(id=_new_id("drift"), status=status, drift_score=drift_score,
                           changed_preferences=changed, suggest_actions=actions)

class ObservabilityReporter:
    def __init__(self, store_root: str = ".evolution_state/self_evolution"):
        self._store = JsonStore(store_root)
    def record_event(self, event: Dict) -> None:
        self._store.append("observability_events.json", event)
    def report(self) -> ObservabilityReport:
        events = self._store.read("observability_events.json", [])
        runs = len(events)
        successes = sum(1 for e in events if e.get("success", False))
        qualities = [float(e.get("quality", 0.0)) for e in events if "quality" in e and isinstance(e.get("quality"), (int, float))]
        budget_violations = sum(1 for e in events if e.get("budget_violation", False))
        privacy_events = sum(1 for e in events if e.get("privacy_level") in {"sensitive", "secret"})
        open_circuits = sum(1 for e in events if e.get("circuit_status") == "open")
        success_rate = round(successes / max(1, runs), 4)
        avg_quality = round(sum(qualities) / max(1, len(qualities)), 4)
        summary = f"runs={runs}, success_rate={success_rate}, avg_quality={avg_quality}, budget_violations={budget_violations}, privacy_events={privacy_events}, open_circuits={open_circuits}"
        return ObservabilityReport(id=_new_id("obs"), runs=runs, success_rate=success_rate,
                                    avg_quality=avg_quality, budget_violations=budget_violations,
                                    privacy_events=privacy_events, open_circuits=open_circuits, summary=summary)

class ImprovementProposer:
    @staticmethod
    def propose(simulation: SimulationStatus, budget: BudgetStatus,
                privacy: PrivacyLevel) -> ImprovementPlan:
        changes = []
        risk_level = "low"
        status = ImprovementStatus.SAFE_TO_APPLY
        if budget == BudgetStatus.NEEDS_DOWNGRADE:
            changes.append("在执前添加成本感知的模型降级")
        if simulation != SimulationStatus.PASS:
            changes.append("在执前插入缺失的审批/安全门")
            status = ImprovementStatus.NEEDS_REVIEW
            risk_level = "medium"
        if privacy in {PrivacyLevel.SENSITIVE, PrivacyLevel.SECRET}:
            changes.append("在工具/模型调用前强制隐私脱敏")
            risk_level = "high"
            if privacy == PrivacyLevel.SECRET:
                status = ImprovementStatus.NEEDS_REVIEW
        if not changes:
            changes.append("记录成功流程并维持当前策略")
        return ImprovementPlan(id=_new_id("improve"), title="self_evolution_cycle_improvement",
                                status=status, target_modules=["scripts/self_evolution_engine"],
                                proposed_changes=changes, expected_gain=0.18 if len(changes) > 1 else 0.08,
                                risk_level=risk_level, rollback_plan="禁用新策略; 恢复之前的 JSON 状态快照")

# ============================================================
# EnginePatchProposer (v4.1)
# ============================================================

ENGINE_PATCH_TEMPLATES = {
    "import_patch_fix": {"trigger": ["导入路径", "import", "ModuleNotFoundError", "模块找不到", "No module"],
        "description": "修正引擎文件中的导入路径错误", "target_hint": "产生 ModuleNotFoundError 的引擎文件",
        "code_template": "    # [EnginePatch: import_patch_fix] 导入路径修正\n    # 当 core/pipeline/ 或 core/engines/ 下的模块移动后需更新 import\n"},
    "batch_config_tuning": {"trigger": ["批处理", "batch", "阈值", "写入频率", "commit频率", "持久化延迟"],
        "description": "调整批处理/提交阈值", "target_hint": "包含 batch_count、_auto_commit 的引擎文件",
        "code_template": "    # [EnginePatch: batch_config_tuning] 批处理参数调优\n    BATCH_THRESHOLD = {threshold}\n    def _should_flush(self):\n        return self._batch_count >= self.BATCH_THRESHOLD\n"},
    "error_handling_gate": {"trigger": ["降级", "fallback", "异常处理", "try-except", "静默失败"],
        "description": "增加错误处理/降级逻辑", "target_hint": "缺少 try-except 的文件",
        "code_template": "    # [EnginePatch: error_handling_gate]\n    def _safe_execute(self, fn, fallback_result=None, error_msg=\"\"):\n        try: return fn()\n        except Exception as e: return fallback_result\n"},
    "memory_lifecycle": {"trigger": ["记忆清理", "记忆过期", "记忆归档", "记忆衰减", "记忆维护", "forget"],
        "description": "增加记忆生命周期管理", "target_hint": "core/engines/memory/",
        "code_template": "    # [EnginePatch: memory_lifecycle]\n    MEMORY_MAX_AGE_DAYS = {threshold}\n    def _auto_archive_stale(self): pass\n"},
    "routing_optimizer": {"trigger": ["路由", "分类", "分类器", "模式判断", "权重", "关键词", "classify"],
        "description": "优化路由/分类逻辑", "target_hint": "路由或分类引擎文件",
        "code_template": "    # [EnginePatch: routing_optimizer] 路由分类优化\n"},
    "signal_gate": {"trigger": ["信号质量门", "重复信号", "质量门", "signal_gate"],
        "description": "增加信号质量门", "target_hint": "有计数器逻辑的引擎文件",
        "code_template": "    # [EnginePatch: signal_gate]\n    SIGNAL_GATE_THRESHOLD = {threshold}\n"},
    "fallback_chain": {"trigger": ["降级链", "fallback链", "多重降级", "级联降级"],
        "description": "启用多级降级链", "target_hint": "LocalFallbackPlanner 的 plan()",
        "code_template": "    # [EnginePatch: fallback_chain] 多级降级链\n"},
}

class EnginePatchProposer:
    @staticmethod
    def evaluate(goal: str, improvement: ImprovementPlan, user_confirm: bool = True) -> List[EnginePatchProposal]:
        analysis_text = goal + " " + " ".join(improvement.proposed_changes)
        patches = []
        for tmpl_name, tmpl in ENGINE_PATCH_TEMPLATES.items():
            if not any(re.search(keyword, analysis_text) for keyword in tmpl["trigger"]):
                continue
            threshold = EnginePatchProposer._extract_threshold(analysis_text)
            target_function = EnginePatchProposer._match_target_function(analysis_text)
            code = tmpl["code_template"].replace("{threshold}", str(threshold))
            risk = "low"
            target_path = tmpl["target_hint"]
            if "engine" in target_path.lower() or "hooks" in target_path.lower():
                risk = "medium"
            patch = EnginePatchProposal(id=_new_id("patch"), title=f"{tmpl_name}: {tmpl['description'][:40]}",
                target_engine_path=target_path, target_function=target_function or "未匹配到具体函数",
                patch_type="append", patch_content=code.strip(), reason=tmpl["description"],
                expected_benefit=f"引擎增加{tmpl_name}能力", rollback_method="删除对应代码块",
                risk_level=risk, simulated_score=0.75 if risk == "low" else 0.55, status="pending")
            patches.append(patch)
        return patches

    @staticmethod
    def evaluate_from_experience(experience: dict) -> List[EnginePatchProposal]:
        analysis_text = " ".join([experience.get("title", ""), experience.get("summary", ""),
                                  " ".join(experience.get("rules", [])), " ".join(experience.get("tags", [])),
                                  experience.get("when_to_use", "")])
        return EnginePatchProposer.evaluate(analysis_text, ImprovementPlan(
            id=_new_id("improve"), title="from_experience", status=ImprovementStatus.SAFE_TO_APPLY,
            target_modules=[], proposed_changes=experience.get("rules", []), expected_gain=0.3,
            risk_level="low", rollback_plan=""), user_confirm=True)

    @staticmethod
    def _extract_threshold(text: str) -> int:
        matches = re.findall(r"(\d+)\s*次", text)
        return int(matches[0]) if matches else 5

    @staticmethod
    def _match_target_function(text: str) -> Optional[str]:
        if re.search(r"updat|message|msg", text): return "update_from_message"
        if re.search(r"run_cycle|cycle", text): return "run_cycle"
        if re.search(r"init|启动|初始化", text): return "__init__"
        return None

class RiskAwareExecutor:
    BACKUP_DIR = os.path.join(WORKSPACE, ".learnings", "backups")

    def __init__(self):
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    def execute(self, risk_level: RiskLevel, action_desc: str,
                backup_paths: Optional[List[str]] = None, exec_fn=None,
                validation_fn=None, dry_run: bool = False) -> Dict[str, Any]:
        result = {"status": "unknown", "message": "", "actions": [], "risk_level": risk_level.value}
        if risk_level == RiskLevel.EXTREME:
            result["status"] = "blocked"
            result["message"] = f"⛔ 极高风险操作已拦截: {action_desc}"
            result["actions"] = ["blocked by security mechanism"]
            return result
        if risk_level == RiskLevel.LOW:
            return self._exec_low(action_desc, backup_paths, exec_fn, validation_fn, dry_run)
        if risk_level == RiskLevel.MEDIUM:
            return self._exec_medium(action_desc, backup_paths, exec_fn, dry_run)
        if risk_level == RiskLevel.HIGH:
            plan = self._gen_plan(action_desc, backup_paths)
            backups = self._do_backup(backup_paths) if backup_paths else []
            result["status"] = "needs_double_approval"
            result["message"] = f"⚠️ 高风险操作: {action_desc}"
            result["plan"] = plan
            result["backups"] = backups
            result["actions"] = ["alert user to risk", f"backup created: {len(backups)} files",
                                 "plan ready", "waiting for user double-confirmation"]
            return result
        result["status"] = "error"
        result["message"] = f"未知风险等级: {risk_level}"
        return result

    def _exec_low(self, action_desc, backup_paths, exec_fn, validation_fn, dry_run):
        actions = []
        backups = self._do_backup(backup_paths)
        actions.append(f"backup: {len(backups)} files")
        if dry_run or exec_fn is None:
            return {"status": "ok_dry_run", "message": f"✅ [模拟] {action_desc}", "actions": actions + ["dry_run"]}
        try:
            exec_result = exec_fn()
            actions.append(f"executed: {str(exec_result)[:100]}")
            if validation_fn:
                valid = validation_fn()
                if not valid:
                    self._do_restore(backups)
                    actions.append("validation failed → auto rollback")
                    return {"status": "rolled_back", "message": f"❌ 验证失败已回滚: {action_desc}", "actions": actions}
                actions.append("validation passed")
            return {"status": "ok", "message": f"✅ 自动执行成功: {action_desc}", "actions": actions}
        except Exception as e:
            self._do_restore(backups)
            actions.append(f"exception → auto rollback")
            return {"status": "rolled_back", "message": f"❌ 执行异常已回滚: {str(e)[:100]}", "actions": actions}

    def _exec_medium(self, action_desc, backup_paths, exec_fn, dry_run):
        plan = self._gen_plan(action_desc, backup_paths)
        backups = self._do_backup(backup_paths) if backup_paths else []
        return {"status": "needs_approval", "message": f"🟡 需要确认: {action_desc}", "plan": plan,
                "backups": backups, "actions": ["plan generated, waiting for user approval"]}

    def _gen_plan(self, action_desc: str, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        return {"action": action_desc, "files_to_modify": paths or [],
                "rollback_method": "restore from backup" if paths else "revert change",
                "summary": f"{action_desc}（涉及 {len(paths or [])} 个文件）", "generated_at": _now()}

    def _do_backup(self, paths: Optional[List[str]]) -> List[str]:
        if not paths: return []
        backups = []
        for rel_path in paths:
            abs_path = os.path.join(WORKSPACE, rel_path)
            if not os.path.exists(abs_path): continue
            ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            backup_name = f"{rel_path.replace('/', '_')}_{ts}.bak"
            backup_path = os.path.join(self.BACKUP_DIR, backup_name)
            try:
                shutil.copy2(abs_path, backup_path)
                backups.append({"original": rel_path, "backup": backup_path})
            except Exception as e:
                logger.warning(f"备份失败: {e}")
        return backups

    def _do_restore(self, backups: List[Dict[str, str]]) -> int:
        restored = 0
        for b in backups:
            orig = os.path.join(WORKSPACE, b["original"])
            if os.path.exists(b["backup"]):
                try:
                    shutil.copy2(b["backup"], orig)
                    restored += 1
                except Exception as e:
                    logger.warning(f"恢复失败: {e}")
        return restored

# ============================================================
# SkillSemanticScorer (v4)
# ============================================================

class SkillSemanticScorer:
    DOMAIN_KEYWORDS = {
        "weather": ["天气", "温度", "weather", "temperature"], "search": ["搜索", "查找", "查一下", "search", "find"],
        "document": ["pdf", "docx", "word", "文档", "论文"], "code": ["代码", "报错", "debug", "pytest", "bug"],
        "image": ["图片", "照片", "视觉", "logo", "海报"], "calendar": ["日程", "会议", "事件", "闹钟", "提醒"],
        "memory": ["记忆", "记住", "回忆", "之前聊"], "device": ["闹钟", "备忘录", "设置", "打电话", "发短信"],
        "analysis": ["分析", "总结", "统计", "汇总", "趋势"], "backup": ["备份", "云", "同步", "导入", "导出"],
    }
    INTENT_KEYWORDS = {
        "query": ["搜", "查", "找", "看", "search", "find"], "create": ["创建", "新建", "写", "生成", "create"],
        "update": ["修改", "改", "更新", "update", "edit"], "delete": ["删", "删除", "delete", "移除"],
        "analyze": ["分析", "总结", "看看", "分析一下", "analyze"],
    }

    def score_and_rank(self, skills: List[Dict[str, Any]], user_message: str,
                       environment: Optional[Dict[str, Any]] = None, top_k: int = 8) -> List[Dict[str, Any]]:
        env = environment or {}
        no_ext = env.get("no_external_api", True)
        msg_domains = self._detect_domains(user_message)
        msg_intents = self._detect_intents(user_message)
        scored = []
        for skill in skills:
            score, parts = self._score_single(skill, msg_domains, msg_intents, user_message, no_ext)
            scored.append({"name": skill.get("name", ""), "description": skill.get("description", "")[:120],
                           "score": round(score, 3), "score_parts": parts,
                           "matched_domains": list(msg_domains), "matched_intents": list(msg_intents),
                           "risk": skill.get("risk_level", "low"), "external": skill.get("external_dependency", False)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _score_single(self, skill: Dict[str, Any], domains: set, intents: set, message: str, no_ext: bool) -> Tuple[float, dict]:
        name = skill.get("name", "").lower()
        desc = skill.get("description", "").lower()
        tags = [t.lower() for t in skill.get("tags", [])]
        text = f"{name} {' '.join(tags)} {desc}"
        domain_score = 40.0 if any(d in text for d in domains) else 0.0
        intent_score = 25.0 if any(i in text for i in intents) else 0.0
        is_generic = any(k in name for k in ["helper", "assistant", "general", "工具", "万能", "base"])
        specificity = 15.0 if not is_generic else 3.0
        special = 0.0
        msg_lower = message.lower()
        if any(k in msg_lower for k in ["天气", "weather"]) and "weather" in text: special += 40
        elif any(k in msg_lower for k in ["代码", "报错", "debug"]) and "code" in text: special += 40
        elif any(k in msg_lower for k in ["图片", "照片", "logo"]) and "image" in text: special += 40
        elif any(k in msg_lower for k in ["闹钟", "设置", "备忘录"]) and "note" in text: special += 40
        elif any(k in msg_lower for k in ["记忆", "记住"]) and "memory" in text: special += 40
        risk = skill.get("risk_level", "low")
        risk_penalty = 35 if risk in ("high", "critical", "commit_high") else 0
        ext_penalty = 25 if no_ext and skill.get("external_dependency", False) else 0
        generic_penalty = 12 if is_generic else 0
        score = domain_score + intent_score + specificity + special - risk_penalty - ext_penalty - generic_penalty
        parts = {"domain": round(domain_score, 1), "intent": round(intent_score, 1),
                 "specificity": round(specificity, 1), "special_boost": round(special, 1),
                 "risk_penalty": risk_penalty, "ext_penalty": ext_penalty, "generic_penalty": generic_penalty}
        return score, parts

    def _detect_domains(self, message: str) -> set:
        msg = message.lower()
        return {d for d, kws in self.DOMAIN_KEYWORDS.items() if any(kw.lower() in msg for kw in kws)}

    def _detect_intents(self, message: str) -> set:
        msg = message.lower()
        return {i for i, kws in self.INTENT_KEYWORDS.items() if any(kw.lower() in msg for kw in kws)}

# ============================================================
# xiaoyi-self-evolution SKILL 模块
# ============================================================

def should_run_evaluate_turn(user_msg: str, assistant_msg: str = "",
                              turn_count: int = 0, tool_calls: int = 0,
                              tool_failures: int = 0) -> bool:
    explicit_keywords = ["下次应该", "你应该", "以后都这样", "记住", "注意", "必须", "别", "不要"]
    correction_words = ["不是", "不行", "不对", "错了", "重来", "重新", "应该", "要"]
    has_explicit = any(kw in user_msg for kw in explicit_keywords)
    has_correction = any(w in user_msg for w in correction_words)
    if has_explicit or has_correction:
        return True
    process_words = ["步骤", "流程", "方法", "套路", "先", "然后", "依次", "第一步", "第二步"]
    process_count = sum(1 for w in process_words if w in user_msg or w in assistant_msg)
    if process_count >= 2:
        return True
    if tool_calls >= 5 or tool_failures >= 1:
        return True
    return False

_CONFLICT_TARGET_FILES = [
    "SOUL.md", "AGENTS.md", "TOOLS.md", "MEMORY.md",
    ".evolution_log.json", ".evolution_tracker/registered_rules.json",
]

class ConflictDetector:
    def __init__(self):
        self.target_files = _CONFLICT_TARGET_FILES

    def check(self, proposed_rule: str) -> dict:
        conflict_items = []
        has_duplicate = False
        has_conflict = False

        # 检查 memory 目录
        memory_dir = os.path.join(WORKSPACE, "memory")
        if os.path.exists(memory_dir):
            for fname in os.listdir(memory_dir):
                if not fname.endswith(".md"): continue
                fpath = os.path.join(memory_dir, fname)
                try:
                    text = open(fpath, "r", encoding="utf-8").read()
                    overlap = self._semantic_overlap(proposed_rule, text)
                    if overlap >= 0.85:
                        has_duplicate = True
                        conflict_items.append({"file": f"memory/{fname}", "overlap": round(overlap, 2), "type": "duplicate"})
                    elif overlap >= 0.4:
                        has_conflict = True
                        conflict_items.append({"file": f"memory/{fname}", "overlap": round(overlap, 2), "type": "conflict"})
                except Exception as e:
                    logger.warning(f"重复检测异常: {e}")

        # 检查目标文件
        for fname in self.target_files:
            fpath = os.path.join(WORKSPACE, fname)
            if not os.path.exists(fpath): continue
            try:
                text = open(fpath, "r", encoding="utf-8").read()
                overlap = self._semantic_overlap(proposed_rule, text)
                if overlap >= 0.85:
                    has_duplicate = True
                    conflict_items.append({"file": fname, "overlap": round(overlap, 2), "type": "duplicate"})
                elif overlap >= 0.4:
                    has_conflict = True
                    conflict_items.append({"file": fname, "overlap": round(overlap, 2), "type": "conflict"})
            except Exception as e:
                logger.warning(f"冲突检测异常: {e}")

        skip = has_duplicate or (len([c for c in conflict_items if c["type"] == "conflict"]) >= 3)
        conflict_summary = "; ".join([f"{c['file']}({c['type']}:{c['overlap']})" for c in conflict_items[:5]])

        return {
            "has_duplicate": has_duplicate,
            "has_conflict": has_conflict,
            "conflict_items": conflict_items[:10],
            "conflict_summary": conflict_summary,
            "skip": skip,
        }

    @staticmethod
    def _semantic_overlap(a: str, b: str) -> float:
        words_a = set(re.findall(r"[\w\u4e00-\u9fff]+", a.lower()))
        words_b = set(re.findall(r"[\w\u4e00-\u9fff]+", b.lower()))
        if not words_a or not words_b: return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / max(len(union), 1)

class QualityGate:
    @staticmethod
    def check(proposed_changes: list, goal: str) -> bool:
        if not proposed_changes:
            return False
        for change in proposed_changes:
            if len(change) < 5:
                return False
            has_verb = any(v in change for v in ["添加", "修改", "替换", "增加", "删除", "调整",
                                                   "使用", "在...前", "强制", "优先", "跳过", "需要",
                                                   "检查", "确认", "验证", "判断", "读取", "写入",
                                                   "执行", "传递", "调用", "对比", "分析", "处理"])
            if not has_verb:
                return False
        # 可执行检查：goal 或 change 文本中有触发条件词或操作动词即可
        all_text = goal + " " + " ".join(proposed_changes)
        has_context = any(t in all_text for t in ["当", "如果", "在", "时", "后", "前", "需要", "必须", "每次", "前", "后",
                                                    "调用", "检查", "确认", "读取", "写入", "判断", "对比"])
        if not has_context and len(proposed_changes) <= 2:
            return False
        # 长期有效
        one_time = any(w in " ".join(proposed_changes) for w in ["这个 bug", "当前", "这次", "临时"])
        if one_time:
            return False
        return True

class TargetFileMapper:
    _TOOLS_KEYWORDS = ["命令", "参数", "路径", "安装", "环境", "端口", "配置", "--", "export", "git", "npm"]
    _AGENTS_KEYWORDS = ["不要", "应该", "必须先", "禁止", "允许", "必须", "检查", "铁律"]
    _MEMORY_KEYWORDS = ["偏好", "习惯", "喜欢", "不喜欢", "常用", "偏好使用", "经常"]

    @staticmethod
    def map(proposed_changes: list) -> str:
        full_text = " ".join(proposed_changes)
        tools_score = sum(1 for kw in TargetFileMapper._TOOLS_KEYWORDS if kw in full_text)
        agents_score = sum(1 for kw in TargetFileMapper._AGENTS_KEYWORDS if kw in full_text)
        memory_score = sum(1 for kw in TargetFileMapper._MEMORY_KEYWORDS if kw in full_text)

        if len(full_text) > 200 and any("步骤" in c or "先" in c for c in proposed_changes):
            return "new_skill"
        if tools_score >= agents_score and tools_score >= memory_score and tools_score > 0:
            return "TOOLS.md"
        if agents_score >= tools_score and agents_score >= memory_score and agents_score > 0:
            return "AGENTS.md"
        return "MEMORY.md"

# ============================================================
# 新增模块1: PatternMiner
# ============================================================

class PatternMiner:
    def __init__(self):
        self.min_results_file = os.path.join(WORKSPACE, ".pattern_mining_results.json")
        self.min_counts_file = os.path.join(WORKSPACE, ".pattern_count_data.json")
        self._cached_results = []

    def scan_all(self) -> list:
        memory_dir = os.path.join(WORKSPACE, "memory")
        sentences = []
        if os.path.exists(memory_dir):
            for fname in os.listdir(memory_dir):
                if not fname.endswith(".md"): continue
                fpath = os.path.join(memory_dir, fname)
                try:
                    text = open(fpath, "r", encoding="utf-8").read()
                    sentences.extend(self.extract_candidate_sentences(text))
                except Exception as e:
                    logger.warning(f"读取规则文件异常: {e}")
        return sentences

    @staticmethod
    def extract_candidate_sentences(text: str) -> list:
        lines = text.split("\n")
        candidates = []
        markers = ["要", "不要", "应该", "注意", "记住", "必须", "禁止", "允许", "偏好", "习惯", "喜欢"]
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(">"):
                continue
            if any(m in line for m in markers):
                candidates.append(line[:200])
        return candidates

    def cluster_semantic(self, sentences: list) -> dict:
        clusters = {}
        used = set()
        for i, sa in enumerate(sentences):
            if i in used: continue
            cluster = [sa]
            used.add(i)
            words_a = self._get_words(sa)
            for j, sb in enumerate(sentences):
                if j in used: continue
                words_b = self._get_words(sb)
                overlap = self._calc_jaccard(words_a, words_b)
                if overlap >= 0.4:
                    cluster.append(sb)
                    used.add(j)
            key = self._cluster_key(cluster[0])
            if key not in clusters:
                clusters[key] = cluster
            else:
                clusters[key].extend(cluster)
        return clusters

    def detect_recurring(self, threshold: int = 3, window_days: int = 7) -> list:
        sentences = self.scan_all()
        clusters = self.cluster_semantic(sentences)
        recurring = []
        for key, items in clusters.items():
            if len(items) >= threshold:
                recurring.append({"pattern": key, "count": len(items), "samples": items[:5]})
        return recurring

    def generate_candidates(self) -> list:
        recurring = self.detect_recurring()
        candidates = []
        for r in recurring:
            candidates.append({
                "source": "pattern_miner",
                "pattern": r["pattern"],
                "count": r["count"],
                "proposed_rule": r["pattern"][:120],
                "samples": r["samples"][:3],
            })
        self._cached_results = candidates
        self.save_results(candidates)
        return candidates

    def save_results(self, results: list):
        data = {"timestamp": _now(), "results": results}
        json.dump(data, open(self.min_results_file, "w"), ensure_ascii=False, indent=2)

    def load_results(self) -> list:
        if os.path.exists(self.min_results_file):
            try:
                return json.load(open(self.min_results_file)).get("results", [])
            except Exception as e:
                logger.warning(f"语义重叠计算异常: {e}")
        return []

    def _get_words(self, text: str) -> set:
        return set(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))

    def _calc_jaccard(self, a: set, b: set) -> float:
        if not a or not b: return 0.0
        return len(a & b) / max(len(a | b), 1)

    def _cluster_key(self, sample: str) -> str:
        words = re.findall(r"[\u4e00-\u9fff]{2,}", sample)
        return "|".join(words[:3]) if words else sample[:20]

# ============================================================
# 新增模块2: SkillGenerator
# ============================================================

class SkillGenerator:
    THRESHOLD_COUNT = 5
    THRESHOLD_HITS = 10

    def __init__(self, rule_store: RuleStore):
        self.rule_store = rule_store

    def check_threshold(self) -> list:
        all_rules = self.rule_store.list_all()
        categories = {}
        for rule in all_rules:
            cat = rule.category or "uncategorized"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rule)
        ready = []
        for cat, rules in categories.items():
            if len(rules) >= self.THRESHOLD_COUNT:
                total_hits = sum(r.total_hits for r in rules)
                if total_hits >= self.THRESHOLD_HITS:
                    ready.append({"category": cat, "count": len(rules), "total_hits": total_hits, "rules": rules})
        return ready

    def merge_candidates(self, category_experiences: list) -> dict:
        if not category_experiences:
            return {}
        rules = category_experiences.get("rules", [])
        merged = {
            "title": f"auto-skill-{category_experiences.get('category', 'uncategorized')}",
            "summary": f"自动生成的技能，来自 {len(rules)} 条同类经验",
            "rules": list(set(r.content[:200] for r in rules)),
            "when_to_use": f"当用户任务涉及 {category_experiences.get('category', '相关')} 领域时",
        }
        return merged

    def propose_skill(self, merged: dict) -> dict:
        return {
            "title": merged.get("title", "auto-skill"),
            "summary": merged.get("summary", ""),
            "rules": merged.get("rules", []),
            "when_to_use": merged.get("when_to_use", ""),
            "proposed_at": _now(),
        }

    def skill_quality_score(self, skill_name: str) -> dict:
        all_rules = self.rule_store.list_all()
        relevant = [r for r in all_rules if skill_name in r.source]
        if not relevant:
            return {"status": "no_data", "skill": skill_name}
        total_hits = sum(r.total_hits for r in relevant)
        total_violations = sum(r.violations for r in relevant)
        hit_rate = total_hits / max(len(relevant), 1)
        violation_rate = (total_violations / max(total_hits, 1)) if total_hits > 0 else 0
        fresh_count = sum(1 for r in relevant if r.last_hit_at and (
            datetime.now(_BEIJING).timestamp() - datetime.fromisoformat(r.last_hit_at).timestamp() < 86400 * 7))
        return {
            "skill": skill_name,
            "total_rules": len(relevant),
            "total_hits": total_hits,
            "total_violations": total_violations,
            "avg_hit_rate": round(hit_rate, 2),
            "violation_rate": round(violation_rate, 4),
            "fresh_rules_7d": fresh_count,
            "score": round(max(0, (hit_rate * 0.6 + fresh_count / max(len(relevant), 1) * 0.3 - violation_rate * 0.1)), 2),
        }

    def generate_all(self) -> list:
        ready_categories = self.check_threshold()
        proposals = []
        for cat_info in ready_categories:
            merged = self.merge_candidates(cat_info)
            proposal = self.propose_skill(merged)
            proposals.append(proposal)
        return proposals

# ============================================================
# 主引擎: SelfEvolutionEngine v5 (统一)
# ============================================================

class SelfEvolutionEngine:
    """
    自进化引擎 v5 — 统一引擎
    合并 v3+v4+tracker+MASA+xiaoyi-skill 规则
    新增 PatternMiner + SkillGenerator
    """

    def __init__(self, state_root: str = ".evolution_state/self_evolution"):
        self.root = Path(state_root)
        self.root.mkdir(parents=True, exist_ok=True)

        # v4 模块
        self.json_store = JsonStore(str(self.root))
        self.intent = IntentContractCompiler()
        self.privacy = PrivacyRedactor()
        self.budget = BudgetGovernor()
        self.simulation = SimulationLab()
        self.reliability = ToolReliabilityManager(str(self.root))
        self.fallback = LocalFallbackPlanner()
        self.drift = PreferenceDriftMonitor(str(self.root))
        self.observability = ObservabilityReporter(str(self.root))
        self.proposer = ImprovementProposer()
        self.patch_proposer = EnginePatchProposer()

        # tracker 融合
        self._rule_store = RuleStore()
        self._rules: Dict[str, RegisteredRule] = {}
        self._load_tracker_state()

        # MASA 融合
        self._masa_predictor = MASAPredictor()
        self._masa_aligner = MASAAliener()
        self._masa_history: list = []
        self._masa_stats = self._load_masa_stats()

        # xiaoyi 新增模块
        self.conflict_detector = ConflictDetector()
        self.quality_gate = QualityGate()
        self.target_mapper = TargetFileMapper()
        self.pattern_miner = PatternMiner()
        self.skill_generator = SkillGenerator(self._rule_store)

        # v3 兼容状态
        self.evolution_log = self._load_evolution_log_v3()
        self.tuning_log = self._load_tuning_log_v3()

    # ── 统一入口 ──

    def unified_run_cycle(self, goal: str, context: Optional[Dict] = None,
                           dry_run: bool = True) -> EvolutionCycleResult:
        """
        统一自进化闭环:
        1. 触发门禁检查 (should_run_evaluate_turn) — 不满足时快速跳过
        2. 质量门禁过滤 (QualityGate)
        3. v4 完整 8 子模块评估
        4. 冲突检测 (ConflictDetector)
        5. 目标文件映射 (TargetFileMapper)
        6. 风险决策树
        7. 低风险自动沉淀 / 中风险提案
        """
        ctx = context or {}
        user_msg = ctx.get("user_msg", "")
        assistant_msg = ctx.get("assistant_msg", "")
        turn_count = ctx.get("turn_count", 0)
        tool_calls = ctx.get("tool_calls", 0)
        tool_failures = ctx.get("tool_failures", 0)

        # ── Phase 1: 触发门禁 ──
        if not should_run_evaluate_turn(user_msg, assistant_msg, turn_count, tool_calls, tool_failures):
            return EvolutionCycleResult(
                run_id=_new_id("sevo_skip"), goal=goal,
                contract_status=ContractStatus.READY,
                context_confidence=0.0, budget_status=BudgetStatus.WITHIN_BUDGET,
                privacy_level=PrivacyLevel.PUBLIC,
                reliability_status=CircuitStatus.CLOSED,
                fallback_mode="none", simulation_status=SimulationStatus.PASS,
                drift_status=DriftStatus.STABLE,
                observability_summary="trigger_gate_skipped",
                improvement_status=ImprovementStatus.PROPOSED,
                final_status="skipped_no_trigger", next_action="日常对话，无需自进化",
                details={},
                engine_patches=[], evolved=False, precipitated=False, experience_count=0,
            )

        # ── Phase 1.5: 无障碍质量数据读取 ──
        # 从 accessibility_filter 的 evolution feed 中读取最近质量评分
        # 如果可读性持续偏低，触发无障碍优化评估
        try:
            from core.engines.hooks.accessibility_filter import get_evolution_feed
            _access_feed = get_evolution_feed(limit=5)
            if _access_feed:
                _avg_score = sum(e.get("score", 0) for e in _access_feed) / len(_access_feed)
                if _avg_score < 3.0:
                    logger.info(f"[SelfEvolve] 无障碍质量持续偏低({round(_avg_score, 2)}/10), "
                                f"共{len(_access_feed)}条记录, 考虑无障碍优化")
        except Exception:
            pass

        # ── Phase 2-3: 完整评估 ──
        result = self.run_cycle(goal, ctx, tool_name="self_evolution_cycle", dry_run=dry_run)

        if dry_run:
            return result

        # ── Phase 4-7: 自动沉淀链路 ──
        proposed = result.details.get("proposed_changes", [])
        if not proposed or not QualityGate.check(proposed, goal):
            return result

        # 冲突检测
        for change in proposed:
            conflict = self.conflict_detector.check(change)
            if conflict.get("skip", False):
                logger.info(f"[SelfEvolve] 冲突/重复跳过: {change[:60]}")
                continue

            # 目标文件映射
            target_file = self.target_mapper.map([change])

            # 风险决策树
            risk = self._assess_precipitation_risk(change, target_file)
            if risk == "high":
                continue
            if risk == "medium":
                self._queue_for_confirmation(goal, change, target_file)
                continue

            # 低风险 → 自动沉淀
            self._auto_precipitate(goal, change, target_file)

        return result

    def _assess_precipitation_risk(self, change: str, target_file: str) -> str:
        """
        自动沉淀风险决策树
        low → 直接沉淀
        medium → 提案等确认
        high → 跳过
        """
        high_keywords = ["删除文件", "修改配置", "重启服务", "改权限", "安装包",
                         "卸载", "token", "密钥", "密码", "rm ", "chmod "]
        for kw in high_keywords:
            if kw in change.lower():
                return "high"
        risky_files = ["openclaw.plugin.json", "config.json", "_meta.json", "install.py", "deploy.js"]
        for f in risky_files:
            if f in target_file:
                return "medium"
        if len(change) < 10:
            return "medium"
        return "low"

    def _auto_precipitate(self, goal: str, change: str, target_file: str):
        """低风险经验自动沉淀到 evolved_experiences.jsonl"""
        path = os.path.join(WORKSPACE, ".evolved_experiences.jsonl")
        entry = {
            "timestamp": _now(),
            "goal": goal[:200],
            "change": change[:300],
            "target_file": target_file,
            "risk": "low",
            "auto_applied": True,
        }
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(f"[SelfEvolve] 自动沉淀到 {target_file}: {change[:60]}")
        except Exception as e:
            logger.warning(f"[SelfEvolve] 沉淀写入失败: {e}")

    def _queue_for_confirmation(self, goal: str, change: str, target_file: str):
        """中风险 → 写入 pending 队列等用户确认"""
        path = os.path.join(WORKSPACE, ".evolution_pending.json")
        entry = {
            "timestamp": _now(),
            "goal": goal[:200],
            "change": change[:300],
            "target_file": target_file,
            "risk": "medium",
            "status": "pending_confirmation",
        }
        try:
            data = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, list):
                data = []
            data.append(entry)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[SelfEvolve] 中风险提案进入待确认: {change[:60]}")
        except Exception as e:
            logger.warning(f"[SelfEvolve] 提案写入失败: {e}")

    # ── v4 run_cycle ──

    def run_cycle(self, goal: str,
                  preferences: Optional[Dict[str, str]] = None,
                  tool_name: str = "default_tool",
                  dry_run: bool = True) -> EvolutionCycleResult:
        run_id = _new_id("sevo")
        preferences = preferences or {"delivery_style": "one_shot_package",
                                       "risk_style": "approval_for_high_risk"}

        # 1. 目标意图合约
        contract = self.intent.compile(goal)

        # 2. 隐私脱敏
        privacy_result = self.privacy.redact(goal)

        # 3. 预算决策
        task_type = self._detect_task_type(goal)
        complexity = self._detect_complexity(goal)
        budget = self.budget.decide(task_type, complexity)

        # 4. 模拟执行
        planned_steps = ["compile intent contract", "check privacy level",
                         "check budget constraints", "simulate execution", "record observation"]
        risk_flags = []
        if privacy_result.privacy_level in {PrivacyLevel.SENSITIVE, PrivacyLevel.SECRET}:
            risk_flags.append("secret")
        if any(x in goal for x in ["发送", "转账", "外发"]):
            risk_flags.append("external_send")
        sim = self.simulation.simulate(goal, planned_steps, risk_flags)

        # 5. 工具可靠性
        reliability = self.reliability.decide(tool_name)

        # 6. 降级规划
        fallback = self.fallback.plan("none")

        # 7. 偏好漂移
        drift = self.drift.check(preferences)

        # 8. 改进提案
        improvement = self.proposer.propose(sim.status, budget.status, privacy_result.privacy_level)

        # 8.5 引擎补丁
        engine_patches = self.patch_proposer.evaluate(goal, improvement)

        # 9. 最终状态
        success = (contract.status == ContractStatus.READY
                   and budget.status != BudgetStatus.BLOCKED_OVER_BUDGET
                   and privacy_result.privacy_level != PrivacyLevel.SECRET
                   and sim.status != SimulationStatus.FAIL)

        # 10. 可观测
        self.observability.record_event({
            "run_id": run_id, "goal": goal[:200], "success": success,
            "quality": 0.9 if success else 0.55,
            "budget_violation": budget.status == BudgetStatus.BLOCKED_OVER_BUDGET,
            "privacy_level": privacy_result.privacy_level.value,
            "circuit_status": reliability.circuit_status.value,
        })
        obs = self.observability.report()

        # 11. 最终判定
        if contract.status == ContractStatus.UNSAFE or privacy_result.privacy_level == PrivacyLevel.SECRET:
            final_status = "blocked_for_privacy_or_contract"
            next_action = "拒绝执行敏感外泄目标，修改安全目标后重试"
        elif sim.status == SimulationStatus.FAIL:
            final_status = "needs_safety_repair"
            next_action = "先补全审批/安全门，再进入执行"
        elif budget.status == BudgetStatus.NEEDS_DOWNGRADE:
            final_status = "ready_with_budget_downgrade"
            next_action = "使用低成本模型组或分批执行"
        else:
            final_status = "ready_for_execution"
            next_action = "可进入 WorkflowOrchestrator 编排执行"

        return EvolutionCycleResult(
            run_id=run_id, goal=goal, contract_status=contract.status,
            context_confidence=0.7, budget_status=budget.status,
            privacy_level=privacy_result.privacy_level,
            reliability_status=reliability.circuit_status,
            fallback_mode="dry_run" if dry_run else fallback.fallback_mode,
            simulation_status=sim.status, drift_status=drift.status,
            observability_summary=obs.summary, improvement_status=improvement.status,
            final_status=final_status, next_action=next_action,
            details={"task_type": task_type, "complexity": complexity,
                     "budget": {"tokens": budget.token_budget, "cost": budget.cost_budget,
                                "model_group": budget.recommended_model_group},
                     "privacy_replacements": privacy_result.replacements,
                     "simulation_failures": sim.failures, "simulation_recommendations": sim.recommendations,
                     "drift_score": drift.drift_score, "proposed_changes": improvement.proposed_changes,
                     "observability": obs.summary,
                     "engine_patches": [{"title": p.title, "target_file": p.target_engine_path,
                                          "risk": p.risk_level, "score": p.simulated_score} for p in engine_patches]},
            engine_patches=engine_patches, evolved=False, precipitated=False, experience_count=0,
        )

    def learn_from_result(self, result: EvolutionCycleResult) -> None:
        success = result.final_status == "ready_for_execution"
        if result.final_status in ("privacy_blocked", "blocked"):
            return
        self.reliability.record_result("self_evolution_cycle", success)

    def try_engine_patch(self, experience: dict) -> List[EnginePatchProposal]:
        patches = EnginePatchProposer.evaluate_from_experience(experience)
        if patches:
            self.observability.record_event({
                "event": "engine_patch_proposed",
                "from_experience": experience.get("title", ""),
                "patch_count": len(patches),
            })
        return patches

    # ── v3 兼容方法 ──

    def evaluate_turn(self, context: Optional[Dict] = None) -> Dict:
        return self.run_cycle(
            goal="评估用户最近输入是否需要自进化",
            preferences={"context": context or {}},
            tool_name="self_evolution_evaluate",
            dry_run=True
        ).__dict__ if False else {"status": "ok", "source": "v5", "evolved": False}

    def reflect(self, task_text: str, result: Dict) -> Optional[Dict]:
        routing = self.route_to_memory_or_evolution(task_text, result)
        outcome = {"routing": routing, "to_memory": routing.get("to_memory", False),
                   "to_evolution": routing.get("to_evolution", False),
                   "reason": routing.get("reason", "无明显进化价值")}
        if routing.get("to_memory"):
            mresult = self.save_to_memory(task_text, tags=routing.get("tags", []), scene=routing.get("scene", ""))
            if isinstance(mresult, dict):
                outcome["memory_id"] = mresult.get("mid")
                outcome["memory_saved"] = mresult.get("mid") is not None
        if bool(result.get("error", "")) and (bool(result.get("tools", [])) or bool(result.get("tool_used", False))):
            outcome["tool_failure"] = {"task": task_text[:200], "error": str(result.get("error", ""))[:200],
                                        "timestamp": datetime.now(_BEIJING).isoformat()}
        if routing.get("to_evolution"):
            learning = {"timestamp": datetime.now(_BEIJING).isoformat(),
                        "triggered_by": ["user_correction" if routing.get("reason") == "行为纠正/纠错" else "auto"],
                        "status": "applied", "reward": 0.5, "context": task_text[:200]}
            self.update_strategy(learning, 0.5)
            outcome.update({"evolved": True, "reward": 0.5, "learning_text": task_text[:60]})
            self._auto_register_from_evolution(task_text, routing.get("tags", []))
        return outcome

    def route_to_memory_or_evolution(self, task_text: str, result: Dict) -> Dict:
        classification = {"to_memory": False, "to_evolution": False, "tags": [], "scene": "", "reason": ""}
        remember_cmds = ["记住", "记下", "别忘了", "不要忘", "写下来", "保存"]
        is_explicit_remember = any(cmd in task_text for cmd in remember_cmds)
        user_corrected = any(["不" in task_text and any(w in task_text for w in ["是", "对", "行"]),
                              "改" in task_text, "不是" in task_text, "错了" in task_text,
                              "不行" in task_text, "不对" in task_text, "重新" in task_text])
        has_error = bool(result.get("error", ""))
        process_words = ["步骤", "流程", "方法", "套路", "先", "然后", "依次"]
        has_process = any(w in task_text for w in process_words)
        preference_words = ["我喜欢", "我用", "我习惯", "偏好", "偏爱"]
        is_preference = any(pw in task_text for pw in preference_words)
        is_debug = has_error
        if is_explicit_remember:
            classification.update({"to_memory": True, "tags": ["user_preference", "explicit"],
                                    "scene": "user_requests", "reason": "用户明确要求记住"})
        elif is_preference:
            classification.update({"to_memory": True, "tags": ["user_preference"],
                                    "scene": "user_profile", "reason": "用户偏好表达"})
        elif (is_debug and user_corrected) or has_error:
            classification.update({"to_evolution": True, "to_memory": True, "tags": ["debug", "pitfall"],
                                    "scene": "troubleshooting", "reason": "排错/踩坑经验（双通道）"})
        elif user_corrected:
            classification.update({"to_evolution": True, "tags": ["behavior_correction"],
                                    "reason": "行为纠正/纠错"})
        elif has_process:
            classification.update({"to_evolution": True, "to_memory": True, "tags": ["process", "workflow"],
                                    "scene": "workflows", "reason": "流程性经验"})
        return classification

    def detect_evolution_trigger(self, text: str, context: Dict = None) -> Dict:
        triggers = {"debug_path": False, "pitfall_avoid": False, "behavior_correct": False,
                    "process_pattern": False, "tool_tip": False}
        if re.search(r'(终于找到原因|排查步骤|排查方法|定位到问题)', text): triggers["debug_path"] = True
        if re.search(r'(踩坑|别掉坑|注意避让|坑点)', text): triggers["pitfall_avoid"] = True
        if re.search(r'(不要这样|以后别|应该这样|正确做法)', text): triggers["behavior_correct"] = True
        if re.search(r'(流程|步骤|方法|套路|标准化)', text): triggers["process_pattern"] = True
        if re.search(r'(妙用|小技巧|还可以这样|高效方法)', text): triggers["tool_tip"] = True
        return triggers

    def masa_predict(self, task_context: dict) -> dict:
        return self._masa_predictor.predict(task_context)

    def masa_align(self, prediction: dict, actual: dict) -> dict:
        result = self._masa_aligner.align(prediction, actual)
        self._masa_record(prediction, actual, result)
        return result

    def masa_run(self, task_context: dict, actual: dict) -> dict:
        prediction = self.masa_predict(task_context)
        alignment = self.masa_align(prediction, actual)
        feedback = self._masa_build_feedback(alignment, task_context)
        return {"prediction": prediction, "alignment": alignment, "feedback": feedback}

    def _masa_record(self, prediction: dict, actual: dict, alignment: dict):
        record = {"timestamp": datetime.now(_BEIJING).isoformat(),
                  "prediction": {"difficulty": prediction.get("difficulty"), "time_cost_s": prediction.get("time_cost_s"),
                                  "confidence": prediction.get("confidence")},
                  "actual": {"difficulty": actual.get("difficulty"), "time_cost_s": actual.get("time_cost_s"),
                              "success": actual.get("success")},
                  "alignment": {"score": alignment.get("alignment_score"), "match": alignment.get("difficulty_match"),
                                 "time_error_rate": alignment.get("time_error_rate"),
                                 "bias_pattern": alignment.get("bias_pattern")}}
        self._masa_history.append(record)
        if len(self._masa_history) > 200:
            self._masa_history = self._masa_history[-200:]
        self._masa_update_stats(alignment)
        self._save_masa_stats()

    def _masa_update_stats(self, alignment: dict):
        s = self._masa_stats
        s["total_cycles"] += 1
        n = s["total_cycles"]
        score = alignment.get("alignment_score", 0.0)
        s["avg_alignment_score"] = round((s["avg_alignment_score"] * (n - 1) + score) / n, 3) if n > 1 else score
        bias = alignment.get("bias_pattern", "unknown")
        s["bias_distribution"][bias] = s["bias_distribution"].get(bias, 0) + 1
        s["last_bias_pattern"] = bias
        s["last_alignment_score"] = score
        s["updated_at"] = datetime.now(_BEIJING).isoformat()

    def _masa_build_feedback(self, alignment: dict, task_context: dict) -> dict:
        bias = alignment.get("bias_pattern", "")
        score = alignment.get("alignment_score", 1.0)
        feedback = {"type": "masa_alignment", "bias_pattern": bias,
                     "bias_label": alignment.get("bias_label"), "alignment_score": score}
        if score < 0.6:
            feedback["requires_evolution"] = True
            feedback["evolution_reason"] = f"对齐度偏低({score}): {alignment.get('bias_label')}"
            feedback["should_reflect"] = True
            feedback["alignment_data"] = {"alignment_score": score, "bias_pattern": bias,
                                           "bias_label": alignment.get("bias_label")}
        else:
            feedback["requires_evolution"] = False
            feedback["should_reflect"] = False
        return feedback

    def save_to_memory(self, text: str, tags: List[str] = None, scene: str = "") -> Dict:
        try:
            from core.engines.memory.auto_memory import AutoMemory
            ms = AutoMemory()
            mid = ms.save(text, tags=tags or [], scene=scene or "")
            return {"ok": True, "mid": mid, "error": None}
        except Exception as e:
            return {"ok": False, "mid": None, "error": str(e)[:200]}

    def update_strategy(self, learning: Dict, reward: float):
        learning["reward"] = reward
        learning["status"] = "applied" if reward >= 0.6 else "low_value"

    # ── 追踪系统 ──

    def register_rule(self, content: str, source: str = "self_evolution",
                      category: str = "experience", tags: list = None) -> str:
        rule_id = self._gen_rule_id(content)
        rule = RegisteredRule(rule_id, content, source, category, tags or [])
        self._rule_store.register(rule)
        return rule_id

    def check_rules(self, context: str) -> List[RegisteredRule]:
        return self._rule_store.check_rules(context)

    def record_hit(self, rule_id: str):
        self._rule_store.record_hit(rule_id)

    def record_violation(self, rule_id: str):
        self._rule_store.record_violation(rule_id)

    def list_rules(self) -> List[RegisteredRule]:
        return self._rule_store.list_all()

    # ── 主动挖掘 ──

    def run_pattern_mining(self) -> list:
        return self.pattern_miner.generate_candidates()

    # ── 技能生成 ──

    def run_skill_generation(self) -> list:
        return self.skill_generator.generate_all()

    # ── v3 兼容内部方法 ──

    def _load_evolution_log_v3(self) -> Dict:
        evo_path = os.path.join(WORKSPACE, ".evolution_log.json")
        if os.path.exists(evo_path):
            try:
                return json.load(open(evo_path))
            except Exception as e:
                logger.warning(f"演进数据加载失败: {e}")
        return {"experiences": [], "learnings": [], "stats": {}}

    def _load_tuning_log_v3(self) -> Dict:
        tun_path = os.path.join(WORKSPACE, ".tuning_log.json")
        if os.path.exists(tun_path):
            try:
                return json.load(open(tun_path))
            except Exception as e:
                logger.warning(f"调优数据加载失败: {e}")
        return {"history": [], "stats": {}}

    def _load_tracker_state(self):
        for rule in self._rule_store.list_all():
            self._rules[rule.id] = rule

    def _load_masa_stats(self) -> dict:
        path = os.path.join(WORKSPACE, ".masa_stats.json")
        if os.path.exists(path):
            try: return json.load(open(path))
            except Exception as e:
                logger.warning(f"MASA配置读取失败: {e}")
        return {"total_cycles": 0, "avg_alignment_score": 0.0, "bias_distribution": {},
                "difficulty_mismatch_count": 0, "overconfidence_count": 0,
                "last_bias_pattern": "", "last_alignment_score": 0.0,
                "initialized_at": datetime.now(_BEIJING).isoformat()}

    def _save_masa_stats(self):
        path = os.path.join(WORKSPACE, ".masa_stats.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._masa_stats, f, indent=2, ensure_ascii=False)

    def _auto_register_from_evolution(self, text: str, tags: list):
        stripped = text.strip().strip('.').strip()[:120]
        if len(stripped) > 10:
            self.register_rule(stripped, "self_evolution", "experience", tags)

    def _gen_rule_id(self, content: str) -> str:
        return "rule_" + str(abs(hash(content)) % 100000)

    def _detect_task_type(self, goal: str) -> str:
        if any(x in goal for x in ["代码", "pytest", "报错", "debug"]): return "coding"
        if any(x in goal for x in ["视频", "图片", "logo", "海报", "视觉"]): return "media"
        if any(x in goal for x in ["规则", "规范", "合规", "安全", "治理"]): return "compliance"
        if any(x in goal for x in ["记忆", "记住", "进化", "人格", "偏好"]): return "evolution"
        return "general"

    def _detect_complexity(self, goal: str) -> str:
        if any(x in goal for x in ["十个", "10个", "大版本", "全量", "一次性全部"]): return "high"
        if len(goal) > 80: return "medium"
        return "low"

# ============================================================
# v3 模块级接口（兼容）
# ============================================================

def init():
    global _instance
    if _instance is None:
        _instance = SelfEvolutionEngine()
    return _instance

def get_engine() -> SelfEvolutionEngine:
    return init()

def get_evolution_engine():
    return init()

def get_store() -> RuleStore:
    return init()._rule_store

def get_predictor() -> MASAPredictor:
    return MASAPredictor()

def get_aligner() -> MASAAliener:
    return MASAAliener()

# ============================================================
# v3 兼容函数
# ============================================================

def _check_correction_signals() -> List[Dict]:
    hits = []
    if os.path.exists(HIT_LOG_FILE):
        try:
            with open(HIT_LOG_FILE) as f:
                lines = f.readlines()
            for line in lines[-10:]:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("hit_type") == "violated":
                        hits.append(entry)
                except Exception as e:
                    logger.warning(f"违规条目分析异常: {e}")
        except Exception as e:
            logger.warning(f"Hit日志读取失败: {e}")
    return hits

def _check_rules_trigger() -> int:
    return len(init().list_rules())

def evaluate_turn() -> Dict:
    try:
        engine = init()
        result = engine.run_cycle(
            goal="评估用户最近输入是否需要自进化",
            preferences={"context": {}},
            tool_name="self_evolution_evaluate",
            dry_run=True
        )
        return {"status": "ok", "source": "v5", "corrections": 0, "rules_triggered": 0,
                "evolved": result.final_status == "ready_for_execution"}
    except Exception as e:
        return {"status": "error", "source": "v5_fallback", "error": str(e)[:200]}

DEFAULT_CONFIG = {
    "anti_fake": {"risk_threshold": "high"},
    "dual_mode": {"default_mode": "fast", "auto_switch": True},
    "lazy_load": {"search_interval_ms": 500, "max_searches_per_task": 5, "cache_ttl_seconds": 1800},
    "mutex": {"task_timeout_seconds": 180, "max_retry": 3},
    "memory_layer": {"l2_retention_days": 7, "decay_start_days": 30, "decay_end_days": 90, "decay_min_weight": 0.5},
}

def get_current_config() -> dict:
    return dict(DEFAULT_CONFIG)

# ============================================================
# CLI 入口
# ============================================================

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

    import sys as _sys
    _sys.path.insert(0, WORKSPACE)
    if "--evaluate-turn" in _sys.argv:
        _result = evaluate_turn()
        print(json.dumps(_result, ensure_ascii=False))
    elif "--init" in _sys.argv or "--bootstrap" in _sys.argv:
        _engine = init()
        print(json.dumps({"status": "ready", "version": "Unified SelfEvolutionEngine v5 --- Crusheart v7.0.0"}, ensure_ascii=False))
    elif "--run-pattern-mining" in _sys.argv:
        _engine = init()
        _candidates = _engine.run_pattern_mining()
        print(json.dumps({"candidates": _candidates}, ensure_ascii=False))
    elif "--run-skill-gen" in _sys.argv:
        _engine = init()
        _proposals = _engine.run_skill_generation()
        print(json.dumps({"proposals": _proposals}, ensure_ascii=False))
    else:
        _engine = init()
        print(json.dumps({"status": "ok", "mode": "standalone",
                           "version": "Unified SelfEvolutionEngine v5 --- Crusheart v7.0.0"},
                          ensure_ascii=False))
