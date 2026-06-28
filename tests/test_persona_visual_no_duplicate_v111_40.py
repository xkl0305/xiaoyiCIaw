from pathlib import Path

def test_pre_reply_detects_only_no_generation():
    from scripts.mainline_bootstrap import enable
    from infrastructure.persona_visual_hook_bus import dispatch
    enable()
    out = dispatch('pre_reply', reply_text='搞定了 🎉', dry_run=True)
    assert out['status'] == 'ok'
    result = out.get('result') or {}
    assert result.get('generation_status') == 'precheck_only'
    assert not result.get('generated_image_path')

def test_post_reply_dedupes_same_reply():
    from scripts.mainline_bootstrap import enable
    from infrastructure.persona_visual_hook_bus import dispatch
    from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state
    enable()
    clear_dedupe_state()
    first = dispatch('post_reply', reply_text='搞定了 🎉', dry_run=True)
    second = dispatch('post_reply', reply_text='搞定了 🎉', dry_run=True)
    r1 = first.get('result') or {}
    r2 = second.get('result') or {}
    assert r1.get('generation_status') in {'dry_run_ready', 'provider_not_ready', 'default_scene_ready_single_fallback'}
    assert r2.get('generation_status') == 'deduped_skip'

def test_scene_defaults_not_auto_send():
    import json
    cfg = json.loads(Path('assets/persona/scene_defaults/scene_default_config.json').read_text(encoding='utf-8'))
    assert cfg.get('auto_image_send') is False
