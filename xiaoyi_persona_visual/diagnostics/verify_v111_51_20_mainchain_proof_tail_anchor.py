from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_context.persona_runtime.providers.seedream_provider import generate_image
from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof, validate_mainchain_proof


def main() -> int:
    checks = {}
    prompt = '生成图片内的人物要和参考图内人物保持像素级一致性，看看你的脚底板'
    refs = ['assets/persona/outfits/pajamas_reference.jpg', 'assets/persona/seed_avatar.jpg']
    blocked = generate_image(prompt=prompt, input_image='assets/persona/seed_avatar.jpg', reference_images=refs, persona_visual_context={
        'persona_visual_request': True, 'pipeline_forced': True, 'persona_visual_controller_used': True, 'wardrobe_loader_used': True, 'prompt_builder_used': 'persona_image_prompt_builder', 'avatar_reference_present': True, 'outfit_reference_present': True, 'reference_images_count': 2, 'generation_mode': 'image_to_image'
    })
    checks['manual_pvc_blocked'] = blocked.get('blocked_reason') == 'manual_pvc_provider_call_blocked'
    proof = issue_mainchain_proof(final_prompt=prompt, reference_images=['assets/persona/seed_avatar.jpg', 'assets/persona/outfits/pajamas_reference.jpg'])
    valid = validate_mainchain_proof({'mainchain_proof': proof}, prompt, ['assets/persona/seed_avatar.jpg', 'assets/persona/outfits/pajamas_reference.jpg'])
    checks['proof_valid'] = valid.get('valid') is True
    tampered = validate_mainchain_proof({'mainchain_proof': proof}, prompt + ' x', ['assets/persona/seed_avatar.jpg', 'assets/persona/outfits/pajamas_reference.jpg'])
    checks['proof_tamper_blocked'] = tampered.get('valid') is False
    overall = all(checks.values())
    print({'overall': 'passed' if overall else 'failed', 'checks': checks})
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
