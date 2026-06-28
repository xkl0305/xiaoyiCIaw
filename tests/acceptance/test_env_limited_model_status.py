from __future__ import annotations

"""Tests verifying env-limited local model status for V111.52.14."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_local_model_environment_diagnosis_exists():
    """reports/current/local_model_environment_diagnosis.json must exist and be valid."""
    path = ROOT / 'reports' / 'current' / 'local_model_environment_diagnosis.json'
    assert path.exists(), f'Missing: {path}'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert isinstance(data, dict)
    assert 'environment_supports_real_model_inference' in data
    assert 'blockers' in data
    assert isinstance(data['blockers'], list)
    assert len(data['blockers']) >= 8, f'Expected >=8 blockers, got {len(data["blockers"])}'


def test_environment_supports_real_inference_is_false():
    """The diagnosis must confirm real model inference is not supported."""
    path = ROOT / 'reports' / 'current' / 'local_model_environment_diagnosis.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['environment_supports_real_model_inference'] is False, \
        f'Expected false, got {data["environment_supports_real_model_inference"]}'


def test_real_ready_capabilities_empty():
    """No capabilities should be marked as real-ready."""
    path = ROOT / 'reports' / 'current' / 'local_model_environment_diagnosis.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data.get('real_ready_capabilities') == [], \
        f'Expected empty list, got {data.get("real_ready_capabilities")}'


def test_local_stack_status_real_model_ready_false():
    """local_stack_status() must return real_model_ready=False."""
    import sys
    sys.path.insert(0, str(ROOT))
    from core.personal_os_enterprise.local_model_stack_binding import local_stack_status
    status = local_stack_status()
    assert status['real_model_ready'] is False, f'Expected False, got {status["real_model_ready"]}'
    assert status['environment_blocked'] is True, f'Expected True, got {status["environment_blocked"]}'


def test_probe_status_stub_ready_only():
    """All 8 capabilities must be stub_ready_only, not real_model_ready."""
    from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities
    probes = probe_all_capabilities()
    kinds = probes.get('ready_kinds', {})
    real_model_ready_caps = [k for k, v in kinds.items() if v == 'real_model_ready']
    assert len(real_model_ready_caps) == 0, f'Real-model-ready caps found: {real_model_ready_caps}'
    # All should be either stub_ready_only or environment_blocked
    for cap, kind in kinds.items():
        assert kind in ('stub_ready_only', 'environment_blocked', 'disabled', 'not_configured'), \
            f'{cap} has unexpected kind: {kind}'


def test_local_llm_not_real_ready():
    """local_llm must NOT be real_model_ready."""
    from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities
    kinds = probe_all_capabilities().get('ready_kinds', {})
    assert kinds.get('local_llm') != 'real_model_ready', 'local_llm must not be real_model_ready'


def test_local_vlm_not_real_ready():
    """local_vlm must NOT be real_model_ready."""
    from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities
    kinds = probe_all_capabilities().get('ready_kinds', {})
    assert kinds.get('local_vlm') != 'real_model_ready', 'local_vlm must not be real_model_ready'


def test_local_image_provider_not_real_ready():
    """local_image_provider must NOT be real_model_ready."""
    from core.personal_os_enterprise.local_runtime_probe import probe_all_capabilities
    kinds = probe_all_capabilities().get('ready_kinds', {})
    assert kinds.get('local_image_provider') != 'real_model_ready', 'local_image_provider must not be real_model_ready'


def test_package_clean():
    """Source runtime boundary must report clean."""
    import os
    # Nuke hook_state that the runtime gateway may have created
    import shutil
    shutil.rmtree(str(ROOT / '.openclaw' / 'hook_state'), ignore_errors=True)
    # Also clear __pycache__ / .pytest_cache left by test runner
    for d in ROOT.rglob('__pycache__'):
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(str(ROOT / '.pytest_cache'), ignore_errors=True)
    # Invalidate package_clean_cache
    os.environ['SOURCE_RUNTIME_BOUNDARY_DISABLE_CACHE'] = '1'
    from infrastructure.packaging.source_runtime_boundary import package_clean_check
    result = package_clean_check(ROOT)
    assert result.get('clean') is True, f'Package not clean: {result}'
