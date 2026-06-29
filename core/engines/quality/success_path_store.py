"""
Crusheart Agent OS — Success Path Store
成功路径存储：记录成功执行的任务路径，供后续复用。
接入 JudgeEngine 的回写管道——当判定一次执行成功时记录路径。

v7.0: 激活为注册引擎，通过 save_success_path() 对外暴露。
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import os
import hashlib

@dataclass
class SuccessPath:
    """成功路径"""
    path_id: str
    goal_pattern: str
    plan: List[Dict[str, Any]]
    capabilities: List[str]
    skills: List[str]
    visual_paths: List[Dict[str, Any]]
    success_count: int = 1
    last_success_at: str = field(default_factory=lambda: datetime.now().isoformat())
    avg_time_ms: int = 0

class SuccessPathStore:
    """成功路径存储"""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            w = os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
            storage_path = os.path.join(w, ".state", "learning_loop", "success_paths.json")
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._paths: Dict[str, SuccessPath] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                for path_data in data.get("paths", []):
                    path = SuccessPath(**path_data)
                    self._paths[path.path_id] = path

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump({"paths": [p.__dict__ for p in self._paths.values()]},
                      f, ensure_ascii=False, indent=2)

    def record_success(self, goal_pattern: str, plan: List[Dict[str, Any]],
                       capabilities: List[str], skills: List[str],
                       visual_paths: List[Dict[str, Any]], elapsed_ms: int):
        for path in self._paths.values():
            if path.goal_pattern == goal_pattern and path.plan == plan:
                path.success_count += 1
                path.last_success_at = datetime.now().isoformat()
                path.avg_time_ms = (path.avg_time_ms * (path.success_count - 1) + elapsed_ms) // path.success_count
                self._save()
                return
        path_id = hashlib.md5(f"{goal_pattern}:{json.dumps(plan)}".encode()).hexdigest()[:12]
        path = SuccessPath(path_id=path_id, goal_pattern=goal_pattern, plan=plan,
                           capabilities=capabilities, skills=skills,
                           visual_paths=visual_paths, avg_time_ms=elapsed_ms)
        self._paths[path_id] = path
        self._save()

    def find_best_path(self, goal_pattern: str) -> Optional[SuccessPath]:
        candidates = [p for p in self._paths.values() if p.goal_pattern == goal_pattern]
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x.success_count, -x.avg_time_ms), reverse=True)
        return candidates[0]

    def get_all_patterns(self) -> List[str]:
        return list(set(p.goal_pattern for p in self._paths.values()))

    def stats(self) -> dict:
        return {"total_paths": len(self._paths), "patterns": len(self.get_all_patterns())}

# ── 引擎初始化入口 ──

def init() -> SuccessPathStore:
    """engines.json 调用的初始化入口"""
    global _instance
    if _instance is None:
        _instance = SuccessPathStore()
    return _instance

def get_store() -> SuccessPathStore:
    if _instance is None:
        return init()
    return _instance

def save_success_path(goal_pattern: str, plan: list, capabilities: list,
                      skills: list, visual_paths: list, elapsed_ms: int):
    """对外 API：供 JudgeEngine / pipeline 调用"""
    store = get_store()
    store.record_success(goal_pattern, plan, capabilities, skills, visual_paths, elapsed_ms)
