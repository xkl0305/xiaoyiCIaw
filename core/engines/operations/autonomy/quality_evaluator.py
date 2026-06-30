"""quality_evaluator (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import asdict
from ._common import new_id, STATE_DIR
from .json_store import JsonStore
from .quality_report import QualityReport

class QualityEvaluator:
    """执行质量评估器"""

    def __init__(self):
        self.store = JsonStore(os.path.join(STATE_DIR, "quality_reports.json"))

    def evaluate(self, run_id: str, goal: str, result: Dict,
                 risk_blocked: bool = False) -> QualityReport:
        issues = []
        completeness = 0.9 if result.get("has_plan") and result.get("has_next_action") else 0.55
        usefulness = 0.9 if result.get("actionable") else 0.6
        efficiency = 0.85 if result.get("steps", 0) <= 10 else 0.65
        safety = 0.95 if not risk_blocked else 0.72
        if not result.get("has_plan"):
            issues.append("missing_plan")
        if not result.get("has_next_action"):
            issues.append("missing_next_action")
        if risk_blocked:
            issues.append("waiting_for_approval")
        final_score = round(completeness * 0.35 + usefulness * 0.25 + safety * 0.25 + efficiency * 0.15, 4)
        report = QualityReport(new_id("quality"), run_id, goal, completeness, safety,
                               usefulness, efficiency, final_score, final_score >= 0.75, issues)
        self.store.append(asdict(report))
        return report


# ================================================================
# 5. StrategyEvolver — 策略演进
# ================================================================

