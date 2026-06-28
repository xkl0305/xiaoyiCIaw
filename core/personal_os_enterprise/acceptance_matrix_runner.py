from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from .action_guard import guard_action
from .local_capability_registry import assert_declared_capabilities, list_capabilities
from .observability_event_bus import emit_event, read_events
from .runtime_profile import load_enterprise_profile, load_offline_profile
from .side_effect_proof import issue_registered_side_effect_proof
from infrastructure.packaging.source_runtime_boundary import is_runtime_path, package_clean_check


def _issue_and_register(action_type: str, payload: Any, root: Path, risk_level: str = "low"):
    return issue_registered_side_effect_proof(action_type=action_type, payload=payload, risk_level=risk_level, entrypoint="acceptance_matrix", root=root)


def run_acceptance_matrix(root=None) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as td:
        temp_root = Path(td)
        online_profile = load_enterprise_profile(root=temp_root)
        offline_profile = load_offline_profile(root=temp_root)

        payload = {"path": "notes/demo.txt"}
        proof = _issue_and_register("file_write", payload, temp_root)
        checks["read_only_allowed"] = guard_action(action_type="read_file", payload={}, root=temp_root).get("allowed") is True
        checks["side_effect_without_proof_blocked"] = guard_action(action_type="file_write", payload=payload, root=temp_root).get("blocked_reason") == "missing_side_effect_proof"
        checks["side_effect_with_proof_allowed"] = guard_action(action_type="file_write", payload=payload, proof=proof, root=temp_root).get("allowed") is True
        checks["proof_replay_blocked"] = guard_action(action_type="file_write", payload=payload, proof=proof, root=temp_root).get("blocked_reason") == "side_effect_proof_replay_blocked"

        network_payload = {"provider": "seedream", "operation": "generate"}
        network_proof = _issue_and_register("provider_call", network_payload, temp_root)
        checks["network_default_online_not_offline_blocked"] = guard_action(action_type="provider_call", payload=network_payload, proof=network_proof, enterprise_profile=online_profile, root=temp_root).get("allowed") is True
        checks["network_explicit_offline_blocked"] = guard_action(action_type="provider_call", payload=network_payload, enterprise_profile=offline_profile, root=temp_root).get("blocked_reason") == "network_disabled_by_active_profile"

        send_payload = {"channel": "chat", "text": "hello"}
        send_proof = _issue_and_register("send_message", send_payload, temp_root, risk_level="high")
        checks["high_risk_requires_approval"] = guard_action(action_type="send_message", payload=send_payload, proof=send_proof, enterprise_profile=online_profile, root=temp_root).get("blocked_reason") == "high_risk_requires_explicit_approval"
        checks["high_risk_with_approval_allowed"] = guard_action(action_type="send_message", payload=send_payload, proof=send_proof, enterprise_profile=online_profile, explicit_approval=True, root=temp_root).get("allowed") is True

        emit_event("acceptance_probe", {"version": "V111.52.3_SIDE_EFFECT_PROOF_FULL_FUSION"}, root=temp_root)
        checks["observability_jsonl_written"] = bool(read_events(root=temp_root))
        checks["runtime_boundary_detects_state"] = is_runtime_path(".openclaw/state/secret.txt") is True
        checks["package_clean_excludes_runtime_state"] = package_clean_check(temp_root).get("clean") is True

    profile = load_enterprise_profile(root=root)
    checks["default_profile_online"] = profile.get("ONLINE_MODE") is True and profile.get("ALLOW_NETWORK") is True and profile.get("OFFLINE_MODE") is False
    checks["capabilities_declared"] = assert_declared_capabilities().get("ok") is True and "provider_bridge" in list_capabilities()

    overall = all(checks.values())
    return {"overall": "passed" if overall else "failed", "checks": checks}
