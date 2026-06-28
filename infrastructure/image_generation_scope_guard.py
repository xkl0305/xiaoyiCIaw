from __future__ import annotations
from typing import Any, Dict
def can_use_persona_seed(scope: str = "", purpose: str = "", **kwargs: Any) -> Dict[str, Any]:
    ok = scope == "persona_scene_auto_only" or purpose == "persona_visualization"
    return {
        "allowed": ok,
        "reason": "persona_seed_allowed" if ok else "persona_seed_forbidden_for_generic_image_generation",
    }
def assert_persona_seed_scope(scope: str = "", purpose: str = "") -> None:
    r = can_use_persona_seed(scope, purpose)
    if not r["allowed"]:
        raise PermissionError(r["reason"])
