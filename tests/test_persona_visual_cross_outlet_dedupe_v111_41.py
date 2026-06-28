from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state, make_dedupe_key
from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
from infrastructure.persona_visual_hook_bus import dispatch
from infrastructure.persona_visual_reply_outlet import finalize_reply


def test_dedupe_key_ignores_request_id_across_outlets():
    pred = predict_visual_intent('搞定了 🎉', {}, {})
    a = make_dedupe_key('搞定了 🎉', pred, '')
    b = make_dedupe_key('搞定了 🎉', pred, 'different-host-request-id')
    assert a == b


def test_direct_post_then_reply_outlet_is_single_emit():
    clear_dedupe_state()
    text = '搞定了 🎉'
    first = dispatch('post_reply', user_message='probe', assistant_message=text, reply_text=text, dry_run=True)
    assert first['result']['generation_status'] == 'dry_run_ready'

    second = finalize_reply(reply_text=text, user_message='probe', source='reply_outlet', dry_run=True)
    hook = second['hook_result']
    assert hook['result']['generation_status'] == 'deduped_skip'
