from __future__ import annotations

def test_ocr_vlm_consistency_placeholder_fail_closed():
    # Local OCR is now enabled with a command stub. Verify it executes locally and does not call external APIs.
    from core.personal_os_enterprise.local_providers import execute_local_capability
    r=execute_local_capability('local_ocr', image_path='missing.png')
    # With stub command active, should execute (not blocked) but with no external fallback
    assert r['blocked'] is False, f'Expected execution, got blocked: {r}'
    assert r.get('status') == 'executed', f'Expected executed status, got: {r.get("status")}'
    assert r['metadata']['allow_external_fallback'] is False
