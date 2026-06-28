from __future__ import annotations
from typing import Any, Dict


def augment_hook_payload(payload: Dict[str, Any], message: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Attach persona visual readiness to reply context.

    V111.20: never defines identity through prose. The payload only references
    the canonical avatar seed path and optionally includes a render plan.
    """
    try:
        from memory_context.persona_runtime.visual_persona_renderer import visual_summary_for_hook, plan_persona_visual, asdict_plan
        msg = message or payload.get("message") or payload.get("last_goal") or ""
        summary = visual_summary_for_hook(str(msg))
        payload["persona_visual_summary"] = summary
        if summary.get("explicit_visual_request_detected"):
            plan = plan_persona_visual(str(msg), user_explicit_request=True)
            payload["persona_visual_plan"] = asdict_plan(plan)
    except Exception as e:  # pragma: no cover
        payload.setdefault("warnings", []).append(f"persona_visual_hook_failed:{e}")
    return payload
