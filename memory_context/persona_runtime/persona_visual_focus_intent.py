from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from xiaoyi_persona_visual.policy.focus_view_resolver import resolve_focus_view

INVALID_TARGETS = {'你', '我', '他', '她', '它', '自己', '人', '一下', '一眼', '这个', '那个', '看看', '看下', '看一下', '图片', '图', '照片', '照', '东西', '内容', '啥', '什么'}
STEALTH_SCENE_PATTERNS = ['偷偷看看你', '偷偷看你', '悄悄看你', '偷看你', '偷瞄你', '躲在屏幕后面偷笑']
BLOCK_WORDS = ['内裤', '私处', '下体', '性器', '裸', '裸体', '全裸', '脱光', '露点', '乳头']

DISPLAY_APPEARANCE_SCENE_ONLY_PATTERNS = [
    '看看你的样子', '看看你现在什么样', '让我看看你', '展示一下',
    '看看全身', '给我看看造型', '露个面看看', '看看整体效果',
]

KNOWN_FOCUS: List[Tuple[str, str, List[str], str]] = [
    ('legs', 'body_focus', ['腿', '美腿', '大长腿', '腿照', '小腿', '膝盖', '腿部'], 'Generate one extra identity-consistent legs-focused image. Elegant legs, tasteful clothed fashion framing, full-body or thigh-to-calf composition, non-explicit.'),
    ('tail', 'signature_trait', ['尾巴', '九条尾巴', '狐尾', '尾巴尖', '尾巴毛', '尾巴尖尖'], 'Generate one extra image focusing on the tails: flowing tail motion, magical glow, full-body or three-quarter view, whimsical and tasteful.'),
    ('ears', 'accessory_detail', ['耳朵', '耳垂', '耳环', '金环耳饰', '耳饰'], 'Generate one extra portrait focusing on normal human ears and gold hoop earrings; no fox ears, no cat ears, no animal ears, upper-body framing, identity unchanged.'),
    ('hair', 'signature_detail', ['头发', '发丝', '长发', '刘海', '发饰', '发夹', '发尾'], 'Generate one extra portrait focusing on hair and accessories: floating hair, detailed ornament, soft motion, identity unchanged.'),
    ('eyes', 'expression_detail', ['眼睛', '眼神', '眨眼', 'wink', '眨一下', '眼'], 'Generate one extra close portrait focusing on eye expression, bright eyes, natural gaze, identity unchanged.'),
    ('hands', 'gesture_detail', ['手', '手指', '手势', '比心', '比耶', '比个耶', 'v手势', '挥手', '小手'], 'Generate one extra image focusing on hands and gesture: cute gesture, clear hand pose, natural expression, identity consistent.'),
    ('headpat', 'interaction_pose', ['摸摸头', '摸头', '被摸头', '揉揉头', '揉揉脑袋', '摸一下头', 'rua', '揉头', '脑袋', '摸摸鸽子王的头', '摸摸小艺的头'], 'Generate one extra headpat-themed portrait: gentle head-touch interaction, bashful smile, upper-body focus, normal human head shape, no fox ears, no cat ears, identity consistent.'),
    ('waist', 'body_focus', ['腰', '腰线', '看看腰', '腰身', '腰部'], 'Generate one extra image focusing on waistline and outfit detail: elegant silhouette, tasteful, clothed, non-explicit.'),
    ('outfit', 'wardrobe_detail', ['衣服', '裙子', '裙摆', '衣装', '套装', '礼服', '睡衣', '薄纱', '披风', '项链', '饰品', '宝石', '衣柜', '衣摆', '月羽云裳', '星尘织梦'], 'Generate one extra clothing-detail image: outfit fabric, accessories, flowing dress or cape, high-quality fashion detail, identity consistent.'),
    ('heel', 'wardrobe_detail', ['脚后跟', '后脚跟', '脚跟', '足跟', '鞋跟', '脚踝后侧', '后脚踝', '膝盖后侧', '腿弯'], 'Generate one extra fashion-detail image focusing on heel and rear lower body detail, side-back or rear-angle composition, tasteful and non-fetish.'),
    ('sole', 'wardrobe_detail', ['脚底板', '脚掌', '脚底', '足底', '足掌', '鞋底', '脚板'], 'Generate one extra fashion-detail image focusing on sole or foot-bottom detail, low or rear foot angle, tasteful and non-fetish.'),
    ('shoes', 'wardrobe_detail', ['鞋', '鞋子', '高跟鞋', '靴子', '脚踝', '鞋尖'], 'Generate one extra fashion-detail image focusing on shoes or ankle styling, full-body fashion framing, tasteful and non-fetish.'),
    ('wings', 'signature_trait', ['翅膀', '羽翼', '光翼', '蝴蝶翼', '翅'], 'Generate one extra image focusing on luminous wings and magical glow, elegant full-body or half-body composition.'),
    ('pose', 'pose_request', ['pose', '姿势', '摆个', '比个', '叉腰', '歪头', '回头', '低头', '抬头', '坐下', '蹲下', '摆pose'], 'Generate one extra image following the requested pose, natural full-body composition, expressive and identity-consistent.'),
    ('face', 'expression_detail', ['脸', '表情', '笑脸', '侧脸', '害羞脸', '脸红', '小脸'], 'Generate one extra portrait focusing on face and expression, natural emotion, identity consistent.'),
]

