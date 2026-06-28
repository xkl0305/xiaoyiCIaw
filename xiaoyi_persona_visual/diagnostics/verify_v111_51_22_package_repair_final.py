from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION = 'V111.51.23_STRICT_TRIGGER_AND_PROOF_FINAL'


def _j(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main() -> int:
    checks = {}
    wm = _j('xiaoyi_persona_visual/wardrobe/wardrobe_manifest.json')
    for outfit_id in ['moonfeather_robe', 'stardust_dream', 'pajamas', 'gown']:
        ref = wm['outfits'][outfit_id]['reference_image']
        checks[f'{outfit_id}_reference_exists'] = bool((ROOT / ref).exists())
        checks[f'{outfit_id}_reference_ascii'] = all(ord(c) < 128 for c in ref)

    vi = _j('xiaoyi_persona_visual/config/visual_identity_profile.json')
    desc = vi.get('description','')
    checks['identity_profile_no_fox_ears_positive'] = not any(x in desc for x in ['头顶一对狐狸耳朵', '狐耳带着', '猫耳带着', '兽耳带着', '耳尖发光']) and '不出现狐狸耳朵' in desc and '不出现任何兽耳' in desc

    versions = [
        _j('xiaoyi_persona_visual/version.json').get('version'),
        _j('release_manifest.json').get('version'),
        _j('.openclaw/hooks/manifest.json').get('version'),
        _j('openclaw.json').get('personaVisual',{}).get('version'),
    ]
    checks['versions_unified'] = versions == [VERSION, VERSION, VERSION, VERSION]

    from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
    pred = predict_visual_intent('把脚掌抬起来，你躺下，看看你的脚底板')
    checks['explicit_sole_request_auto'] = pred.get('auto_generation_candidate') is True and pred.get('confidence',0) >= 0.6

    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    focus = detect_focus_request('把脚掌抬起来，你躺下，看看你的脚底板')
    checks['sole_focus_detected'] = focus.get('focus_target') == 'sole' and focus.get('view_angle') == 'low_or_rear_foot_detail'

    from memory_context.persona_runtime.providers.seedream_provider import generate_image
    manual = generate_image(
        prompt='把脚掌抬起来，看看你的脚底板',
        input_image='assets/persona/seed_avatar.jpg',
        reference_images=['assets/persona/outfits/pajamas_reference.jpg'],
        persona_visual_context={
            'persona_visual_request': True, 'pipeline_forced': True, 'persona_visual_controller_used': True,
            'wardrobe_loader_used': True, 'prompt_builder_used': 'persona_image_prompt_builder',
            'avatar_reference_present': True, 'outfit_reference_present': True, 'reference_images_count': 2,
            'generation_mode': 'image_to_image'
        }
    )
    checks['manual_pvc_blocked_without_proof'] = manual.get('blocked') is True and manual.get('blocked_reason') == 'manual_pvc_provider_call_blocked'

    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import prepare_generation_context, generate_from_prediction
    prediction = {'auto_generation_candidate': True, 'should_auto_generate': True, 'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization', 'mood': 'calm', 'semantic_scene': 'daily_presence_scene', 'confidence': 0.72, 'emotion_signature': [], 'expression_hints': []}
    prepared = prepare_generation_context(prediction, text='看看腿', user_message='看看腿')
    dry = generate_from_prediction(prediction, text='看看腿', user_message='看看腿', dry_run=True, prepared_context=prepared)
    checks['dry_run_has_outfit_reference'] = dry.get('outfit_reference_present') is True and int(dry.get('reference_images_count') or 0) >= 2
    checks['dry_run_uses_prompt_builder'] = dry.get('prompt_builder_used') == 'persona_image_prompt_builder'

    six = _j('infrastructure/SIX_LAYER_REGISTRY.json')
    layer_of = {}
    for lid, layer in six.get('layers',{}).items():
        for comp in layer.get('components',[]):
            layer_of[comp.get('name')] = lid
    checks['layer_persona_visual_controller_L3'] = layer_of.get('persona_visual_controller') == 'L3'
    checks['layer_seedream_provider_L4'] = layer_of.get('seedream_provider') == 'L4'
    checks['layer_guard_L5'] = layer_of.get('persona_visual_request_guard') == 'L5'
    checks['layer_identity_L1'] = layer_of.get('visual_identity_profile') == 'L1'

    ok = all(checks.values())
    print(json.dumps({'overall': 'passed' if ok else 'failed', 'checks': checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
