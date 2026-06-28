"""
persona_visual_request_guard.py — V111.51.18

Canonical guard for 鸽子王 persona visual requests.
Internal package paths may still say xiaoyi_persona_visual for compatibility, but
all external semantics/debug fields use persona_subject=鸽子王.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PERSONA_SUBJECT = '鸽子王'
BLOCKED_REASON = 'persona_visual_request_must_use_main_pipeline'
REQUIRED_ENTRY = 'post_reply_or_mainline_hook'

PERSONA_VISUAL_KEYWORDS: List[str] = [
    '鸽子王',
    '小艺',
    '看看你的样子', '看看你', '看看你现在什么样', '让我看看你', '展示一下', '看看全身',
    '看看腿', '看看脚', '看看头发', '看看眼睛', '看看手', '看看腰', '看看鞋',
    '摸摸头', '摸头', '被摸头', '揉揉头', '摸一下头', '摸摸鸽子王的头',
    '站在窗边', '坐在床边', '从门后探头', '露个面看看', '看看造型', '看看整体效果',
    # V111.51.16: persona identity descriptors - fixed identity phrases
    '图片内角色不变', '像素级一致性', '像素级一致', '同一张脸', '同一人物气质',
    '长银发蓝眼少女', '九条星空渐变尾巴', '金环耳饰',
]

REQUIRED_PVC_FIELDS: List[str] = [
    'persona_visual_request',
    'pipeline_forced',
    'persona_visual_controller_used',
    'wardrobe_loader_used',
    'avatar_reference_present',
    'outfit_reference_present',
    'generation_mode',
]


def _compact(s: str) -> str:
    return (s or '').replace(' ', '').replace('\u3000', '')


def detect_persona_visual_request(
    text: str = '',
    prompt: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    input_image: str = '',
    reference_images: Optional[List[str]] = None,
) -> bool:
    md = metadata or {}
    if md.get('persona_visual_request') or md.get('is_persona_image'):
        return True
    if md.get('persona_subject') == PERSONA_SUBJECT:
        return True
    ctx = md.get('persona_visual_context', {})
    if isinstance(ctx, dict) and (ctx.get('persona_visual_request') or ctx.get('persona_subject') == PERSONA_SUBJECT):
        return True
    combined = _compact(f'{text or ""} {prompt or ""}')
    if not combined:
        return False
    return any(_compact(kw) in combined for kw in PERSONA_VISUAL_KEYWORDS)


def validate_persona_visual_context(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(ctx, dict) or not ctx:
        return {'valid': False, 'reason': 'missing_persona_visual_context', 'missing_context_fields': list(REQUIRED_PVC_FIELDS), 'persona_subject': PERSONA_SUBJECT}
    missing: List[str] = []
    for field in REQUIRED_PVC_FIELDS:
        value = ctx.get(field)
        if field == 'generation_mode':
            if value != 'image_to_image':
                missing.append(field)
        elif value is not True:
            missing.append(field)
    if ctx.get('prompt_builder_used') != 'persona_image_prompt_builder':
        missing.append('prompt_builder_used')
    try:
        ref_count = int(ctx.get('reference_images_count') or 0)
    except Exception:
        ref_count = 0
    if ref_count < 2:
        missing.append('reference_images_count>=2')
    if missing:
        return {'valid': False, 'reason': 'invalid_persona_visual_context', 'missing_context_fields': missing, 'persona_subject': PERSONA_SUBJECT}
    return {'valid': True, 'reason': '', 'missing_context_fields': [], 'persona_subject': PERSONA_SUBJECT}


def has_persona_avatar_reference(
    input_image: str = '',
    reference_images: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if seed_avatar is among reference images or input_image."""
    if not input_image and not reference_images:
        return False
    all_paths = list(reference_images or [])
    if input_image and input_image not in all_paths:
        all_paths.append(input_image)
    indicators = ['seed_avatar', 'persona/seed_avatar']
    return any(
        any(ind in str(p).replace('\\', '/') for ind in indicators)
        for p in all_paths
    )


def block_result(reason: str = BLOCKED_REASON, missing_context_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        'status': 'blocked',
        'blocked': True,
        'blocked_reason': reason,
        'required_entry': REQUIRED_ENTRY,
        'message': '鸽子王人格视觉请求必须走主链，禁止手动直调 ARK API 或裸调 seedream_provider。',
        'persona_subject': PERSONA_SUBJECT,
        'missing_context_fields': missing_context_fields or [],
        'generated_image_path': None,
        'output_path': None,
        'provider_status': 'blocked',
        'provider_error': reason,
    }


def block_if_persona_visual_without_main_pipeline(
    text: str = '',
    prompt: str = '',
    metadata: Optional[Dict[str, Any]] = None,
    input_image: str = '',
    reference_images: Optional[List[str]] = None,
    persona_visual_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    md = dict(metadata or {})
    if persona_visual_context is not None:
        md['persona_visual_context'] = persona_visual_context
    is_persona = detect_persona_visual_request(text=text, prompt=prompt, metadata=md, input_image=input_image, reference_images=reference_images)
    # V111.51.18: seed_avatar / persona avatar reference is itself a persona visual request.
    # This prevents prompts like "图片内角色不变" or generic wording from bypassing keyword checks.
    if has_persona_avatar_reference(input_image=input_image, reference_images=reference_images, metadata=md):
        is_persona = True
    if not is_persona:
        return {'blocked': False, 'persona_subject': PERSONA_SUBJECT}
    validation = validate_persona_visual_context(persona_visual_context or md.get('persona_visual_context'))
    if validation.get('valid'):
        return {'blocked': False, 'persona_subject': PERSONA_SUBJECT, 'validated': True, 'persona_visual_request': True}
    return block_result(missing_context_fields=validation.get('missing_context_fields', []))
