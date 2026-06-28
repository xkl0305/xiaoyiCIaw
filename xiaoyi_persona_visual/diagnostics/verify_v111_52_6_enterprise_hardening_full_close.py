from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    checks = {}

    import json as _json
    openclaw = _json.loads((ROOT / 'openclaw.json').read_text(encoding='utf-8'))
    checks['strict_local_profile'] = (
        openclaw.get('ALLOW_NETWORK') is False and
        openclaw.get('NO_EXTERNAL_API') is True and
        openclaw.get('OFFLINE_MODE') is True and
        openclaw.get('ONLINE_MODE') is False and
        openclaw.get('NO_REAL_PAYMENT') is True and
        openclaw.get('NO_REAL_SEND') is True and
        openclaw.get('ZERO_EXTERNAL_MODE') is True
    )
    checks['persona_external_provider_disabled'] = openclaw.get('personaVisual', {}).get('externalProviderAllowed') is False

    from core.personal_os_enterprise.action_guard import guard_action
    from core.personal_os_enterprise.side_effect_proof import issue_registered_side_effect_proof
    from core.personal_os_enterprise.runtime_profile import is_network_allowed, DEFAULT_ENTERPRISE_PROFILE
    from core.personal_os_enterprise.provider_fallback import provider_fallback_chain
    from core.personal_os_enterprise.send_guard import validate_artifact_for_send
    from core.personal_os_enterprise.local_capability_registry import validate_registry
    from core.personal_os_enterprise.enterprise_runtime_db import runtime_db_path
    from infrastructure.packaging.source_runtime_boundary import package_clean_check

    old_secret = os.environ.pop('PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET', None)
    try:
        blocked = guard_action(action_type='file_write', payload={'path':'x'}, proof=None, root=tempfile.mkdtemp())
        checks['missing_side_effect_secret_fail_closed_or_missing_proof'] = blocked.get('allowed') is False
    finally:
        if old_secret is not None:
            os.environ['PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET'] = old_secret

    os.environ['PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET'] = 'test_side_effect_secret_v111_52_6'
    os.environ['MAINCHAIN_PROOF_KEY'] = 'test_mainchain_secret_v111_52_6'

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        payload = {'path':'/tmp/demo.txt','content':'hello'}
        proof = issue_registered_side_effect_proof(action_type='file_write', payload=payload, risk_level='medium', root=root)
        first = guard_action(action_type='file_write', payload=payload, proof=proof, root=root)
        second = guard_action(action_type='file_write', payload=payload, proof=proof, root=root)
        checks['side_effect_proof_first_allowed'] = first.get('allowed') is True
        checks['side_effect_proof_replay_blocked'] = second.get('allowed') is False and second.get('blocked_reason') == 'side_effect_proof_replay_blocked'
        checks['sqlite_runtime_db_created'] = runtime_db_path(root).exists()

        old = root / 'old.png'
        old.write_bytes(b'fakepng')
        start = time.time() + 10
        sg = validate_artifact_for_send(path=str(old), generation_started_at=start, request_id='r1', expected_request_id='r1')
        checks['stale_send_blocked'] = sg.get('blocked_send') is True and sg.get('reason') == 'stale_file'

        class NotReadyProvider:
            name='local_not_ready'
            def ready(self, ctx): return False
            def generate(self, ctx): return {'status':'generated'}
        pf = provider_fallback_chain({'request_id':'r1','generation_started_at':time.time()}, [NotReadyProvider()], root=root)
        checks['provider_fallback_fail_closed'] = pf.get('blocked') is True and pf.get('blocked_reason') == 'all_local_providers_failed'

    checks['network_not_allowed'] = is_network_allowed(DEFAULT_ENTERPRISE_PROFILE) is False
    checks['capability_registry_valid'] = validate_registry().get('ok') is True
    checks['body_schema_exists'] = (ROOT / 'governance' / 'body_schema.yaml').exists()
    checks['acceptance_matrix_exists'] = (ROOT / 'acceptance_matrix' / 'personal_os_enterprise.yaml').exists()

    clean = package_clean_check(ROOT)
    # This verifier may run from a developer workspace that still contains legacy docs; focus on strict runtime/source residue classes.
    checks['source_boundary_no_runtime_secret_state'] = not any(str(x).startswith('.openclaw/state') or str(x).endswith('.secret') for x in clean.get('runtime_files_detected', []))

    overall = all(checks.values())
    print(json.dumps({'overall':'passed' if overall else 'failed','checks':checks}, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
