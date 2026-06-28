from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .action_guard import guard_action, classify_action
from .side_effect_proof import issue_registered_side_effect_proof
from .observability_event_bus import emit_event


@dataclass
class SideEffectRequest:
    action_type: str
    payload: Any = None
    risk_level: str = "low"
    entrypoint: str = "mainline"
    issuer: str = "personal_os_enterprise_core"
    explicit_approval: bool = False


def prepare_side_effect(
    *,
    action_type: str,
    payload: Any = None,
    risk_level: str = "low",
    entrypoint: str = "mainline",
    issuer: str = "personal_os_enterprise_core",
    root=None,
) -> Dict[str, Any]:
    """Canonical issuance path for any real side effect.

    The caller must pass the returned proof into guard_action / execute_side_effect.
    This separates plan/authorization from execution while preventing hand-written
    proof bypasses because the proof is registry-backed and one-time-use.
    """
    classification = classify_action(action_type)
    proof = issue_registered_side_effect_proof(
        action_type=action_type,
        payload=payload,
        risk_level=risk_level,
        entrypoint=entrypoint,
        issuer=issuer,
        root=root,
    )
    emit_event("side_effect_prepared", {
        "action_type": action_type,
        "request_id": proof.get("request_id"),
        "category": classification.get("category"),
        "risk_level": risk_level,
        "entrypoint": entrypoint,
    }, root=root)
    return {"proof": proof, "classification": classification}


def execute_side_effect(
    *,
    action_type: str,
    payload: Any = None,
    proof: Optional[Dict[str, Any]] = None,
    executor: Optional[Callable[[Any], Any]] = None,
    explicit_approval: bool = False,
    root=None,
) -> Dict[str, Any]:
    """Guard then execute a side effect.

    The executor is only called after action_guard allows the action. This function
    is intentionally small so file writes, provider calls, device calls, memory
    writes, and send operations can all share the same gate.
    """
    decision = guard_action(
        action_type=action_type,
        payload=payload,
        proof=proof,
        explicit_approval=explicit_approval,
        root=root,
    )
    if not decision.get("allowed"):
        emit_event("side_effect_execution_blocked", decision, root=root)
        return {"status": "blocked", "blocked": True, "guard": decision, "result": None}
    if executor is None:
        emit_event("side_effect_execution_allowed_noop", decision, root=root)
        return {"status": "allowed", "blocked": False, "guard": decision, "result": None}
    try:
        result = executor(payload)
        emit_event("side_effect_executed", {"action_type": action_type, "request_id": proof.get("request_id") if proof else "", "ok": True}, root=root)
        return {"status": "executed", "blocked": False, "guard": decision, "result": result}
    except Exception as exc:
        emit_event("side_effect_execution_failed", {"action_type": action_type, "error": str(exc)}, root=root)
        return {"status": "failed", "blocked": False, "guard": decision, "error": str(exc), "result": None}
