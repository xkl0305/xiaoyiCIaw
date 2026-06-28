#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state, make_dedupe_key
    from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
    from infrastructure.persona_visual_hook_bus import dispatch, status as bus_status
    from infrastructure.persona_visual_reply_outlet import finalize_reply

    text = '搞定了 🎉'
    pred = predict_visual_intent(text, {}, {})
    key_a = make_dedupe_key(text, pred, '')
    key_b = make_dedupe_key(text, pred, 'different-request-id')
    clear_dedupe_state()
    direct = dispatch('post_reply', user_message='probe', assistant_message=text, reply_text=text, dry_run=True)
    outlet = finalize_reply(reply_text=text, user_message='probe', source='reply_outlet', dry_run=True)

    cfg = json.loads((ROOT / 'openclaw.json').read_text(encoding='utf-8')).get('personaVisual', {})
    scene_default = json.loads((ROOT / 'assets/persona/scene_defaults/scene_default_config.json').read_text(encoding='utf-8'))
    provider_installed = importlib.util.find_spec('skills.seedream_image_gen.scripts.generate_seedream') is not None

    report = {
        'status': 'ok',
        'version': 'V111.41',
        'bus_status': bus_status(),
        'dedupe_key_equal_across_request_id': key_a == key_b,
        'direct_post_generation_status': direct.get('result', {}).get('generation_status'),
        'reply_outlet_generation_status': outlet.get('hook_result', {}).get('result', {}).get('generation_status'),
        'scene_default_auto_image_send': scene_default.get('auto_image_send'),
        'seedream_provider_module_installed': provider_installed,
        'persona_visual_config': {
            'generateOnlyOnPhase': cfg.get('generateOnlyOnPhase'),
            'preventDuplicateImageSend': cfg.get('preventDuplicateImageSend'),
            'fallbackToSceneDefault': cfg.get('fallbackToSceneDefault'),
            'dedupeKeyPolicy': cfg.get('dedupeKeyPolicy'),
            'providerInstallPolicy': cfg.get('providerInstallPolicy'),
        }
    }
    ok = (
        report['dedupe_key_equal_across_request_id']
        and report['direct_post_generation_status'] in {'dry_run_ready', 'provider_not_ready', 'generated'}
        and report['reply_outlet_generation_status'] == 'deduped_skip'
        and report['scene_default_auto_image_send'] is False
        and report['seedream_provider_module_installed'] is True
    )
    report['status'] = 'ok' if ok else 'fail'
    out = ROOT / 'reports' / 'V111_41_PERSONA_VISUAL_AUDIT.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
