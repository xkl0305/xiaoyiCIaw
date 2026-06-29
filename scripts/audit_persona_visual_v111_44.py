#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    from memory_context.persona_runtime.providers.seedream_provider import provider_ready
    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit

    manifest = ROOT / '.openclaw/hooks/manifest.json'
    static_cfg = json.loads((ROOT / 'assets/persona/outfits/outfit_config.json').read_text(encoding='utf-8'))
    pred = {'auto_generation_candidate': True, 'should_auto_generate': True, 'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization', 'mood': 'shy', 'semantic_scene': 'bashful_scene'}
    dry = generate_from_prediction(pred, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看尾巴尖', dry_run=True)
    report = {
        'status': 'ok',
        'version': 'V111.44_PERSONA_VISUAL_FUSION_CLEAN',
        'hooks_present': manifest.exists() and (ROOT / '.openclaw/hooks/pre_reply.py').exists() and (ROOT / '.openclaw/hooks/post_reply.py').exists(),
        'manifest': json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else None,
        'stealth_focus': detect_focus_request('偷偷看看你'),
        'tail_focus': detect_focus_request('看看尾巴尖'),
        'blocked_focus': detect_focus_request('看看内裤'),
        'static_outfit_has_current_outfit': 'current_outfit' in static_cfg,
        'moonfeather_outfit': choose_outfit(text='穿月羽云裳', mood='shy', semantic_scene='bashful_scene').get('outfit_id'),
        'provider_ready': provider_ready(),
        'dry_run_status': dry.get('status'),
        'dry_run_focus_target': dry.get('focus_target'),
        'secondary_generation_planned': dry.get('secondary_generation_planned'),
        'max_images_this_turn': dry.get('max_images_this_turn'),
    }
    out = ROOT / 'reports/V111_44_PERSONA_VISUAL_FUSION_AUDIT.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
