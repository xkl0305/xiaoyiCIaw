import shutil
from pathlib import Path

from infrastructure.persona_visual_hook_bus import dispatch, status
from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state

ROOT = Path(__file__).resolve().parents[1]


def test_dispatch_self_heals_missing_no_skills_hooks():
    shutil.rmtree(ROOT / '.openclaw' / 'hooks', ignore_errors=True)
    clear_dedupe_state()
    first = dispatch('post_reply', user_message='probe', assistant_message='搞定了 🎉', reply_text='搞定了 🎉', dry_run=True)
    assert first['status'] == 'ok'
    assert first['called'] is True
    assert first['result']['generation_status'] == 'dry_run_ready'
    assert (ROOT / '.openclaw' / 'hooks' / 'manifest.json').exists()
    assert status()['enabled'] is True


def test_self_healed_dispatch_still_dedupes_reply_outlet():
    clear_dedupe_state()
    text = '搞定了 🎉'
    first = dispatch('post_reply', user_message='probe', assistant_message=text, reply_text=text, dry_run=True)
    assert first['result']['generation_status'] == 'dry_run_ready'
    second = dispatch('post_reply', user_message='probe', assistant_message=text, reply_text=text, dry_run=True)
    assert second['result']['generation_status'] == 'deduped_skip'
