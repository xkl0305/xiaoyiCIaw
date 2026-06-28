from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION = 'V111.51.23_STRICT_TRIGGER_AND_PROOF_FINAL'


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def main() -> int:
    from memory_context.persona_runtime.providers.seedream_provider import generate_image
    from xiaoyi_persona_visual.policy.persona_visual_request_guard import (
        detect_persona_visual_request,
        has_persona_avatar_reference,
    )
    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof

    checks = {}
    failures = []

    for rel in ['release_manifest.json', 'xiaoyi_persona_visual/version.json', '.openclaw/hooks/manifest.json']:
        obj = _load_json(rel)
        checks[f'{rel}:version'] = obj.get('version')
        if obj.get('version') != VERSION:
            failures.append(f'version_not_unified:{rel}:{obj.get("version")}')
    oc = _load_json('openclaw.json')
    checks['openclaw_personaVisual_version'] = oc.get('personaVisual', {}).get('version')
    if oc.get('personaVisual', {}).get('version') != VERSION:
        failures.append('openclaw_personaVisual_version_not_unified')

    provider_text = (ROOT / 'memory_context/persona_runtime/providers/seedream_provider.py').read_text(encoding='utf-8')
    checks['auto_pvc_removed'] = '_build_auto_pvc' not in provider_text and '_auto_route_text' not in provider_text
    checks['provider_calls_guard_with_reference_images'] = 'reference_images=reference_images' in provider_text
    checks['actual_payload_reference_required'] = 'missing_required_reference_images' in provider_text

    avatar = str(ROOT / 'assets/persona/seed_avatar.jpg')
    outfit = str(ROOT / 'assets/persona/outfits/moonfeather_robe_reference.jpg')
    pvc = {
        'persona_visual_request': True,
        'pipeline_forced': True,
        'persona_visual_controller_used': True,
        'wardrobe_loader_used': True,
        'prompt_builder_used': 'persona_image_prompt_builder',
        'avatar_reference_present': True,
        'outfit_reference_present': True,
        'reference_images_count': 2,
        'generation_mode': 'image_to_image',
    }

    checks['guard_detects_seed_avatar_path'] = has_persona_avatar_reference(input_image=avatar) is True
    checks['guard_detects_identity_descriptor'] = detect_persona_visual_request(prompt='生成图片内的人物要和参考图内人物保持像素级一致性，长银发蓝眼少女，金环耳饰，身后有九条星空渐变尾巴') is True

    seed_no_pvc = generate_image(prompt='图片内角色不变，生成图片内的人物要和参考图内人物保持像素级一致性', input_image=avatar)
    checks['seed_avatar_no_pvc_blocked'] = seed_no_pvc.get('status') == 'blocked' and seed_no_pvc.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'

    identity_no_pvc = generate_image(prompt='生成图片内的人物要和参考图内人物保持像素级一致性，长银发蓝眼少女，金环耳饰，身后有九条星空渐变尾巴')
    checks['identity_descriptor_no_pvc_blocked'] = identity_no_pvc.get('status') == 'blocked' and identity_no_pvc.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'

    seed_valid_pvc_missing_outfit = generate_image(prompt='普通描述', input_image=avatar, persona_visual_context=pvc)
    checks['valid_pvc_but_one_actual_ref_blocked'] = seed_valid_pvc_missing_outfit.get('status') == 'blocked' and seed_valid_pvc_missing_outfit.get('blocked_reason') == 'missing_required_reference_images'

    manual_two_refs = generate_image(prompt='普通描述', input_image=avatar, reference_images=[avatar, outfit], persona_visual_context=pvc)
    checks['manual_pvc_two_refs_blocked_without_proof'] = manual_two_refs.get('blocked') is True and manual_two_refs.get('blocked_reason') == 'manual_pvc_provider_call_blocked'
    pvc_with_proof = dict(pvc)
    pvc_with_proof['mainchain_proof'] = issue_mainchain_proof(final_prompt='普通描述', reference_images=[avatar, outfit])
    seed_valid_pvc_two_refs = generate_image(prompt='普通描述', input_image=avatar, reference_images=[avatar, outfit], persona_visual_context=pvc_with_proof)
    checks['valid_pvc_two_refs_blocked_by_proof_registry'] = seed_valid_pvc_two_refs.get('blocked') is True and seed_valid_pvc_two_refs.get('blocked_reason') in {'mainchain_proof_not_issued_by_bridge', 'manual_pvc_provider_call_blocked', 'invalid_mainchain_proof'}
    checks['valid_pvc_two_refs_count_actual'] = int(seed_valid_pvc_two_refs.get('reference_images_count') or 0) >= 2 or seed_valid_pvc_two_refs.get('status') == 'provider_not_ready'

    ordinary = generate_image(prompt='生成一张山水图，水墨风格')
    checks['ordinary_text_to_image_not_blocked'] = ordinary.get('status') != 'blocked' and ordinary.get('blocked') is not True

    for k, v in checks.items():
        if isinstance(v, bool) and not v:
            failures.append(k)

    for k, v in checks.items():
        print(f'{k}={v}')
    print('failures=' + json.dumps(failures, ensure_ascii=False))
    print(f'overall={"passed" if not failures else "failed"}')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
