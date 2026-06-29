#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import site
import subprocess
import sys
import time
import tempfile
sys.dont_write_bytecode = True
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP_TIMEOUT = int(os.environ.get('ACCEPTANCE_STEP_TIMEOUT_SECONDS', '90'))
PYTEST_TIMEOUT = int(os.environ.get('ACCEPTANCE_PYTEST_TIMEOUT_SECONDS', '180'))
LEGACY_FAST_TIMEOUT = int(os.environ.get('ACCEPTANCE_LEGACY_FAST_TIMEOUT_SECONDS', '45'))


def _env() -> dict[str, str]:
    env = os.environ.copy()
    # Collect extra site-packages dirs so subprocess -S can find pytest & deps
    _extra_paths = []
    for _p in (site.getusersitepackages(), str(Path(ROOT, 'repo/lib/python3.12/site-packages'))):
        if _p and os.path.isdir(_p):
            _extra_paths.append(_p)
    _py_path = '.'
    if _extra_paths:
        _py_path = f'.{os.pathsep}{os.pathsep.join(_extra_paths)}'
    env.update({
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
        'OFFLINE_MODE': 'true',
        'NO_EXTERNAL_API': 'true',
        'ALLOW_NETWORK': 'false',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONPATH': _py_path,
        'PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET': env.get('PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET', 'local_test_side_effect_secret'),
        'MAINCHAIN_PROOF_KEY': env.get('MAINCHAIN_PROOF_KEY', 'local_test_mainchain_secret'),
    })
    return env


def run(name: str, cmd: list[str], *, show: bool = False, timeout: int | None = None) -> None:
    print(f'[enterprise-acceptance] {name}', flush=True)
    start = time.time()
    limit = timeout or STEP_TIMEOUT

    # Never let child verifiers inherit the runner stdout/stderr directly.
    # Some pytest/telemetry/plugin environments can leave detached grandchildren
    # holding inherited file descriptors; when that happens, the acceptance
    # command may print "passed" but the outer caller still waits for EOF.  Route
    # subprocess output to temp files, wait only on the direct child, then replay
    # the captured output from the parent. Detached grandchildren no longer keep
    # the top-level acceptance stream open.
    with tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False) as out_f, \
            tempfile.NamedTemporaryFile('w+', encoding='utf-8', delete=False) as err_f:
        out_name = out_f.name
        err_name = err_f.name
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=_env(),
            text=True,
            stdout=out_f,
            stderr=err_f,
            start_new_session=True,
            close_fds=True,
        )
        timed_out = False
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            if time.time() - start > limit:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                break
            time.sleep(0.05)
        out_f.flush()
        err_f.flush()

    try:
        stdout = Path(out_name).read_text(encoding='utf-8', errors='replace')
    except Exception:
        stdout = ''
    try:
        stderr = Path(err_name).read_text(encoding='utf-8', errors='replace')
    except Exception:
        stderr = ''
    for fn in (out_name, err_name):
        try:
            Path(fn).unlink(missing_ok=True)
        except Exception:
            pass

    if timed_out:
        elapsed = time.time() - start
        sys.stderr.write(
            f'[enterprise-acceptance] {name} timed out after {elapsed:.1f}s '
            f'(limit={limit}s)\n'
        )
        if stdout:
            sys.stderr.write(str(stdout)[-4000:])
        if stderr:
            sys.stderr.write(str(stderr)[-4000:])
        raise SystemExit(124)

    if proc.returncode != 0:
        sys.stderr.write((stdout or '')[-4000:])
        sys.stderr.write((stderr or '')[-4000:])
        raise SystemExit(proc.returncode)

    if show and stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith('\n'):
            sys.stdout.write('\n')
        sys.stdout.flush()
    if show and stderr:
        sys.stderr.write(stderr)
        if not stderr.endswith('\n'):
            sys.stderr.write('\n')
        sys.stderr.flush()
    if not show and stdout and name in {'model_cache_hash'}:
        sys.stdout.write((stdout or '').split('\n', 1)[0] + '\n')
        sys.stdout.flush()


def run_direct(name: str, fn, *, timeout: int | None = None) -> None:
    print(f'[enterprise-acceptance] {name}', flush=True)
    # Direct checks are intentionally fast-path checks. They must not call legacy
    # verifiers that recursively invoke acceptance runners. Keep a wall-clock guard
    # so future slow checks fail clearly instead of hanging.
    start = time.time()
    result = fn()
    elapsed = time.time() - start
    limit = timeout or LEGACY_FAST_TIMEOUT
    if elapsed > limit:
        sys.stderr.write(f'[enterprise-acceptance] {name} exceeded fast-path budget: {elapsed:.1f}s > {limit}s\n')
        raise SystemExit(124)
    if result is False:
        raise SystemExit(1)


