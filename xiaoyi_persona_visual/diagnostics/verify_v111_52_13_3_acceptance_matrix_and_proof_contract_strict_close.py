#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_VERSION = 'V111.52.13.3_ACCEPTANCE_MATRIX_AND_PROOF_CONTRACT_STRICT_CLOSE_PATCH'
ACTIVE_VERSION = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _json(path: str) -> dict:
    return json.loads(_read(path))


def _clean() -> None:
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='.')
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault('MAINCHAIN_PROOF_KEY', 'local_test_mainchain_secret')
    os.environ.setdefault('PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET', 'local_test_side_effect_secret')
    _clean()
    checks = {}

    vj = _json('xiaoyi_persona_visual/version.json')
    checks['active_version_preserved'] = vj.get('version') == ACTIVE_VERSION
    checks['patch_feature_recorded'] = vj.get('features', {}).get('v111_52_13_3_patch_applied') == PATCH_VERSION

    run_all = _read('scripts/acceptance/run_all_enterprise_acceptance.sh')
    runner = _read('scripts/acceptance/enterprise_acceptance_runner.py')
    combined_runner = run_all + '\n' + runner
    required_pytest_targets = [
        'tests/acceptance',
        'tests/regression/test_ocr_vlm_consistency.py',
        'tests/regression/test_persona_visual_anatomy.py',
        'tests/regression/test_wardrobe_state.py',
    ]
    checks['run_all_executes_pytest_matrix'] = ('pytest' in combined_runner and all(t in combined_runner for t in required_pytest_targets))
    checks['run_all_calls_this_verifier'] = 'verify_v111_52_13_3_acceptance_matrix_and_proof_contract_strict_close.py' in combined_runner

    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof
    sig = inspect.signature(issue_mainchain_proof)
    checks['mainchain_issue_accepts_contract_args'] = all(k in sig.parameters for k in ['chain_id', 'entrypoint', 'policy_digest', 'issuer_version'])
    proof = issue_mainchain_proof(request_id='diag-r1', chain_id='diag-c1', entrypoint='diag', final_prompt='hello', reference_images=['a.png'], policy_digest='diag-policy', issuer_version='diag')
    checks['mainchain_proof_has_body_sig_and_legacy_token'] = isinstance(proof.get('body'), dict) and bool(proof.get('sig')) and bool(proof.get('proof_token'))
    checks['mainchain_body_fields_aligned'] = proof.get('body', {}).get('chain_id') == 'diag-c1' and proof.get('body', {}).get('entrypoint') == 'diag'

    from core.personal_os_enterprise.side_effect_registry import register_issued_proof, consume_issued_proof
    with tempfile.TemporaryDirectory() as td:
        reg = register_issued_proof('diag-replay', 'diag-token', 'payload', root=td)
        c1 = consume_issued_proof('diag-replay', 'diag-token', root=td)
        c2 = consume_issued_proof('diag-replay', 'diag-token', root=td)
    checks['side_registry_positional_replay_contract'] = reg.get('ok') is True and c1.get('ok') is True and c2.get('ok') is False and c2.get('reason') == 'side_effect_proof_replay_blocked'

    schema_path = ROOT / 'xiaoyi_persona_visual/policy/body_schema.yaml'
    schema_text = schema_path.read_text(encoding='utf-8') if schema_path.exists() else ''
    checks['body_schema_policy_path_exists'] = schema_path.exists()
    checks['body_schema_contains_tail_anchor'] = any(x in schema_text for x in ['tailbone', 'sacrum', '后腰']) and any(x in schema_text for x in ['floating', '漂浮'])
    builder = _read('xiaoyi_persona_visual/prompt/persona_image_prompt_builder.py')
    checks['body_schema_prompt_builder_injected'] = '_load_body_schema_block' in builder and "policy/body_schema.yaml" in builder and 'body_schema_loaded' in builder

    from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import build_structured_chinese_prompt
    body, meta = build_structured_chinese_prompt(base_prompt='背身展示尾巴', focus_target='tail')
    checks['body_schema_prompt_runtime_loaded'] = meta.get('body_schema_loaded') is True and ('tailbone' in body or '后腰' in body or 'sacrum' in body)

    model_hash_script = _read('scripts/verify_model_cache_hash.py')
    checks['model_hash_pending_not_fake_pass'] = 'pending_not_configured' in model_hash_script and 'blocked_missing_expected_sha256' in model_hash_script

    from core.personal_os_enterprise.local_model_stack_binding import local_stack_status
    stack = local_stack_status(ROOT)
    checks['local_model_stack_declares_all_8'] = len(stack.get('recommended_stack', {})) == 8 and stack.get('allow_external_fallback') is False
    checks['local_model_stack_missing_is_explicit'] = len(stack.get('missing', [])) >= 1 and stack.get('network_egress_attempted') is False

    from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
    img = persona_image_provider_chain_status({})
    checks['local_persona_image_fail_closed_until_configured'] = img.get('status') == 'blocked' and img.get('external_fallback_allowed') is False and img.get('fail_closed') is True

    from core.personal_os_enterprise.observability_ops import build_slo_report, METRIC_KEYS
    slo = build_slo_report(root=tempfile.mkdtemp())
    checks['observability_slo_catalog_present'] = slo.get('trace_coverage_ready') is True and len(METRIC_KEYS) >= 10

    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    _clean()
    clean = package_clean_check(ROOT)
    checks['package_clean'] = clean.get('clean') is True

    out = {
        'overall': 'passed' if all(checks.values()) else 'failed',
        'patch_version': PATCH_VERSION,
        'active_version': vj.get('version'),
        'checks': checks,
        'local_model_stack_status': {
            'ready': stack.get('ready'),
            'missing': stack.get('missing'),
            'allow_external_fallback': stack.get('allow_external_fallback'),
        },
        'package_clean': clean,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    _rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_rc)
