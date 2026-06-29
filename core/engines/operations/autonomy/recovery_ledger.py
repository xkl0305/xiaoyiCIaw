"""RecoveryLedger (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class RecoveryLedger:
    """检查点+回滚计划的交易账本"""

    def __init__(self):
        self.store = JsonStore(os.path.join(STATE_DIR, "recovery_ledger.json"))

    def record_checkpoint(self, run_id: str, action: str, checkpoint: Dict,
                          rollback_plan: str = "", reversible: bool = True) -> RecoveryEntry:
        entry = RecoveryEntry(new_id("recovery"), run_id, action, checkpoint,
                              rollback_plan, reversible, now_ts())
        self.store.append(asdict(entry))
        return entry

    def list_run(self, run_id: str) -> List[RecoveryEntry]:
        return [RecoveryEntry(**x) for x in self.store.read() if x.get("run_id") == run_id]

    def resume_hint(self, run_id: str) -> Dict:
        entries = self.list_run(run_id)
        if not entries:
            return {"can_resume": False, "reason": "no_checkpoint"}
        last = entries[-1]
        return {
            "can_resume": True,
            "last_action": last.action,
            "rollback_plan": last.rollback_plan,
            "reversible": last.reversible,
        }


# ================================================================
# 7. ContinuousTaskRunner — 持久化任务注册表
# ================================================================

@dataclass