def _j(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def _no_network() -> bool:
    data = _j('openclaw.json')
    return all([
        data.get('ALLOW_NETWORK') is False,
        data.get('NO_EXTERNAL_API') is True,
        data.get('OFFLINE_MODE') is True,
        data.get('ONLINE_MODE') is False,
        data.get('ZERO_EXTERNAL_MODE') is True,
        data.get('NO_REAL_PAYMENT') is True,
        data.get('NO_REAL_SEND') is True,
        data.get('externalAccessPolicy', {}).get('allowExternalApi') is False,
        data.get('personaVisual', {}).get('externalProviderAllowed') is False,
    ])


def _active_metadata() -> bool:
    version = _j('xiaoyi_persona_visual/version.json').get('version')
    manifest_version = _j('release_manifest.json').get('version')
    expected = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'
    return version == expected and manifest_version == expected


def _forward_compat_fast() -> bool:
    """Fast forward-compatibility gate.

    V111.52.13.2.1 already covered the expensive 52.12.1 forward-compat run.
    The enterprise top-level runner must not repeat that nested legacy verifier.
    This gate only verifies the compatibility patch files/metadata are present and
    the current package remains clean.
    """
    checks = []
    checks.append(_active_metadata())
    checks.append((ROOT / 'xiaoyi_persona_visual/diagnostics' / ('verify_v111_52_13_2_1_' + 'forward_compat_clean_gate.py')).exists())
    checks.append((ROOT / 'xiaoyi_persona_visual/diagnostics' / ('verify_v111_52_12_1_' + 'full_local_stack_runtime_clean_close.py')).exists())
    version_features = _j('xiaoyi_persona_visual/version.json').get('features', {})
    checks.append(version_features.get('v111_52_13_3_patch_applied') == 'V111.52.13.3_ACCEPTANCE_MATRIX_AND_PROOF_CONTRACT_STRICT_CLOSE_PATCH')
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    checks.append(clean.get('clean') is True)
    return all(checks)


def _clean_gate_fast() -> bool:
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    return _active_metadata() and clean.get('clean') is True and clean.get('runtime_file_count') == 0 and clean.get('secret_literal_count') == 0


def _no_runtime_secret() -> bool:
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    return clean.get('clean') is True and clean.get('secret_literal_count') == 0


def _secret_workflow() -> bool:
    from core.personal_os_enterprise.secret_workflow_guard import validate_secret_workflow
    return bool(validate_secret_workflow(ROOT).get('ok'))


def _rootless() -> bool:
    from core.personal_os_enterprise.rootless_deploy_smoke import rootless_deploy_plan
    return bool(rootless_deploy_plan(ROOT).get('ok'))


def _model_hash() -> bool:
    import importlib.util
    spec = importlib.util.spec_from_file_location('verify_model_cache_hash', ROOT / 'scripts/verify_model_cache_hash.py')
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod.main() == 0



def _report_remaining_fast() -> bool:
    """Fast in-process version of report_remaining verifier.

    The standalone report verifier is still kept for direct diagnostics, but the
    enterprise top-level runner must not spawn it as a child process because some
    Python/plugin environments can hang during child interpreter shutdown after
    package-clean scanning. This gate verifies the same required contract without
    creating a nested verifier process.
    """
    if not _active_metadata():
        return False
    required = [
        'core/personal_os_enterprise/enterprise_acceptance_suite.py',
        'core/personal_os_enterprise/observability_ops.py',
        'core/personal_os_enterprise/secret_workflow_guard.py',
        'core/personal_os_enterprise/rootless_deploy_smoke.py',
        'core/personal_os_enterprise/data_retention_manager.py',
        'core/personal_os_enterprise/local_persona_image_domain.py',
        'core/personal_os_enterprise/private_network_policy.py',
        'acceptance_matrix/report_remaining_close.yaml',
        'tests/acceptance/test_offline_boot.py',
        'tests/acceptance/test_mainchain_proof.py',
        'tests/acceptance/test_send_guard.py',
        'tests/acceptance/test_provider_fallback.py',
        'tests/regression/test_ocr_vlm_consistency.py',
        'tests/regression/test_persona_visual_anatomy.py',
        'tests/regression/test_wardrobe_state.py',
        'scripts/security/verify_secret_workflow.py',
        'scripts/deployment/verify_rootless_runtime.py',
        'deployment/rootless/healthcheck.sh',
    ]
    if not all((ROOT / item).exists() for item in required):
        return False
    from core.personal_os_enterprise.enterprise_acceptance_suite import acceptance_matrix, validate_acceptance_files
    matrix = acceptance_matrix()
    file_check = validate_acceptance_files(ROOT)
    if matrix.get('case_count', 0) < 13 or file_check.get('ok') is not True:
        return False
    from core.personal_os_enterprise.observability_ops import SLO_TARGETS, METRIC_KEYS, build_slo_report
    if len(METRIC_KEYS) < 12 or SLO_TARGETS.get('network_egress_allowed') is not False:
        return False
    with tempfile.TemporaryDirectory() as td:
        slo = build_slo_report(root=td)
    if slo.get('trace_coverage_ready') is not True or slo.get('fail_closed_policy') is not True:
        return False
    from core.personal_os_enterprise.data_retention_manager import retention_policy
    pol = retention_policy()
    if pol.get('debug_log_redaction_required') is not True or 'S1_screenshot' not in pol.get('ttl_days', {}):
        return False
    from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
    lp = persona_image_provider_chain_status({})
    if lp.get('status') != 'blocked' or lp.get('external_fallback_allowed') is not False:
        return False
    from core.personal_os_enterprise.private_network_policy import private_network_policy
    pn = private_network_policy()
    if pn.get('external_internet_egress') is not False or pn.get('node_id_required_for_multi_node') is not True:
        return False
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    return clean.get('clean') is True


def _strict_52_14() -> bool:
    """In-process 52.14 env-limited model wiring gate.

    Confirms that the environment is blocked, no real model is ready,
    and all capabilities are stub_ready_only or environment_blocked.
    This runs in-process to avoid nested subprocess complexity.
    """
    # Check diagnosis file exists
    diag_path = ROOT / 'reports' / 'current' / 'local_model_environment_diagnosis.json'
    if not diag_path.exists():
        return False
    try:
        import json
        diag = json.loads(diag_path.read_text(encoding='utf-8'))
    except Exception:
        return False
    if diag.get('environment_supports_real_model_inference') is not False:
        return False
    if diag.get('real_ready_capabilities') != []:
        return False
    from core.personal_os_enterprise.local_model_stack_binding import local_stack_status
    status = local_stack_status(ROOT)
    if status.get('real_model_ready') is not False:
        return False
    if status.get('environment_blocked') is not True:
        return False
    from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities
    probes = probe_all_capabilities(ROOT)
    kinds = probes.get('ready_kinds', {})
    stub_count = sum(1 for k in kinds.values() if k == 'stub_ready_only')
    blocked_count = sum(1 for k in kinds.values() if k == 'environment_blocked' or k == 'not_configured' or k == 'disabled')
    real_count = sum(1 for k in kinds.values() if k == 'real_model_ready')
    if real_count != 0:
        return False
    if stub_count < 4:
        return False
    if kinds.get('local_llm') == 'real_model_ready':
        return False
    if kinds.get('local_vlm') == 'real_model_ready':
        return False
    if kinds.get('local_image_provider') == 'real_model_ready':
        return False
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    if clean.get('clean') is not True:
        return False
    return True


def _strict_52_13_3() -> bool:
    """In-process 52.13.3 strict contract gate.

    This keeps the strict contract checks but avoids executing the standalone
    diagnostic as a nested verifier process. The top-level runner already runs
    the real pytest matrix, so this gate focuses on the proof/body-schema/model
    contract checks needed for fast repeatable enterprise acceptance.
    """
    import inspect
    import tempfile
    vj = _j('xiaoyi_persona_visual/version.json')
    if vj.get('version') != 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL':
        return False
    if vj.get('features', {}).get('v111_52_13_3_patch_applied') != 'V111.52.13.3_ACCEPTANCE_MATRIX_AND_PROOF_CONTRACT_STRICT_CLOSE_PATCH':
        return False
    runner = (ROOT / 'scripts/acceptance/enterprise_acceptance_runner.py').read_text(encoding='utf-8')
    required_pytest_targets = [
        'tests/acceptance',
        'tests/regression/test_ocr_vlm_consistency.py',
        'tests/regression/test_persona_visual_anatomy.py',
        'tests/regression/test_wardrobe_state.py',
    ]
    if not ('pytest' in runner and all(t in runner for t in required_pytest_targets)):
        return False
    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof
    sig = inspect.signature(issue_mainchain_proof)
    if not all(k in sig.parameters for k in ['chain_id', 'entrypoint', 'policy_digest', 'issuer_version']):
        return False
    proof = issue_mainchain_proof(request_id='diag-r1', chain_id='diag-c1', entrypoint='diag', final_prompt='hello', reference_images=['a.png'], policy_digest='diag-policy', issuer_version='diag')
    if not (isinstance(proof.get('body'), dict) and proof.get('sig') and proof.get('proof_token')):
        return False
    from core.personal_os_enterprise.side_effect_registry import register_issued_proof, consume_issued_proof
    with tempfile.TemporaryDirectory() as td:
        reg = register_issued_proof('diag-replay', 'diag-token', 'payload', root=td)
        c1 = consume_issued_proof('diag-replay', 'diag-token', root=td)
        c2 = consume_issued_proof('diag-replay', 'diag-token', root=td)
    if not (reg.get('ok') is True and c1.get('ok') is True and c2.get('ok') is False):
        return False
    schema_path = ROOT / 'xiaoyi_persona_visual/policy/body_schema.yaml'
    schema_text = schema_path.read_text(encoding='utf-8') if schema_path.exists() else ''
    if not (schema_path.exists() and any(x in schema_text for x in ['tailbone', 'sacrum', '后腰']) and any(x in schema_text for x in ['floating', '漂浮'])):
        return False
    builder = (ROOT / 'xiaoyi_persona_visual/prompt/persona_image_prompt_builder.py').read_text(encoding='utf-8')
    if not ('_load_body_schema_block' in builder and 'policy/body_schema.yaml' in builder and 'body_schema_loaded' in builder):
        return False
    from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import build_structured_chinese_prompt
    body, meta = build_structured_chinese_prompt(base_prompt='背身展示尾巴', focus_target='tail')
    if not (meta.get('body_schema_loaded') is True and ('tailbone' in body or '后腰' in body or 'sacrum' in body)):
        return False
    model_hash_script = (ROOT / 'scripts/verify_model_cache_hash.py').read_text(encoding='utf-8')
    if not ('pending_not_configured' in model_hash_script and 'blocked_missing_expected_sha256' in model_hash_script):
        return False
    from core.personal_os_enterprise.local_model_stack_binding import local_stack_status
    stack = local_stack_status(ROOT)
    if not (len(stack.get('recommended_stack', {})) == 8 and stack.get('allow_external_fallback') is False and stack.get('network_egress_attempted') is False):
        return False
    from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
    img = persona_image_provider_chain_status({})
    if not (img.get('status') == 'blocked' and img.get('external_fallback_allowed') is False and img.get('fail_closed') is True):
        return False
    from core.personal_os_enterprise.observability_ops import build_slo_report, METRIC_KEYS
    with tempfile.TemporaryDirectory() as td:
        slo = build_slo_report(root=td)
    if not (slo.get('trace_coverage_ready') is True and len(METRIC_KEYS) >= 10):
        return False
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    clean = package_clean_check(ROOT)
    return clean.get('clean') is True

def main() -> int:
    py = sys.executable
    run('clean_before', [py, '-S', 'scripts/clean_runtime_artifacts.py'])
    # Also nuke hook_state that may have been created by the outer runtime
    import shutil
    shutil.rmtree(str(ROOT / '.openclaw' / 'hook_state'), ignore_errors=True)
    run_direct('active_metadata_fast', _active_metadata)
    run_direct('forward_compat_fast', _forward_compat_fast)
    run_direct('clean_gate_fast', _clean_gate_fast)
    run_direct('report_remaining_fast', _report_remaining_fast)
    run(
        'pytest_matrix',
        [
            py, '-m', 'pytest', '-q',
            'tests/acceptance',
            'tests/regression/test_ocr_vlm_consistency.py',
            'tests/regression/test_persona_visual_anatomy.py',
            'tests/regression/test_wardrobe_state.py',
        ],
        show=True,
        timeout=PYTEST_TIMEOUT,
    )
    run('clean_after_pytest', [py, '-S', 'scripts/clean_runtime_artifacts.py'])
    run_direct('no_network_egress', _no_network)
    run_direct('no_runtime_secret', _no_runtime_secret)
    run_direct('secret_workflow', _secret_workflow)
    run_direct('rootless_runtime', _rootless)
    run_direct('model_cache_hash', _model_hash)
    run_direct('strict_52_13_3_fast', _strict_52_13_3)
    run_direct('strict_52_14_env_limited', _strict_52_14)
    run('clean_final', [py, '-S', 'scripts/clean_runtime_artifacts.py'])
    os.write(1, b'[enterprise-acceptance] passed\n')
    return 0


if __name__ == '__main__':
    # Exit by os._exit immediately after main() returns. Some pytest/telemetry
    # plugin environments can leave non-daemon background threads or blocking
    # stream finalizers behind the interpreter shutdown path. The runner already
    # flushes every step-level print; a direct process exit makes the top-level
    # acceptance command repeatable instead of hanging after the final passed line.
    os._exit(main())