SAFE_REDIRECT = {
    '胸': ('upper_body_outfit_detail', 'safe_redirect', 'Generate a safe upper-body outfit-detail image focusing on collar, necklace, fabric, posture, and facial expression; clothed, tasteful, non-explicit, no erotic framing.'),
    '胸口': ('upper_body_outfit_detail', 'safe_redirect', 'Generate a safe upper-body outfit-detail image focusing on collar, necklace, fabric, posture, and facial expression; clothed, tasteful, non-explicit, no erotic framing.'),
    '胸部': ('upper_body_outfit_detail', 'safe_redirect', 'Generate a safe upper-body outfit-detail image focusing on collar, necklace, fabric, posture, and facial expression; clothed, tasteful, non-explicit, no erotic framing.'),
    '屁股': ('back_outfit_tail_detail', 'safe_redirect', 'Generate a safe back-view outfit-detail image focusing on tail motion, skirt/cape silhouette and fabric flow; clothed, tasteful, non-explicit.'),
    '臀': ('back_outfit_tail_detail', 'safe_redirect', 'Generate a safe back-view outfit-detail image focusing on tail motion, skirt/cape silhouette and fabric flow; clothed, tasteful, non-explicit.'),
}

TRIGGER_PATTERNS = [
    r'(?:看看|看一下|给我看|让我看|来张|拍张|生成|画|出一张|展示|摆个|比个|摸摸|摸一下|rua一下?|rua)(?P<target>[\u4e00-\u9fffA-Za-z0-9_·]{1,16})',
    r'(?P<target>[\u4e00-\u9fffA-Za-z0-9_·]{1,16})(?:给我看看|给我看一下|来一张|来张|照|图)',
]


def _norm(s: str) -> str:
    return re.sub(r'[\s,，。.!！?？:：;；"“”\'’‘、_\-]+', '', s or '').lower()


def _safe_prompt(target: str) -> str:
    return f'Generate one extra identity-consistent image focusing on {target}. Keep it tasteful, clothed, non-explicit, expressive, aligned with current outfit and scene, no watermark, no text.'


def _clean_target(target: str) -> str:
    t = _norm(target)
    for prefix in ['你的', '你这个', '我的', '这个', '那个', '一下', '一张']:
        if t.startswith(prefix):
            t = t[len(prefix):]
    for suffix in ['一下', '看看', '看一下', '照片', '图片', '图', '照', '给我看']:
        if t.endswith(suffix):
            t = t[:-len(suffix)]
    return t[:16]


def _extract_targets(text: str) -> List[str]:
    out: List[str] = []
    for pattern in TRIGGER_PATTERNS:
        for m in re.finditer(pattern, text or '', flags=re.IGNORECASE):
            t = _clean_target(m.group('target'))
            if t and t not in INVALID_TARGETS and t not in out:
                out.append(t)
    return out[:5]


_FOCUS_COMMON_FIELDS = {
    'reference_policy': 'priority_context_reference',
    'reference_priority': ['outfit_image', 'scene_default_image', 'seed_avatar'],
    'focus_generation_model': 'seedream5.0_image_to_image',
    'scene_direct_send_when_available': True,
    'focus_generate_count': 1,
}


def _with_common(d: Dict[str, Any]) -> Dict[str, Any]:
    d.update(_FOCUS_COMMON_FIELDS)
    return d



