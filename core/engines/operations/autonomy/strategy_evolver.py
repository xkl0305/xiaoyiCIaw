"""StrategyEvolver (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class StrategyEvolver:
    """质量驱动的策略自动演进"""

    def __init__(self):
        self.store = JsonStore(os.path.join(STATE_DIR, "strategy_rules.json"))
        self._ensure_defaults()

    def _ensure_defaults(self):
        if self.store.read():
            return
        defaults = [
            StrategyRule(new_id("rule"), "prefer_plan_first", "complexity>=medium",
                         "compile_goal_before_tool_use", 1.0),
            StrategyRule(new_id("rule"), "approval_for_external_side_effect",
                         "risk>=L3", "interrupt_for_approval", 1.0),
            StrategyRule(new_id("rule"), "write_memory_after_success",
                         "quality>=0.75", "write_episodic_and_procedure_memory", 0.8),
        ]
        self.store.write([asdict(r) for r in defaults])

    def evolve_from_quality(self, report: QualityReport) -> List[StrategyRule]:
        data = self.store.read()
        changed = []
        if report.final_score < 0.75:
            # 避免累积无效 rule：检查是否已有同类 rule
            existing = [i for i, item in enumerate(data)
                        if item.get("name", "").startswith("repair_low_quality")]
            if len(existing) >= 5:
                # 超过上限不再追加
                pass
            elif existing:
                idx = existing[-1]
                data[idx]["weight"] = min(1.5, float(data[idx].get("weight", 0.6)) + 0.1)
                data[idx]["updated_at"] = now_ts()
            else:
                rule = StrategyRule(new_id("rule"),
                                    f"repair_low_quality::{report.run_id}",
                                    f"run_id=={report.run_id}",
                                    f"address_issues::{','.join(report.issues) or 'general_quality'}",
                                    0.6)
                data.append(asdict(rule))
                changed.append(rule)
        else:
            for item in data:
                if item.get("name") == "write_memory_after_success":
                    item["weight"] = min(1.5, float(item.get("weight", 1.0)) + 0.05)
                    item["updated_at"] = now_ts()
                    changed.append(StrategyRule(**item))
        self.store.write(data)
        return changed

    def list_rules(self, enabled_only: bool = True) -> List[StrategyRule]:
        rules = [StrategyRule(**x) for x in self.store.read()]
        return [r for r in rules if r.enabled] if enabled_only else rules


# ================================================================
# 6. RecoveryLedger — 检查点回滚账本
# ================================================================

@dataclass
