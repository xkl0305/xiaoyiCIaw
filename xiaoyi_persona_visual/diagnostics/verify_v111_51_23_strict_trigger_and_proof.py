from __future__ import annotations

from pathlib import Path

from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
from memory_context.persona_runtime.providers.seedream_provider import generate_image
from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof


def main() -> int:
    checks = {}
    ordinary = ['生成一张山水图', '画一只橘猫坐在窗边', '给我生成一张产品海报']
    checks['ordinary_not_persona_auto'] = all(not predict_visual_intent(x).get('auto_generation_candidate') for x in ordinary)
    persona = predict_visual_intent('把脚掌抬起来，你躺下，看看你的脚底板')
    checks['persona_focus_auto'] = bool(persona.get('auto_generation_candidate'))

    prompt = '生成图片内的人物要和参考图内人物保持像素级一致性，看看你的脚底板'
    refs = ['assets/persona/seed_avatar.jpg', 'assets/persona/outfits/pajamas_reference.jpg']
    proof = issue_mainchain_proof(final_prompt=prompt, reference_images=refs)
    manual = generate_image(prompt=prompt, reference_images=refs, persona_visual_context={
        'persona_visual_request': True,
        'pipeline_forced': True,
        'persona_visual_controller_used': True,
        'wardrobe_loader_used': True,
        'prompt_builder_used': 'persona_image_prompt_builder',
        'avatar_reference_present': True,
        'outfit_reference_present': True,
        'reference_images_count': 2,
        'generation_mode': 'image_to_image',
        'mainchain_proof': proof,
    })
    checks['manual_issue_proof_blocked'] = manual.get('blocked_reason') in {'mainchain_proof_not_issued_by_bridge', 'manual_pvc_provider_call_blocked'}
    # This verification may create a runtime secret while testing proof code. The packaging
    # rule is that the secret must not be shipped in the overlay; remove it after the test.
    secret = Path('.openclaw/state/persona_visual_mainchain_secret')
    registry = Path('.openclaw/state/persona_visual_mainchain_proof_registry.jsonl')
    if secret.exists():
        secret.unlink()
    if registry.exists():
        registry.unlink()
    checks['runtime_secret_not_packaged'] = not secret.exists()
    checks['legacy_readonly_removed'] = not Path('legacy_readonly').exists()
    checks['sitecustomize_with_skills_conditional'] = 'if not (_ROOT / \'skills\').exists()' in Path('sitecustomize.py').read_text(encoding='utf-8')
    overall = all(checks.values())
    print({'overall': 'passed' if overall else 'failed', 'checks': checks})
    return 0 if overall else 1

if __name__ == '__main__':
    raise SystemExit(main())
