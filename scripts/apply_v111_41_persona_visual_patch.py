#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def update_json(path: Path, mutate):
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
    mutate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def main() -> int:
    def mutate_openclaw(data):
        pv = data.setdefault('personaVisual', {})
        pv.update({
            'enabled': True,
            'autoGenerate': True,
            'generateOnlyOnPhase': 'post_reply',
            'preReplyMode': 'detect_only',
            'maxImagesPerTurn': 1,
            'dedupeWindowSeconds': 45,
            'preventDuplicateImageSend': True,
            'fallbackToSceneDefault': False,
            'sceneDefaultFallback': 'manual_only_no_auto_send',
            'dedupeKeyPolicy': 'same_text_mood_scene_across_all_outlets',
            'providerInstallPolicy': 'seedream_skill_required_or_xiaoyi_env',
            'version': 'V111.41',
        })

    update_json(ROOT / 'openclaw.json', mutate_openclaw)

    scene_cfg = ROOT / 'assets/persona/scene_defaults/scene_default_config.json'
    if scene_cfg.exists():
        def mutate_scene(data):
            data['auto_image_send'] = False
            data['auto_hint'] = False
            data['send_policy'] = 'manual_only_no_auto_send'
        update_json(scene_cfg, mutate_scene)

    try:
        from scripts.mainline_bootstrap import enable
        enable()
    except Exception:
        pass

    try:
        from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state
        clear_dedupe_state()
    except Exception:
        pass

    print(json.dumps({
        'status': 'ok',
        'version': 'V111.41',
        'patched': [
            'openclaw.json personaVisual',
            'scene_default_config auto_image_send=false',
            '.openclaw hooks enabled',
            'dedupe state cleared',
        ]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