def _resolver_focus_dict(resolved: Dict[str, Any], extracted: List[str]) -> Dict[str, Any]:
    return _with_common({
        'focus_target': resolved.get('focus_target', ''),
        'focus_category': resolved.get('focus_category', ''),
        'focus_label': resolved.get('focus_label', ''),
        'raw_focus_label': resolved.get('raw_focus_label', resolved.get('focus_label', '')),
        'secondary_prompt': resolved.get('secondary_prompt', ''),
        'secondary_generation_allowed': bool(resolved.get('secondary_generation_allowed', False)),
        'focus_match_mode': resolved.get('focus_match_mode', 'focus_view_resolver'),
        'extracted_targets': extracted,
        'safety_policy': resolved.get('safety_policy', 'auto_safe'),
        'use_current_outfit_reference': bool(resolved.get('use_current_outfit_reference', True)),
        'body_region': resolved.get('body_region', ''),
        'view_angle': resolved.get('view_angle', ''),
        'composition_template': resolved.get('composition_template', ''),
        'pose_template': resolved.get('pose_template', ''),
        'scene_template': resolved.get('scene_template', ''),
        'light_template': resolved.get('light_template', ''),
        'allowed_detail_block': resolved.get('allowed_detail_block', ''),
        'forbidden_detail_block': resolved.get('forbidden_detail_block', ''),
        'negative_prompt_extra': resolved.get('negative_prompt_extra', []),
        'focus_confidence': resolved.get('focus_confidence', 0.0),
        'focus_score': resolved.get('focus_score', 0),
        'resolver_rule_id': resolved.get('resolver_rule_id', ''),
        'view_angle_source': resolved.get('view_angle_source', ''),
        'candidate_matches': resolved.get('candidate_matches', []),
        'side_hint': resolved.get('side_hint', ''),
        'surface_hint': resolved.get('surface_hint', ''),
        'direction_flags': resolved.get('direction_flags', {}),
        'parsed_focus_text': resolved.get('parsed_focus_text', ''),
        'normalized_query': resolved.get('normalized_query', ''),
        'primary_focus': resolved.get('primary_focus', ''),
        'primary_focus_keyword': resolved.get('primary_focus_keyword', ''),
        'secondary_focuses': resolved.get('secondary_focuses', []),
        'multi_focus': bool(resolved.get('multi_focus', False)),
        'focus_priority_reason': resolved.get('focus_priority_reason', ''),
        'modifiers': resolved.get('modifiers', {}),
        'explicit_view_request': resolved.get('explicit_view_request', ''),
        'ambiguity_level': resolved.get('ambiguity_level', ''),
        'fallback_reason': resolved.get('fallback_reason', ''),
        'focus_parse_trace': resolved.get('focus_parse_trace', []),
    })

def detect_focus_request(*texts: str, **kwargs: Any) -> Dict[str, Any]:
    joined_text = ' '.join([t for t in texts if isinstance(t, str) and t.strip()])
    compact = _norm(joined_text)
    if any(_norm(p) in compact for p in DISPLAY_APPEARANCE_SCENE_ONLY_PATTERNS):
        return _with_common({'focus_target': '', 'focus_category': '', 'focus_label': '', 'secondary_prompt': '', 'secondary_generation_allowed': False, 'focus_match_mode': 'display_appearance_scene_only', 'extracted_targets': [], 'safety_policy': 'scene_only', 'use_current_outfit_reference': False})
    if any(_norm(p) in compact for p in STEALTH_SCENE_PATTERNS):
        return _with_common({'focus_target': '', 'focus_category': '', 'focus_label': '', 'secondary_prompt': '', 'secondary_generation_allowed': False, 'focus_match_mode': 'scene_only_stealth_peek', 'extracted_targets': [], 'safety_policy': 'scene_only', 'use_current_outfit_reference': False})

    extracted = _extract_targets(joined_text)
    for word in BLOCK_WORDS:
        if _norm(word) in compact or _norm(word) in extracted:
            resolved = resolve_focus_view(text=joined_text, focus_target='blocked_sensitive', focus_label=word)
            return _resolver_focus_dict(resolved, extracted)

    for word, (target, policy, prompt) in SAFE_REDIRECT.items():
        if _norm(word) in compact or _norm(word) in extracted:
            resolved = resolve_focus_view(text=joined_text, focus_target=target, focus_label=word)
            return _resolver_focus_dict(resolved, extracted)

    # V111.51.11: central resolver before legacy known-keyword matching.
    # This catches compound targets such as 脚后跟 / 膝盖后侧 / 侧腰 / 肩胛骨
    # and attaches a view_angle so prompt_builder does not default to a front portrait.
    if extracted:
        resolved = resolve_focus_view(text=joined_text, focus_label=extracted[0])
        if resolved.get('focus_target') and resolved.get('focus_match_mode') not in ('none',):
            return _resolver_focus_dict(resolved, extracted)

    # V111.51.13: semantic resolver on full text before legacy broad keyword matching.
    # This handles forms like “低头看脚尖” or “回头看后腰” even when regex extraction misses the target.
    full_resolved = resolve_focus_view(text=joined_text)
    if full_resolved.get('matched') and full_resolved.get('focus_target') not in ('', 'safe_general_outfit_detail'):
        return _resolver_focus_dict(full_resolved, extracted)

    joined = _norm(' '.join([joined_text, ' '.join(extracted)]))
    for key, category, words, prompt in KNOWN_FOCUS:
        for w in words:
            if _norm(w) and _norm(w) in joined:
                return _with_common({'focus_target': key, 'focus_category': category, 'focus_label': w, 'secondary_prompt': prompt, 'secondary_generation_allowed': True, 'focus_match_mode': 'known_keyword', 'extracted_targets': extracted, 'safety_policy': 'auto_safe', 'use_current_outfit_reference': True})

    if extracted:
        target = extracted[0]
        if target in INVALID_TARGETS:
            return _with_common({'focus_target': '', 'focus_category': '', 'focus_label': '', 'secondary_prompt': '', 'secondary_generation_allowed': False, 'focus_match_mode': 'invalid_dynamic_target', 'extracted_targets': extracted, 'safety_policy': 'scene_only', 'use_current_outfit_reference': False})
        resolved = resolve_focus_view(text=joined_text, focus_label=target)
        return _resolver_focus_dict(resolved, extracted)

    return _with_common({'focus_target': '', 'focus_category': '', 'focus_label': '', 'secondary_prompt': '', 'secondary_generation_allowed': False, 'focus_match_mode': 'none', 'extracted_targets': [], 'safety_policy': 'none', 'use_current_outfit_reference': False})


