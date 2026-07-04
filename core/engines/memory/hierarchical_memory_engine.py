"""
HierarchicalMemoryEngine — 层次化记忆引擎 wrapper
功能：包装 galaxyos_modules.hierarchical_memory 为 crusheart 引擎
接线：memory_layer 引擎前做分级调度，减少冗余召回
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("hierarchical_memory_engine")

# 确保 galaxyos_modules 可导入
_SCRIPTS_DIR = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace/scripts")
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "galaxyos_modules"))

_ENGINE = None  # 单例


class HierarchicalMemoryEngine:
    """层次化记忆引擎包装器"""

    def __init__(self, db_path: Optional[str] = None):
        from hierarchical_memory import HierarchicalMemoryManager
        if db_path is None:
            workspace = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
            db_path = os.path.join(workspace, "memory", "hierarchical_memory.db")
        self._manager = HierarchicalMemoryManager(db_path=db_path)
        global _ENGINE
        _ENGINE = self
        logger.info(f"HierarchicalMemoryEngine 已初始化 (db={db_path})")

    def add(
        self,
        content: str,
        importance: Optional[float] = None,
        source: str = "conversation",
        tags: Optional[List[str]] = None,
        session_id: str = "",
    ) -> str:
        """添加新记忆"""
        return self._manager.add(content, importance, source, tags or [], session_id)

    def recall(self, query: str, top_k: int = 10) -> list:
        """分层召回记忆（优先工作集 → 近期集 → 归档集）"""
        return self._manager.recall(query, top_k)

    def get_working_set(self) -> list:
        return self._manager.get_working_set()

    def get_stats(self) -> dict:
        return {
            "working_set": len(self._manager.working_set),
            "recent_set": len(self._manager.recent_set),
            "archive_set": len(self._manager.archive_set),
        }

    def run_maintenance(self) -> dict:
        """执行层级维护（遗忘/合并/降级）"""
        return self._manager.run_maintenance()

    def status(self) -> dict:
        return {
            "name": "hierarchical_memory",
            "engine": "galaxyos_modules.hierarchical_memory.HierarchicalMemoryManager",
            "version": "1.0.0",
            "state": "initialized" if _ENGINE else "pending",
            "stats": self.get_stats(),
        }


def init(db_path: Optional[str] = None) -> HierarchicalMemoryEngine:
    """engines.json init_fn 入口"""
    return HierarchicalMemoryEngine(db_path)
