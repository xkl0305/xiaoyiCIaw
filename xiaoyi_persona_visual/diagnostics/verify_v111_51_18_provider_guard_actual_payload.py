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


def _pvc() -> dict:
    return {
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


def main() -> int:
    from memory_context.persona_runtime.providers.seedream_provider import generate_image
    from xiaoyi_persona_visual.policy.persona_visual_request_guard import (
        detect_persona_visual_request,
        has_persona_avatar_reference,
        block_if_persona_visual_without_main_pipeline,
    )
    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof

    checks: dict[str, object] = {}
    failures: list[str] = []

    for rel in ['release_manifest.json', 'xiaoyi_persona_visual/version.json', '.openclaw/hooks/manifest.json']:
        obj = _load_json(rel)
        checks[f'{rel}:version'] = obj.get('version')
        if obj.get('version') != VERSION:
            failures.append(f'version_not_unified:{rel}:{obj.get("version")}')
    oc = _load_json('openclaw.json')
    checks['openclaw_personaVisual_version'] = oc.get('personaVisual', {}).get('version')
    if oc.get('personaVisual', {}).get('version') != VERSION:
        failures.append('openclaw_personaVisual_version_not_unified')

    provider_path = ROOT / 'memory_context/persona_runtime/providers/seedream_provider.py'
    provider_text = provider_path.read_text(encoding='utf-8')
    backup_path = ROOT / 'memory_context/persona_runtime/providers/seedream_provider.py.backup'
    checks['provider_backup_removed'] = not backup_path.exists()
    checks['auto_pvc_removed'] = '_build_auto_pvc' not in provider_text and '_auto_route_text' not in provider_text and 'guard2' not in provider_text
    checks['provider_calls_canonical_guard'] = 'block_if_persona_visual_without_main_pipeline' in provider_text
    checks['actual_payload_reference_required'] = 'missing_required_reference_images' in provider_text and '_persona_actual_reference_status' in provider_text
    checks['provider_no_is_persona_undefined'] = 'if is_persona' not in provider_text

    avatar = str(ROOT / 'assets/persona/seed_avatar.jpg')
    outfit = str(ROOT / 'assets/persona/outfits/moonfeather_robe_reference.jpg')
    pvc = _pvc()

    checks['avatar_reference_file_exists'] = Path(avatar).exists()
    checks['outfit_reference_file_exists'] = Path(outfit).exists()
    checks['guard_detects_seed_avatar_path'] = has_persona_avatar_reference(input_image=avatar) is True
    checks['guard_detects_identity_descriptor'] = detect_persona_visual_request(prompt='生成图片内的人物要和参考图内人物保持像素级一致性，长银发蓝眼少女，金环耳饰，身后有九条星空渐变尾巴') is True

    direct_guard = block_if_persona_visual_without_main_pipeline(prompt='生成一张漂亮图片', input_image=avatar)
    checks['canonical_guard_blocks_seed_avatar_without_pvc'] = direct_guard.get('blocked') is True and direct_guard.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'

    seed_no_pvc = generate_image(prompt='生成一张漂亮图片', input_image=avatar)
    checks['provider_seed_avatar_no_pvc_blocked'] = seed_no_pvc.get('status') == 'blocked' and seed_no_pvc.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'

    identity_no_pvc = generate_image(prompt='生成图片内的人物要和参考图内人物保持像素级一致性，长银发蓝眼少女，金环耳饰，身后有九条星空渐变尾巴')
    checks['identity_descriptor_no_pvc_blocked'] = identity_no_pvc.get('status') == 'blocked' and identity_no_pvc.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline'

    one_ref = generate_image(prompt='普通描述', input_image=avatar, persona_visual_context=pvc)
    checks['valid_pvc_but_one_actual_ref_blocked'] = one_ref.get('status') == 'blocked' and one_ref.get('blocked_reason') == 'missing_required_reference_images'
    checks['one_ref_actual_count_is_one'] = int(one_ref.get('reference_images_count_actual') or 0) == 1

    manual_two_refs = generate_image(prompt='普通描述', input_image=avatar, reference_images=[avatar, outfit], persona_visual_context=pvc)
    checks['manual_pvc_two_refs_blocked_without_proof'] = manual_two_refs.get('blocked') is True and manual_two_refs.get('blocked_reason') == 'manual_pvc_provider_call_blocked'
    pvc_with_proof = dict(pvc)
    pvc_with_proof['mainchain_proof'] = issue_mainchain_proof(final_prompt='普通描述', reference_images=[avatar, outfit])
    two_refs = generate_image(prompt='普通描述', input_image=avatar, reference_images=[avatar, outfit], persona_visual_context=pvc_with_proof)
    checks['valid_pvc_two_refs_blocked_without_bridge_proof'] = two_refs.get('blocked') is True and two_refs.get('blocked_reason') in {'mainchain_proof_not_issued_by_bridge', 'manual_pvc_provider_call_blocked', 'invalid_mainchain_proof'}
    checks['valid_pvc_two_refs_provider_blocked_by_proof_registry'] = two_refs.get('status') == 'blocked'

    normal = generate_image(prompt='生成一张山水图，水墨风格')
    checks['ordinary_text_to_image_not_blocked'] = normal.get('status') != 'blocked' and normal.get('blocked') is not True

    # Simulate provider exception path without requests/network by pointing to an invalid URL; should not NameError on is_persona.
    import os
    old_url = os.environ.get('SEEDREAM_API_URL')
    old_key = os.environ.get('SEEDREAM_API_KEY')
    os.environ['SEEDREAM_API_URL'] = 'http://127.0.0.1:1'
    os.environ['SEEDREAM_API_KEY'] = 'test-key'
    try:
        exc_case = generate_image(prompt='生成一张山水图，水墨风格')
        checks['provider_exception_no_is_persona_nameerror'] = 'is_persona' not in str(exc_case.get('error', '')) and exc_case.get('status') in {'provider_exception', 'provider_http_error'}
    finally:
        if old_url is None:
            os.environ.pop('SEEDREAM_API_URL', None)
        else:
            os.environ['SEEDREAM_API_URL'] = old_url
        if old_key is None:
            os.environ.pop('SEEDREAM_API_KEY', None)
        else:
            os.environ['SEEDREAM_API_KEY'] = old_key

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