_FOCUS_ENHANCEMENT_TABLE: Dict[str, Dict[str, Any]] = {
    'legs': {
        'action': '微微抬腿，裙摆轻轻掀起一点，身体微微侧转，双腿交错站姿，手扶裙摆边缘',
        'expression': '害羞配合，微微脸红，轻咬下唇',
        'composition': '三分之二身镜头，从大腿到小腿的美观取景，腿部线条自然展示',
        'atmosphere': '温柔展示、精致优雅、配合呈现',
    },
    'tail': {
        'action': '尾巴轻晃摇曳，九尾如极光缓缓流动，手轻轻拨弄其中一条尾巴尖',
        'expression': '俏皮灵动，眼神温柔带笑',
        'composition': '全身或大半身构图，尾巴在身后展开形成视觉焦点',
        'atmosphere': '灵动可爱、狐狸感十足、魔法光效',
    },
    'ears': {
        'action': '微微侧头，正常人类耳朵与金环耳饰清楚可见，头顶不出现任何兽耳',
        'expression': '害羞、软萌、微微瞪眼',
        'composition': '上半身近景，正常人类耳朵和金环耳饰位于画面侧面焦点区域',
        'atmosphere': '耳饰精致、正常人类耳朵、无狐耳无猫耳无兽耳',
    },
    'hair': {
        'action': '银白长发轻轻飘散，发丝如银河流淌，手轻拢发梢',
        'expression': '温柔安静，眼神柔和',
        'composition': '大半身或上半身，头发作为重要视觉元素铺展开',
        'atmosphere': '发丝飘逸、柔美精致、星光闪烁',
    },
    'eyes': {
        'action': '轻轻眨眼，微微睁大眼睛，睫毛轻颤',
        'expression': '明亮有神、清澈灵动、略带好奇',
        'composition': '面部近景特写，眼睛位于黄金分割点',
        'atmosphere': '眼神清澈、灵光闪烁、情感交流',
    },
    'hands': {
        'action': '抬手，指尖轻轻比划，比心或比耶的手势自然舒展',
        'expression': '俏皮可爱，略带害羞',
        'composition': '上半身加手部特写，手势清晰可见',
        'atmosphere': '手势明确、可爱俏皮、互动感',
    },
    'headpat': {
        'action': '微微低头，头部保持正常人类头型，一脸乖巧被摸头，不出现狐狸耳朵、不出现猫耳、不出现任何兽耳',
        'expression': '乖巧、害羞、满足',
        'composition': '上半身，头顶区域留有互动空间',
        'atmosphere': '乖巧、被宠爱的感觉、温暖',
    },
    'waist': {
        'action': '轻轻侧身，手扶腰际，腰线自然展现',
        'expression': '温柔配合，微微偏头',
        'composition': '大半身，腰线位于画面中心区域',
        'atmosphere': '优雅线条、服装细节、精致剪裁',
    },
    'heel': {
        'action': '人物轻微侧身或转身，一只脚自然后撤或微微踮起，让脚后跟和鞋跟从后侧角度清楚可见',
        'expression': '神情自然，不过度卖萌，不喧宾夺主',
        'composition': '全身、三分之二身或下半身侧后视角构图，重点锁定脚后跟与鞋跟区域',
        'atmosphere': '优雅展示、后侧细节清楚、服装与鞋履关系明确',
    },
    'outfit': {
        'action': '轻轻转身，衣摆自然飘动，指尖轻触布料纹理',
        'expression': '温柔展示，略带得意',
        'composition': '全身或大半身，服装细节清晰展现',
        'atmosphere': '时尚高雅、材质细节、工艺精良',
    },
    'shoes': {
        'action': '轻轻踮脚或交错站立，展示鞋子造型',
        'expression': '俏皮配合',
        'composition': '全身或脚部以下半身取景',
        'atmosphere': '时尚造型、细节精致',
    },
    'wings': {
        'action': '光翼缓缓展开，流光羽翼轻轻扇动',
        'expression': '温柔骄傲，眼神柔和',
        'composition': '全身三分之二，翅膀展开作为背景',
        'atmosphere': '圣洁光辉、梦幻、流光溢彩',
    },
    'pose': {
        'action': '自然摆出优美姿态，腰背挺直，四肢舒展',
        'expression': '自信大方，略带俏皮',
        'composition': '全身构图，姿态明确清晰',
        'atmosphere': '姿态明确、镜头感强、表现力强',
    },
    'face': {
        'action': '微微偏头，轻轻侧脸',
        'expression': '自然柔和，笑意浅浅',
        'composition': '面部特写或上半身近景',
        'atmosphere': '自然生动、表情丰富、亲切',
    },
    'safe_general_outfit_detail': {
        'action': '自然展示目标细节，动作克制，服装和身体比例稳定',
        'expression': '神情自然，不喧宾夺主',
        'composition': '全身或三分之二身安全服装细节构图，不默认正面大头照',
        'atmosphere': '安全克制、服装导向、目标细节清楚',
    },
}


