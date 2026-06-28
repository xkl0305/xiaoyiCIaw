from __future__ import annotations

from typing import Any, Dict, Optional

from .runtime_profile import DEFAULT_ENTERPRISE_PROFILE, is_network_allowed
from .side_effect_proof import validate_side_effect_proof
from .runtime_secret_provider import MissingRuntimeSecretError
from .side_effect_registry import consume_issued_proof
from .observability_event_bus import emit_event

READ_ONLY_ACTIONS = {
    "read_file", "search", "inspect", "summarize", "classify", "dry_run", "list_state",
    "calendar_search", "contacts_search", "memory_read", "capability_list", "health_check",
    "verify", "validate", "read_config", "list_files",
}

NETWORK_ACTIONS = {
    "network_call", "external_api_call", "provider_call", "web_request", "connector_call",
    "image_generation", "seedream_generation", "model_provider_call",
}

HIGH_RISK_ACTIONS = {
    "file_delete", "payment", "config_change", "shell_exec", "device_control",
    "send_message", "calendar_delete", "contact_modify", "credential_write",
    "delete_state", "execute_script",
}

MEDIUM_RISK_PROOF_ONLY_ACTIONS = {
    "file_write", "memory_write", "memo_append", "calendar_create", "alarm_create",
    "reminder_create", "hiboard_push", "chat_cron", "tool_call", "provider_call",
    "local_provider_call", "network_call", "external_api_call", "web_request", "connector_call",
    "image_generation", "seedream_generation", "model_provider_call", "send_image",
    "write_config", "state_write", "cache_write", "ledger_append", "device_action",
}

SIDE_EFFECT_ACTIONS = HIGH_RISK_ACTIONS | MEDIUM_RISK_PROOF_ONLY_ACTIONS


def _emit(event_type: str, payload: Dict[str, Any], root=None) -> None:
    try:
        emit_event(event_type, payload, root=root)
    except Exception:
        pass


def classify_action(action_type: str) -> Dict[str, Any]:
    action_type = str(action_type or "")
    if action_type in READ_ONLY_ACTIONS:
        return {"category": "read_only", "requires_proof": False, "requires_approval": False}
    if action_type in HIGH_RISK_ACTIONS:
        return {"category": "high_risk_side_effect", "requires_proof": True, "requires_approval": True}
    if action_type in MEDIUM_RISK_PROOF_ONLY_ACTIONS:
        return {"category": "medium_risk_side_effect", "requires_proof": True, "requires_approval": False}
    return {"category": "unknown_side_effect", "requires_proof": True, "requires_approval": False}


def guard_action(
    *,
    action_type: str,
    payload: Any = None,
    proof: Optional[Dict[str, Any]] = None,
    enterprise_profile: Optional[Dict[str, Any]] = None,
    offline_profile: Optional[Dict[str, Any]] = None,
    explicit_approval: bool = False,
    root=None,
) -> Dict[str, Any]:
    """Decide whether an action can execute.

    V111.52.3: every real side effect is denied by default unless a registered,
    one-time side_effect_proof is present. Read-only actions remain allowed.
    """
    profile = enterprise_profile or offline_profile or DEFAULT_ENTERPRISE_PROFILE
    action_type = str(action_type or "")
    classification = classify_action(action_type)

    if classification["category"] == "read_only":
        out = {"allowed": True, "reason": "read_only_action", "action_type": action_type, **classification}
        _emit("action_guard_allowed", out, root=root)
        return out

    if action_type in NETWORK_ACTIONS and not is_network_allowed(profile):
        out = {"allowed": False, "blocked": True, "blocked_reason": "network_disabled_by_active_profile", "action_type": action_type, **classification}
        _emit("action_guard_blocked", out, root=root)
        return out

    if classification.get("requires_approval") and profile.get("HIGH_RISK_REQUIRES_APPROVAL", True) and not explicit_approval:
        out = {"allowed": False, "blocked": True, "blocked_reason": "high_risk_requires_explicit_approval", "action_type": action_type, **classification}
        _emit("action_guard_blocked", out, root=root)
        return out

    if classification.get("requires_proof") or profile.get("REQUIRE_SIDE_EFFECT_PROOF", True):
        try:
            validation = validate_side_effect_proof(proof, action_type=action_type, payload=payload, root=root)
        except MissingRuntimeSecretError as exc:
            validation = {"valid": False, "reason": "missing_runtime_secret", "error": str(exc)}
        if not validation.get("valid"):
            out = {"allowed": False, "blocked": True, "blocked_reason": validation.get("reason"), "action_type": action_type, **classification}
            _emit("action_guard_blocked", out, root=root)
            return out
        consumed = consume_issued_proof(proof, root=root)
        if not consumed.get("valid"):
            out = {"allowed": False, "blocked": True, "blocked_reason": consumed.get("reason"), "action_type": action_type, **classification}
            _emit("action_guard_blocked", out, root=root)
            return out
        out = {"allowed": True, "reason": "side_effect_proof_valid", "action_type": action_type, "request_id": proof.get("request_id"), **classification}
        _emit("action_guard_allowed", out, root=root)
        return out

    out = {"allowed": True, "reason": "non_side_effect_action", "action_type": action_type, **classification}
    _emit("action_guard_allowed", out, root=root)
    return out
