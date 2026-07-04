"""
鸽子王人格视觉出图引擎
功能：在引擎启动时注册 persona_visual 全管线
运行时：post_reply hook 感知对话情绪 → 匹配场景/衣柜/焦点 → 生成提示词 → seedream 生图
"""

import logging
import os
import sys
from typing import Dict, Any

logger = logging.getLogger("persona_visual_engine")

_ENGINE = None
_WORKSPACE = os.environ.get(
    "OPENCLAW_WORKSPACE",
    os.path.expanduser("~/.openclaw/workspace")
)


class PersonaVisualEngine:
    """人格视觉出图引擎包装器"""

    def __init__(self):
        sys.path.insert(0, _WORKSPACE)
        self._registered = False
        self._result = {}

    def initialize(self) -> Dict[str, Any]:
        """注册 persona_visual 全管线"""
        try:
            from xiaoyi_persona_visual.registry.register_persona_visual import register_persona_visual
            self._result = register_persona_visual()
            self._registered = self._result.get("registered", False)
            status = "ok" if self._registered else "failed"
            logger.info(f"persona_visual register: {status}")
            if self._registered:
                wardrobe_count = self._result.get("wardrobe_loaded", 0)
                self_check = self._result.get("self_check_ok", False)
                logger.info(f"  衣柜: {wardrobe_count}套 | 自检: {'✅' if self_check else '❌'}")
            return self._result
        except Exception as e:
            logger.error(f"persona_visual register failed: {e}")
            self._result = {"status": "error", "error": str(e)}
            return self._result

    def status(self) -> Dict[str, Any]:
        return {
            "name": "persona_visual",
            "version": "1.0.0",
            "state": "registered" if self._registered else "pending",
            "wardrobe": self._result.get("wardrobe_loaded", 0),
            "self_check": self._result.get("self_check_ok", False),
            "detail": {k: v for k, v in self._result.items()
                       if k not in ("status", "registered")},
        }

    def generate(self, text: str, mood: str = "", dry_run: bool = True) -> Dict[str, Any]:
        """辅助入口：传入对话文本，走完整管线生成出图请求"""
        try:
            from xiaoyi_persona_visual.helpers.generate_persona_visual_request import generate_persona_visual_request
            return generate_persona_visual_request(text=text, dry_run=dry_run)
        except ImportError:
            return {"status": "error", "error": "generate_persona_visual_request not available"}


def init() -> PersonaVisualEngine:
    """engines.json init_fn 入口"""
    global _ENGINE
    _ENGINE = PersonaVisualEngine()
    _ENGINE.initialize()
    return _ENGINE


def get_engine() -> PersonaVisualEngine:
    return _ENGINE
