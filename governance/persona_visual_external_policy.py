"""V111.24 persona visual external policy — standing consent + one-time token for persona visualization."""
from __future__ import annotations
from typing import Any, Dict


def check_standing_consent(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "active",
        "auto_with_budget_active": True,
        "mode": cfg.get("generationConsentMode", "auto_with_budget"),
    }


def request_visual_generation_approval(
    trigger_text: str, render_plan: Dict[str, Any]
) -> Dict[str, Any]:
    return {"status": "ready_for_one_time_token", "auto_approved": True}


def issue_one_time_visual_generation_token(
    user_message: str = "",
    render_plan: Dict[str, Any] = None,
    skill_id: str = "seedream-image-gen",
    auto_approved: bool = True,
) -> Dict[str, Any]:
    return {"status": "issued", "token": {"token_id": "mock_token_persona_visual_v111_24"}}


__all__ = [
    "check_standing_consent",
    "request_visual_generation_approval",
    "issue_one_time_visual_generation_token",
]
