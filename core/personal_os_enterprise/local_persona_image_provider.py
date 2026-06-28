from __future__ import annotations
from typing import Dict, Any, List
from .local_providers import run_local_image_provider
from .send_guard import validate_artifact_for_send
VERSION = 'V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'
def generate_local_persona_image(*, prompt: str, reference_images: List[str], output_path: str, request_id: str, generation_started_at: float, root=None, **ctx) -> Dict[str, Any]:
    if len(reference_images or []) < 2:
        return {'status':'blocked','blocked':True,'blocked_reason':'persona_local_image_requires_avatar_and_outfit_refs'}
    res = run_local_image_provider(prompt, root=root, output_path=output_path, reference_images=reference_images, **ctx)
    if res.get('blocked'):
        res['persona_local_provider_used'] = False; return res
    guard = validate_artifact_for_send(path=output_path, generation_started_at=generation_started_at, request_id=request_id, expected_request_id=request_id)
    if not guard.get('send_ok'):
        return {'status':'blocked','blocked':True,'blocked_reason':guard.get('reason') or 'local_persona_send_guard_failed','send_guard':guard,'provider_result':res}
    return {'status':'generated','blocked':False,'persona_local_provider_used':True,'send_guard':guard,'provider_result':res,'version':VERSION}
