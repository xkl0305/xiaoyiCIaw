"""
HallucinationGuardEngine — 防幻觉守护引擎 wrapper
功能：包装 galaxyos_modules.hallucination_guard 为 crusheart 引擎
接线：quality 管线输出验证环节，挂到 hook_engine 的 post_hook
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("hallucination_guard_engine")

_SCRIPTS_DIR = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace/scripts")
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "galaxyos_modules"))

_ENGINE = None


class HallucinationGuardEngine:
    """防幻觉守护引擎包装器"""

    def __init__(self):
        from hallucination_guard import HallucinationGuard
        self._guard = HallucinationGuard()
        global _ENGINE
        _ENGINE = self
        logger.info("HallucinationGuardEngine 已初始化")

    def validate_output(self, content: str, context: Optional[Dict] = None) -> dict:
        """
        验证输出内容是否有幻觉风险

        返回:
            {
                "passed": bool,
                "risk_level": str,      # "low" / "medium" / "high"
                "issues": List[str],
                "confidence": float,
            }
        """
        ctx = context or {}
        # guard.validate_output() 返回 VerifiedMemory 或类似对象
        result = self._guard.validate_output(content)

        if hasattr(result, "to_dict"):
            result_dict = result.to_dict()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {"passed": True, "detail": str(result)}

        return {
            "passed": result_dict.get("passed", True),
            "risk_level": result_dict.get("risk_level", "low"),
            "issues": result_dict.get("issues", []),
            "confidence": result_dict.get("confidence", 1.0),
        }

    def check_familiarity(self, content: str) -> dict:
        """检查内容的自熟悉度（是否有已知源支撑）"""
        result = self._guard.self_familiarity_checker.check(content)
        return {
            "familiar": getattr(result, "familiar", True),
            "source_count": getattr(result, "source_count", 0),
            "confidence": getattr(result, "confidence", 1.0),
        }

    def status(self) -> dict:
        return {
            "name": "hallucination_guard",
            "engine": "galaxyos_modules.hallucination_guard.HallucinationGuard",
            "version": "1.0.0",
            "state": "initialized" if _ENGINE else "pending",
        }


def init() -> HallucinationGuardEngine:
    """engines.json init_fn 入口"""
    return HallucinationGuardEngine()
