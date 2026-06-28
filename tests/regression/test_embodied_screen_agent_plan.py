from core.personal_os_enterprise.embodied_screen_agent import plan_screen_understanding


def test_screen_agent_fail_closed_when_missing_local_models(tmp_path):
    r = plan_screen_understanding('看一下截图里有什么按钮', root=tmp_path)
    assert r['blocked'] is True
    assert r['allow_external_fallback'] is False
    assert 'local_vlm' in r['required_capabilities']
