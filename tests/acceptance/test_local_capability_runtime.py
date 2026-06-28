from core.personal_os_enterprise.capability_router import classify_capability_request, route_request


def test_local_ocr_route():
    r = classify_capability_request('识别图片文字')
    assert 'local_ocr' in r['required_capabilities']
    assert r['allow_external_fallback'] is False


def test_local_vlm_route():
    r = classify_capability_request('看一下截图里有什么按钮')
    assert 'local_vlm' in r['required_capabilities']


def test_missing_capability_fail_closed(tmp_path):
    r = route_request('识别图片文字', root=tmp_path, require_ready=True)
    assert r['blocked'] is True
    assert r['blocked_reason'] == 'capability_not_available'
    assert r['allow_external_fallback'] is False
