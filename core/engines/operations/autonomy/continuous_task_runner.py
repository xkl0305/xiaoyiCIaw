"""ContinuousTaskRunner (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class ContinuousTaskRunner:
    """持久化任务注册表 — 供外部调度器（cron）使用"""

    def __init__(self):
        self.store = JsonStore(os.path.join(STATE_DIR, "continuous_tasks.json"))

    def create(self, title: str, goal: str, cadence: str,
               next_run_hint: str = "") -> ContinuousTask:
        task = ContinuousTask(new_id("ctask"), title, goal, cadence,
                              "created", None, next_run_hint)
        self.store.append(asdict(task))
        return task

    def mark_run(self, task_id: str, status: TaskRunStatus,
                 metadata: Dict = None) -> ContinuousTask:
        data = self.store.read()
        for item in data:
            if item["id"] == task_id:
                item["status"] = status.value
                item["last_run_at"] = now_ts()
                item.setdefault("metadata", {}).update(metadata or {})
                self.store.write(data)
                return ContinuousTask(**item)
        raise KeyError(f"unknown task_id: {task_id}")

    def due(self) -> List[ContinuousTask]:
        due_status = {TaskRunStatus.CREATED.value, TaskRunStatus.PARTIAL.value,
                      TaskRunStatus.FAILED.value}
        return [ContinuousTask(**x) for x in self.store.read()
                if x.get("status") in due_status]

    def list_tasks(self) -> List[ContinuousTask]:
        return [ContinuousTask(**x) for x in self.store.read()]


# ================================================================
# 8. AutonomyCycle — 7阶段自治周期编排
# ================================================================

@dataclass
