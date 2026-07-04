"""
RCCAMClassifierEngine — R-CCAM 查询分类引擎 wrapper
功能：包装 galaxyos_modules.rccam_classifier 为 crusheart 引擎
接线：hook_engine 前置钩子，用户输入时提前分流
"""

import os
import sys
import logging
from typing import Dict, Optional

logger = logging.getLogger("rccam_classifier_engine")

_SCRIPTS_DIR = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace/scripts")
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "galaxyos_modules"))

_ENGINE = None


class RCCAMClassifierEngine:
    """R-CCAM 查询分类引擎包装器"""

    def __init__(self):
        global _ENGINE
        _ENGINE = self
        logger.info("RCCAMClassifierEngine 已初始化")

    def classify(self, user_input: str) -> dict:
        """
        判定用户输入是否需要走完整管线

        返回:
            {
                "is_simple": bool,   # True=直答, False=走完整管线
                "confidence": float, # 判定置信度 (0~1)
                "method": str,       # "heuristic" | "ml" | "ml+fallback"
            }
        """
        from rccam_classifier import classify as _classify
        return _classify(user_input)

    def pre_hook(self, context: Dict) -> str:
        """
        前置钩子函数：hook_engine 注册用。
        context 应包含 {"content": "用户消息"}
        """
        content = context.get("content", "")
        if not content:
            return "pre_hook: empty content, skip"

        result = self.classify(content)
        context["rccam_classification"] = result

        if result["is_simple"]:
            return f"pre_hook: simple ({result['method']}, conf={result['confidence']:.2f})"
        else:
            return f"pre_hook: complex ({result['method']}, conf={result['confidence']:.2f})"

    def post_hook(self, context: Dict) -> str:
        """后置钩子：在 tool_execution_gateway 后再次确认分类质量（可选）"""
        return f"post_hook: rccam_classifier completed"

    def status(self) -> dict:
        return {
            "name": "rccam_classifier",
            "engine": "galaxyos_modules.rccam_classifier.classify",
            "version": "1.0.0",
            "state": "initialized" if _ENGINE else "pending",
        }


def init() -> RCCAMClassifierEngine:
    """engines.json init_fn 入口"""
    return RCCAMClassifierEngine()
