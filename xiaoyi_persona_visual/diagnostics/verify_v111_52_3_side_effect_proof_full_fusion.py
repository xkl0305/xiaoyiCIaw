from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.personal_os_enterprise import SYSTEM_VERSION
from core.personal_os_enterprise.action_guard import guard_action
from core.personal_os_enterprise.side_effect_gateway import prepare_side_effect, execute_side_effect
from core.personal_os_enterprise.guarded_actions import prepare_file_write, guarded_file_write
from core.personal_os_enterprise.local_capability_registry import list_capabilities, assert_declared_capabilities
from core.personal_os_enterprise.observability_event_bus import read_events

EXPECTED_VERSION = "V111.52.3_SIDE_EFFECT_PROOF_FULL_FUSION"
ACCEPTED_DESCENDANT_VERSIONS = {
    "V111.52.4_SIDE_EFFECT_FUSION_CLEAN_REPAIR_FINAL",
    "V111.52.5_SECRET_CLEAN_RUNTIME_PROOF_FINAL",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        checks = {}
        checks["system_version"] = SYSTEM_VERSION == EXPECTED_VERSION

        payload = {"path": "demo.txt", "content_sha_hint": 4}
        missing = guard_action(action_type="file_write", payload=payload, proof=None, root=root)
        checks["missing_proof_blocks"] = missing.get("blocked_reason") == "missing_side_effect_proof"

        prepared = prepare_side_effect(action_type="file_write", payload=payload, risk_level="medium", entrypoint="verify", root=root)
        proof = prepared.get("proof")
        allowed = guard_action(action_type="file_write", payload=payload, proof=proof, root=root)
        checks["registered_proof_allows_once"] = allowed.get("allowed") is True
        replay = guard_action(action_type="file_write", payload=payload, proof=proof, root=root)
        checks["proof_replay_blocks"] = replay.get("blocked_reason") == "side_effect_proof_replay_blocked"

        high_prepared = prepare_side_effect(action_type="config_change", payload={"k":"v"}, risk_level="high", entrypoint="verify", root=root)
        high_block = guard_action(action_type="config_change", payload={"k":"v"}, proof=high_prepared.get("proof"), root=root)
        checks["high_risk_needs_approval"] = high_block.get("blocked_reason") == "high_risk_requires_explicit_approval"
        high_prepared2 = prepare_side_effect(action_type="config_change", payload={"k":"v2"}, risk_level="high", entrypoint="verify", root=root)
        high_ok = guard_action(action_type="config_change", payload={"k":"v2"}, proof=high_prepared2.get("proof"), explicit_approval=True, root=root)
        checks["high_risk_with_approval_allows"] = high_ok.get("allowed") is True

        counter = {"called": 0}
        def executor(_):
            counter["called"] += 1
            return {"ok": True}
        blocked_exec = execute_side_effect(action_type="memory_write", payload={"key":"x"}, proof=None, executor=executor, root=root)
        checks["blocked_executor_not_called"] = blocked_exec.get("blocked") is True and counter["called"] == 0
        mem_payload = {"key":"x"}
        mem_prep = prepare_side_effect(action_type="memory_write", payload=mem_payload, risk_level="medium", entrypoint="verify", root=root)
        ok_exec = execute_side_effect(action_type="memory_write", payload=mem_payload, proof=mem_prep.get("proof"), executor=executor, root=root)
        checks["allowed_executor_called"] = ok_exec.get("status") == "executed" and counter["called"] == 1

        target = root / "out" / "guarded.txt"
        write_prep = prepare_file_write(target, "hello", root=root)
        write_res = guarded_file_write(target, "hello", proof=write_prep.get("proof"), root=root)
        checks["guarded_file_write"] = write_res.get("status") == "executed" and target.read_text(encoding="utf-8") == "hello"

        caps = list_capabilities()
        checks["capability_registry_fused"] = all(k in caps for k in ["guarded_file_write", "guarded_memory_write", "guarded_provider_call", "guarded_device_action", "side_effect_gateway"])
        checks["capability_registry_valid"] = assert_declared_capabilities().get("ok") is True

        events = read_events(limit=100, root=root)
        event_types = {e.get("event_type") for e in events}
        checks["observability_events"] = {"side_effect_proof_issued", "action_guard_allowed", "action_guard_blocked", "side_effect_executed"}.issubset(event_types)

        manifest = json.loads(Path("release_manifest.json").read_text(encoding="utf-8")) if Path("release_manifest.json").exists() else {}
        checks["release_manifest_version"] = manifest.get("version") in {EXPECTED_VERSION, *ACCEPTED_DESCENDANT_VERSIONS}

        failure = json.loads(Path("governance/failure_pattern_registry.json").read_text(encoding="utf-8")) if Path("governance/failure_pattern_registry.json").exists() else {}
        patterns = set(failure.get("guarded_failure_patterns", []))
        checks["failure_patterns_include_side_effects"] = {"side_effect_without_registered_proof", "unobserved_side_effect_execution", "proof_forgery_or_replay"}.issubset(patterns)

        overall = all(checks.values())
        print(json.dumps({"overall": "passed" if overall else "failed", "version": EXPECTED_VERSION, "checks": checks}, ensure_ascii=False, indent=2))
        return 0 if overall else 1

if __name__ == "__main__":
    raise SystemExit(main())