def build_focus_enhanced_prompt(
    focus_target: str = '',
    focus_label: str = '',
    mood: str = '',
    semantic_scene: str = '',
    outfit: str = '',
    outfit_prompt_suffix: str = '',
    stage_hints: str = '',
    emotion_signature: list = None,
    expression_hints: list = None,
) -> Dict[str, Any]:
    """Build an enhanced, scene-understood focus prompt instead of raw keyword translation."""
    emotion_signature = emotion_signature or []
    expression_hints = expression_hints or []
    clean_target = focus_target.replace('dynamic:', '') if focus_target.startswith('dynamic:') else focus_target
    enhancement = _FOCUS_ENHANCEMENT_TABLE.get(clean_target, {})
    if not enhancement:
        enhancement = {'action': '自然展现', 'expression': '温柔配合', 'composition': '大半身构图', 'atmosphere': '精致优雅'}
    action_part = enhancement.get('action', '')
    expression_part = enhancement.get('expression', '')
    composition_part = enhancement.get('composition', '')
    atmosphere_part = enhancement.get('atmosphere', '')
    emo_text = '，'.join(emotion_signature[:3]) if emotion_signature else ''
    expr_text = '，'.join(expression_hints[:3]) if expression_hints else ''
    emotion_part = f'，{emo_text}' if emo_text else ''
    expression_part_part = f'，{expr_text}' if expr_text else ''
    outfit_part = f'，{outfit_prompt_suffix[:120]}' if outfit_prompt_suffix else ''
    stage_part = f'，{stage_hints[:160]}' if stage_hints else ''
    enhanced = (
        f'，{action_part}'
        f'，{expression_part}{emotion_part}{expression_part_part}'
        f'，{composition_part}'
        f'，{atmosphere_part}'
        f'{outfit_part}'
        f'{stage_part}'
    )
    return {
        'focus_prompt_enhanced': True,
        'focus_prompt_style': 'scene_enhanced',
        'focus_prompt_preview': enhanced[:300],
        'enhanced_focus_prompt': enhanced,
    }
