"""V111.24 persona visual prediction hook shim — delegates to the runtime."""
from __future__ import annotations
from typing import Any, Dict

try:
    from memory_context.persona_runtime.persona_visual_prediction_hook import run as _runtime_run
    
    def run(message: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return _runtime_run(message=message, context=context)

except Exception as e:
    def run(message: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "status": "shim_fail_soft",
            "error": str(e),
            "visual_suggestion_available": False,
            "visual_auto_generation_allowed": False,
            "visual_requires_confirmation": True,
        }
