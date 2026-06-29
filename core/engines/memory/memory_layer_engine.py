"""
Crusheart Agent OS — 记忆层级引擎（兼容层）
所有逻辑已合并到 auto_memory.py，此文件仅保留兼容导入别名。
"""

from core.engines.memory.auto_memory import (
    CORE_ANCHOR_KEYWORDS,
    BEIJING_TZ as _,
    detect_memory_instruction,
    force_core_anchor_by_instruction,
    is_noise_content,
)

class MemoryLayerEngine:
    """兼容别名 — 已内联到 AutoMemory"""
    def __init__(self, workspace=None):
        from core.engines.memory.auto_memory import AutoMemory
        self._impl = AutoMemory()
        self.workspace = self._impl.workspace
        self.memory_dir = None
        self.long_term_file = None

    def __getattr__(self, name):
        return getattr(self._impl, name)

    def get_memory_report(self):
        return {
            "layers": {
                "L1_session": "对话上下文中",
                "L2_daily": 0,
                "L3_longterm": "MEMORY.md",
                "L4_vector": "TF-IDF增强版"
            },
            "core_anchors": len(CORE_ANCHOR_KEYWORDS),
            "instruction_detection": True,
            "maintenance_window": "23:00-23:59",
            "decay_threshold_days": {"attenuate": 30, "archive": 90},
            "anchor_exemption": True
        }


def get_preloaded_anchors():
    from core.engines.memory.auto_memory import AutoMemory
    return AutoMemory().get_preloaded_anchors()
