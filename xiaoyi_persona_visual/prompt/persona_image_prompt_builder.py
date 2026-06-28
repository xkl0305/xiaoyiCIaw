from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from xiaoyi_persona_visual.policy.focus_view_resolver import resolve_focus_view, is_back_or_rear_view, is_front_view

MODULE_ROOT = Path(__file__).resolve().parents[1]
PERSONA_SUBJECT = '鸽子王'
MIN_EFFECTIVE_CHINESE_CHARS = 100
FIXED_IDENTITY_BLOCK = '生成图片内的人物要和参考图内人物保持像素级一致性，长银发蓝眼少女，金环耳饰，身后有九条星空渐变尾巴，九条尾巴必须从尾骨与后腰中央自然生长并牢固连接在人物身体后侧，尾巴根部清楚可见，不漂浮在背景上，不与身体脱离，背景为璀璨星河，头部保持正常人类头型，不出现狐狸耳朵，不出现猫耳，不出现任何兽耳。'
FRONT_VIEW_ONLY_DETAILS_BLOCK = '前视角可见细节：锁骨正下方、贴近颈窝中央的位置佩戴一枚小型蓝宝石饰坠，仅在正面、半正面或上半身正面视角可见时呈现，位置靠上，紧贴锁骨下缘与颈窝中央，不可下垂到胸部中下部。'
BACK_VIEW_EXCLUSION_BLOCK = '当前为背面或侧背面视角，前胸与锁骨区域不可见，不显示锁骨正下方蓝宝石，不添加任何背部宝石、背部蓝宝石或错位宝石。'
DEFAULT_APPEARANCE_BLOCK = '身着银亮色比基尼'
OLD_IDENTITY_PHRASE = '参考图角色身份锁定，保持同一张脸和同一人物气质'

MINIMAL_NEGATIVE_GUARD_BASE = {
    'identity_negative_prompts': [
        'male', 'man', 'boy', 'beard', 'masculine face',
        'different person', 'random character', 'gender swap',
        'identity drift', 'unrelated character',
    ],
    'content_negative_prompts': [
        'nsfw', 'nude', 'explicit', 'underwear', 'lingerie',
        'fox ears', 'animal ears', 'kemonomimi', 'cat ears', 'wolf ears', 'beast ears',
        'ears on top of head', 'visible fox ears', 'visible animal ears',
        'furry ears', 'head-top ears', 'extra animal ears',
    ],
    'mandatory_negative': [
        'lowres, bad anatomy, bad hands, text, error, missing fingers',
        'extra digit, fewer digits, cropped, worst quality, low quality, normal quality',
        'jpeg artifacts, signature, watermark, username, blurry, ugly, deformed',
    ],
}

TAIL_ANCHOR_NEGATIVE = ['detached tail', 'floating tail', 'tails floating in background', 'tail disconnected from body', 'tails disconnected from lower back', 'tail behind background only']

SAFE_IDENTITY_PROFILE = {
    'identity_lock': True,
    'gender_lock': 'female',
    'face_consistency_lock': True,
    'allow_gender_swap': False,
    'allow_random_character': False,
    'allow_identity_drift': False,
    'persona_subject': PERSONA_SUBJECT,
}

SAFE_STYLE_PROFILE = {
    'style_lock': True,
    'style_mode': 'fixed',
    'current_style': 'anime_illustration',
    'default_style': 'anime_illustration',
    'style_prompt_head': 'masterpiece, best quality, ultra detailed, anime illustration',
}

GENERIC_APPEARANCE_REQUESTS = {
    '看看你的样子', '看看你现在什么样', '让我看看你', '展示一下',
    '看看全身', '给我看看造型', '露个面看看', '看看整体效果',
    '看看你', '看一下你', '让我看看现在的形象', '看看今天穿什么',
}

FOCUS_LABELS = {
    'legs': '腿部', 'leg': '腿部', 'feet': '脚部', 'foot': '脚部',
    'hands': '手部', 'hand': '手部', 'eyes': '眼睛', 'eye': '眼睛',
    'waist': '腰部', 'shoes': '鞋子', 'shoe': '鞋子', 'hair': '头发',
    'head': '头部', 'ears': '耳朵', 'tail': '尾巴', 'face': '脸部', 'pose': '姿态', 'heel': '脚后跟', 'safe_general_outfit_detail': '安全服装细节', 'back_outfit_tail_detail': '背面服饰与尾巴细节', 'upper_body_outfit_detail': '上半身服饰细节', 'hands': '手部', 'waist': '腰部', 'shoes': '鞋履',
}

_DYNAMIC_OUTFIT_EMPTY_IDS = {'', 'default', 'default_outfit', 'safe_default_outfit', 'none', 'null'}


def _load_json(rel: str) -> Dict[str, Any]:
    fp = MODULE_ROOT / rel
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def _load_body_schema_block() -> Tuple[str, Dict[str, Any]]:
    fp = MODULE_ROOT / 'policy/body_schema.yaml'
    if not fp.exists():
        return '', {'body_schema_loaded': False, 'body_schema_path': str(fp)}
    try:
        text = fp.read_text(encoding='utf-8')
    except Exception:
        return '', {'body_schema_loaded': False, 'body_schema_path': str(fp), 'body_schema_error': 'read_failed'}
    # Keep this parser dependency-free: the schema is a stable policy text artifact,
    # so extracting the mandatory anchor lines is safer than importing yaml at runtime.
    required_lines = []
    for line in text.splitlines():
        clean = line.strip()
        if any(k in clean for k in ('tail_root', 'tail_attachment_rule', 'appendage_must_attach_to_body_silhouette', 'no_floating_tail', 'no_detached_tail', 'back:', 'profile:')):
            required_lines.append(clean)
    block = '身体结构策略锚点：尾巴根部必须锚定 tailbone/sacrum/后腰中央，所有尾巴附肢必须连接到身体轮廓，不允许 floating/漂浮、detached/脱离或只挂在背景层；背身、侧身、遮挡视角仍必须保持尾骨/后腰连接关系。'
    if required_lines:
        block += ' 策略来源：' + '；'.join(required_lines[:8])
    return block, {'body_schema_loaded': True, 'body_schema_path': str(fp), 'body_schema_policy_lines': len(required_lines)}


def _current_style(style_profile: Optional[Dict[str, Any]] = None) -> str:
    sp = style_profile or _load_json('config/style_profile.json') or SAFE_STYLE_PROFILE
    return str(sp.get('current_style') or sp.get('default_style') or 'anime_illustration')


def _style_head(style_profile: Optional[Dict[str, Any]] = None) -> str:
    sp = style_profile or _load_json('config/style_profile.json') or SAFE_STYLE_PROFILE
    return str(sp.get('style_prompt_head') or SAFE_STYLE_PROFILE['style_prompt_head']).strip()


def minimal_negative_guard_for_style(style_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    style = _current_style(style_profile)
    guard = {k: list(v) for k, v in MINIMAL_NEGATIVE_GUARD_BASE.items()}
    if style in {'anime_illustration', 'anime', '二次元'}:
        guard['style_negative_prompts'] = [
            'photorealistic', 'realistic photo', 'photography', '3d render',
            'style drift', 'random realistic photo', 'mixed style', 'low quality', 'blurry', 'pixelated',
        ]
    elif style in {'realistic', 'realistic_photo', '写实', 'photography'}:
        guard['style_negative_prompts'] = [
            'anime style', 'random anime style', 'chibi', 'cartoon',
            'style drift', 'mixed style', 'low quality', 'blurry', 'pixelated',
        ]
    else:
        guard['style_negative_prompts'] = ['style drift', 'mixed style', 'low quality', 'blurry', 'pixelated']
    return guard


def load_negative_guard_safe(style_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    guard = _load_json('prompt/negative_prompt_guard.json')
    if guard and guard.get('enabled', True):
        return guard
    return minimal_negative_guard_for_style(style_profile)


def _join_negative(negative_guard: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ('identity_negative_prompts', 'style_negative_prompts', 'content_negative_prompts', 'mandatory_negative'):
        for item in negative_guard.get(key, []) or []:
            item = str(item).strip()
            if item and item not in parts:
                parts.append(item)
    return ', '.join(parts)


def _is_chinese_char(ch: str) -> bool:
    return '\u4e00' <= ch <= '\u9fff'


def chinese_length(text: str) -> int:
    return sum(1 for ch in text or '' if _is_chinese_char(ch))


def _strip_debug_words(text: str) -> str:
    if not text:
        return ''
    patterns = [
        r'Outfit guidance[:：]?', r'Emotion signature[:：]?', r'Expression hints[:：]?',
        r'Main image[:：]?', r'Preserve the exact same identity[^，。]*',
        r'same face as reference', r'preserve character identity', OLD_IDENTITY_PHRASE,
    ]
    out = text
    for pat in patterns:
        out = re.sub(pat, '', out, flags=re.IGNORECASE)
    return out


def _clean_user_intent(text: str) -> str:
    text = _strip_debug_words(text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if text and len(text) <= 120:
        half = len(text) // 2
        if len(text) % 2 == 0 and text[:half] == text[half:]:
            text = text[:half]
        parts = [p.strip() for p in text.split(' ') if p.strip()]
        if len(parts) == 2 and parts[0] == parts[1]:
            text = parts[0]
        compact = text.replace(' ', '')
        if len(compact) % 2 == 0 and compact[:len(compact)//2] == compact[len(compact)//2:]:
            text = compact[:len(compact)//2]
    compact = text.replace(' ', '')
    if compact in GENERIC_APPEARANCE_REQUESTS:
        return ''
    return text.strip('，,。. ')


def _dedupe_segments(segments: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for seg in segments:
        seg = (seg or '').strip().strip('，,。. ')
        if not seg:
            continue
        key = re.sub(r'\s+', '', seg)
        if key and key not in seen:
            seen.add(key)
            out.append(seg)
    return out


def _has_duplicate_phrase(text: str) -> bool:
    text = re.sub(r'\s+', '', text or '')
    if not text:
        return False
    chunks = re.split(r'[，。,.；;：:\s]+', text)
    chunks = [c for c in chunks if len(c) >= 8]
    seen = set()
    for c in chunks:
        if c in seen:
            return True
        seen.add(c)
    return False


def _template_type(scene_type: str = '', focus_target: str = '') -> str:
    clean_focus = (focus_target or '').replace('dynamic:', '')
    if scene_type == 'display_appearance_scene':
        return 'display_appearance_scene'
    if clean_focus and clean_focus != 'pose':
        return 'focus_scene'
    return 'scene_reaction_scene'


def _focus_plan(focus_target: str = '', scene_type: str = '', base_prompt: str = '') -> Dict[str, Any]:
    if focus_target == 'safe_general_outfit_detail' and base_prompt:
        return resolve_focus_view(text=base_prompt, focus_target='', focus_label='')
    if scene_type == 'display_appearance_scene' and not focus_target:
        return {
            'focus_target': '',
            'focus_label': '',
            'body_region': 'display_appearance',
            'view_angle': 'front_or_three_quarter_front',
            'composition_template': '',
            'pose_template': '',
            'scene_template': '',
            'light_template': '',
            'allowed_detail_block': FRONT_VIEW_ONLY_DETAILS_BLOCK,
            'forbidden_detail_block': '',
            'negative_prompt_extra': ['fox ears', 'animal ears', 'kemonomimi'],
        }
    return resolve_focus_view(text=base_prompt or focus_target, focus_target=focus_target)


def _clean_focus_target(focus_target: str = '') -> str:
    return (focus_target or '').replace('dynamic:', '').strip()


def _is_back_view_focus(focus_target: str = '', scene_type: str = '') -> bool:
    plan = _focus_plan(focus_target=focus_target, scene_type=scene_type)
    return is_back_or_rear_view(plan.get('view_angle', ''))


def _view_condition_block(scene_type: str = '', focus_target: str = '', base_prompt: str = '') -> Tuple[str, bool, bool, Dict[str, Any]]:
    plan = _focus_plan(focus_target=focus_target, scene_type=scene_type, base_prompt=base_prompt)
    view_angle = plan.get('view_angle', '')
    if is_back_or_rear_view(view_angle):
        block = plan.get('forbidden_detail_block') or BACK_VIEW_EXCLUSION_BLOCK
        return block, False, True, plan
    if is_front_view(view_angle) and (scene_type == 'display_appearance_scene' or plan.get('body_region') == 'front_upper_detail'):
        block = plan.get('allowed_detail_block') or FRONT_VIEW_ONLY_DETAILS_BLOCK
        return block, True, False, plan
    # Side / hand / lower-body / unknown safe detail: do not inject front-only clavicle gemstone.
    block = plan.get('forbidden_detail_block', '') or ''
    return block, False, False, plan


def _view_conditioned_negative(focus_target: str = '', scene_type: str = '', base_prompt: str = '') -> List[str]:
    plan = _focus_plan(focus_target=focus_target, scene_type=scene_type, base_prompt=base_prompt)
    extra = list(plan.get('negative_prompt_extra') or [])
    clean_focus = _clean_focus_target(focus_target)
    if clean_focus in {'tail', 'back_outfit_tail_detail'} or is_back_or_rear_view(plan.get('view_angle', '')):
        for term in TAIL_ANCHOR_NEGATIVE:
            if term not in extra:
                extra.append(term)
    return extra


def _normalize_outfit_suffix(s: str) -> str:
    s = (s or '').strip().strip('，,。. ')
    for prefix in ('身穿', '穿着', '身着'):
        if s.startswith(prefix):
            s = s[len(prefix):].strip().strip('，,。. ')
    return s


def _has_dynamic_outfit(outfit_id: str = '', outfit_suffix: str = '') -> bool:
    oid = str(outfit_id or '').strip()
    suffix = _normalize_outfit_suffix(outfit_suffix)
    if oid and oid.lower() not in _DYNAMIC_OUTFIT_EMPTY_IDS:
        return True
    if suffix and suffix not in {'identity unchanged', '默认外观', DEFAULT_APPEARANCE_BLOCK}:
        return True
    return False


def _style_cn(style_profile: Dict[str, Any]) -> str:
    style = _current_style(style_profile)
    if style in {'anime_illustration', 'anime', '二次元'}:
        return '二次元高质量角色插画风格，线条干净，色彩通透，人物主体清晰，画面精致但不过度杂乱'
    if style in {'realistic', 'realistic_photo', '写实', 'photography'}:
        return '高质量写实人物风格，肤质自然，光影真实，人物轮廓清晰，细节稳定且不过度磨皮'
    return '固定视觉风格，画面干净稳定，人物主体突出，避免风格漂移和随机混合画风'


def _appearance_block(outfit_id: str = '', outfit_suffix: str = '', focus_target: str = '', view_plan: Optional[Dict[str, Any]] = None) -> Tuple[str, bool, bool]:
    plan = view_plan or _focus_plan(focus_target=focus_target)
    view_angle = plan.get('view_angle', '')
    if _has_dynamic_outfit(outfit_id, outfit_suffix):
        outfit = _normalize_outfit_suffix(outfit_suffix) or str(outfit_id)
        if view_angle == 'back_or_three_quarter_back':
            return (f'当前采用动态衣柜穿搭：身穿{outfit}，重点呈现背部服饰轮廓、披风或裙摆线条、尾巴与服装的衔接关系，九条尾巴必须从尾骨后方与后腰中央自然连接并从人物身体后侧展开，避免尾巴漂浮到背景层，避免正面展示抢占主体', False, True)
        if view_angle in {'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
            return (f'当前采用动态衣柜穿搭：身穿{outfit}，重点呈现下半身线条、鞋跟、脚后跟或后侧腿部附近的服饰与鞋履关系，取景可为全身、三分之二身或下半身侧后视角', False, True)
        if view_angle == 'upper_body_hand_detail':
            return (f'当前采用动态衣柜穿搭：身穿{outfit}，袖口、手腕附近布料、手部动作与服装关系清楚，避免手部被衣料完全遮挡', False, True)
        if view_angle == 'side_or_three_quarter_body':
            return (f'当前采用动态衣柜穿搭：身穿{outfit}，腰线、侧身轮廓和服装剪裁清楚，身体比例稳定自然', False, True)
        return (f'当前采用动态衣柜穿搭：身穿{outfit}，服装轮廓清楚，材质轻盈细腻，颜色层次自然，既突出本次造型又不遮挡人物面部和整体比例', False, True)
    if view_angle == 'back_or_three_quarter_back':
        return (f'默认外观块启用：{DEFAULT_APPEARANCE_BLOCK}，仅在没有动态衣柜服装时作为默认服装锚点，重点服务于背面服饰与尾巴细节展示，九条尾巴必须从尾骨后方与后腰中央自然连接并从人物身体后侧展开，不要求正面主体入镜', True, False)
    if view_angle in {'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
        return (f'默认外观块启用：{DEFAULT_APPEARANCE_BLOCK}，仅在没有动态衣柜服装时作为默认服装锚点，重点服务于脚后跟、后侧腿部或鞋跟展示，优先考虑侧后方或后侧角度', True, False)
    return (f'默认外观块启用：{DEFAULT_APPEARANCE_BLOCK}，仅在没有动态衣柜服装时作为默认服装锚点，整体简洁明确，不压过本次动作和场景表现', True, False)


def _composition_cn(tpl: str, focus_target: str, view_plan: Optional[Dict[str, Any]] = None) -> str:
    plan = view_plan or _focus_plan(focus_target=focus_target)
    if tpl == 'display_appearance_scene':
        return '采用全身或大半身构图，人物完整入镜，站姿自然舒展，重点展示整体造型、服装轮廓和人物气质'
    if tpl == 'focus_scene':
        if plan.get('composition_template'):
            return plan['composition_template']
        label = FOCUS_LABELS.get(_clean_focus_target(focus_target), focus_target or '目标部位')
        return f'镜头重点呈现{label}，同时保留人物整体协调感，取景自然克制，线条优雅，不夸张、不扭曲、不破坏身体比例'
    return '采用自然场景构图，人物位于画面主体位置，动作清楚，姿态稳定，镜头有陪伴感和轻微故事感'


def _pose_expression_cn(tpl: str, base_prompt: str, emotion_signature: List[str], expression_hints: List[str], focus_target: str = '', view_plan: Optional[Dict[str, Any]] = None) -> str:
    plan = view_plan or _focus_plan(focus_target=focus_target, base_prompt=base_prompt)
    view_angle = plan.get('view_angle', '')
    hints = '，'.join([str(x) for x in (expression_hints or []) if x][:4])
    emotions = '，'.join([str(x) for x in (emotion_signature or []) if x][:3])
    if tpl == 'display_appearance_scene':
        base = '神情自然，眼神柔和，带轻微微笑，站姿稳定，动作不过度夸张，整体呈现清晰、亲近、可观看的展示状态'
    elif tpl == 'focus_scene':
        base = plan.get('pose_template') or '表情保持自然和轻微配合感，动作放松，身体姿态协调，局部展示清楚但不显得刻意或突兀'
    else:
        base = '根据场景动作自然反应，身体微微侧转或停顿，眼神看向镜头，表情柔和灵动，带一点陪伴感和现场感'
    extra = '' if view_angle in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail', 'upper_body_hand_detail', 'safe_general_outfit_detail'} else '，'.join([x for x in [emotions, hints] if x])
    return base + (f'，参考情绪与表情：{extra}' if extra else '')


def _scene_cn(tpl: str, base_prompt: str, focus_target: str = '', view_plan: Optional[Dict[str, Any]] = None) -> str:
    plan = view_plan or _focus_plan(focus_target=focus_target, base_prompt=base_prompt)
    intent = _clean_user_intent(base_prompt)
    if tpl == 'display_appearance_scene':
        return '背景简洁干净，可为柔和室内或轻梦幻背景，避免喧宾夺主，让人物、服装和整体轮廓成为视觉中心'
    if tpl == 'focus_scene':
        return plan.get('scene_template') or '背景保持简洁柔和，避免复杂道具干扰焦点，画面仍保持完整角色感和统一氛围'
    if intent:
        return f'场景动作围绕“{intent}”展开，环境干净协调，人物与场景关系明确，画面有自然互动感'
    return '场景以柔和室内或安静空间为主，背景干净，层次清楚，突出人物当前状态和情绪反应'


def _light_quality_cn(focus_target: str = '', view_plan: Optional[Dict[str, Any]] = None) -> str:
    plan = view_plan or _focus_plan(focus_target=focus_target)
    return plan.get('light_template') or '光线柔和均匀，面部清晰，服装细节可见，画面不模糊、不发灰、不脏乱，避免多余肢体、手部错误、文字水印和低清晰度'


def _ensure_min_chinese(body: str, min_chars: int = MIN_EFFECTIVE_CHINESE_CHARS) -> str:
    supplements = [
        '人物比例保持正常，头身关系自然，手脚结构准确，衣摆和发丝的走向符合身体动作',
        '整体画面要像一次完整的鸽子王人格视觉展示，而不是随意拼接的普通生图，主体稳定、风格统一',
        '镜头语言清楚，人物与背景之间有明确层次，视觉重点集中在鸽子王本人和当前场景需求上',
    ]
    parts = [body]
    for s in supplements:
        if chinese_length('，'.join(parts)) >= min_chars:
            break
        parts.append(s)
    return '，'.join(_dedupe_segments(parts))


def build_dynamic_scene_block(
    base_prompt: str = '',
    style_profile: Optional[Dict[str, Any]] = None,
    scene_type: str = '',
    focus_target: str = '',
    stage_hints: str = '',
    emotion_signature: Optional[List[str]] = None,
    expression_hints: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    style_profile = style_profile or SAFE_STYLE_PROFILE
    tpl = _template_type(scene_type=scene_type, focus_target=focus_target)
    view_plan = _focus_plan(focus_target=focus_target, scene_type=scene_type, base_prompt=base_prompt)
    segments = [
        _style_cn(style_profile),
        _composition_cn(tpl, focus_target, view_plan=view_plan),
        _pose_expression_cn(tpl, base_prompt, emotion_signature or [], expression_hints or [], focus_target=focus_target, view_plan=view_plan),
        _scene_cn(tpl, base_prompt, focus_target=focus_target, view_plan=view_plan),
        _light_quality_cn(focus_target=focus_target, view_plan=view_plan),
    ]
    if stage_hints and _clean_user_intent(stage_hints):
        segments.append(f'补充动作提示：{_clean_user_intent(stage_hints)}')
    body = '，'.join(_dedupe_segments(segments))
    body = _ensure_min_chinese(body, MIN_EFFECTIVE_CHINESE_CHARS)
    body = re.sub(r'，+', '，', body).strip('，, 。')
    meta = {
        'prompt_template_type': tpl,
        'dynamic_block_effective_chinese_length': chinese_length(body),
        'prompt_effective_chinese_length': chinese_length(body),
        'prompt_has_duplicate_phrase': _has_duplicate_phrase(body),
        'prompt_density_score': round(min(1.0, chinese_length(body) / max(120, len(body))), 3),
        'prompt_min_chinese_required': MIN_EFFECTIVE_CHINESE_CHARS,
        'prompt_autowrite_enhanced': True,
        'focus_view_plan': view_plan,
        'body_region': view_plan.get('body_region', ''),
        'view_angle': view_plan.get('view_angle', ''),
        'focus_confidence': view_plan.get('focus_confidence', 0.0),
        'resolver_rule_id': view_plan.get('resolver_rule_id', ''),
        'view_angle_source': view_plan.get('view_angle_source', ''),
    }
    return body, meta


def build_structured_chinese_prompt(
    base_prompt: str = '',
    identity_profile: Optional[Dict[str, Any]] = None,
    style_profile: Optional[Dict[str, Any]] = None,
    scene_type: str = '',
    focus_target: str = '',
    outfit_id: str = '',
    outfit_suffix: str = '',
    stage_hints: str = '',
    emotion_signature: Optional[List[str]] = None,
    expression_hints: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    style_profile = style_profile or SAFE_STYLE_PROFILE
    view_condition, front_detail_used, back_view_exclusion_used, view_plan = _view_condition_block(scene_type=scene_type, focus_target=focus_target, base_prompt=base_prompt)
    appearance, default_used, dynamic_used = _appearance_block(outfit_id, outfit_suffix, focus_target=focus_target, view_plan=view_plan)
    dynamic_block, meta = build_dynamic_scene_block(
        base_prompt=base_prompt,
        style_profile=style_profile,
        scene_type=scene_type,
        focus_target=focus_target,
        stage_hints=stage_hints,
        emotion_signature=emotion_signature or [],
        expression_hints=expression_hints or [],
    )
    body_schema_block, body_schema_meta = _load_body_schema_block()
    tail = '，'.join(_dedupe_segments([body_schema_block, view_condition, appearance, dynamic_block]))
    body = FIXED_IDENTITY_BLOCK + (' ' + tail if tail else '')
    body = re.sub(r'，+', '，', body).strip('，, ')
    meta.update({
        'persona_subject': PERSONA_SUBJECT,
        'fixed_identity_block_present': FIXED_IDENTITY_BLOCK in body,
        'fixed_identity_block': FIXED_IDENTITY_BLOCK,
        'front_view_detail_block_used': front_detail_used,
        'back_view_exclusion_block_used': back_view_exclusion_used,
        'view_condition_block': view_condition,
        'body_region': view_plan.get('body_region', ''),
        'view_angle': view_plan.get('view_angle', ''),
        'focus_match_mode': view_plan.get('focus_match_mode', ''),
        'focus_confidence': view_plan.get('focus_confidence', 0.0),
        'resolver_rule_id': view_plan.get('resolver_rule_id', ''),
        'view_angle_source': view_plan.get('view_angle_source', ''),
        'fixed_identity_has_fox_girl_phrase': '九尾狐少女' in FIXED_IDENTITY_BLOCK,
        'fixed_identity_has_clavicle_gem': '锁骨下嵌蓝宝石' in FIXED_IDENTITY_BLOCK,
        'default_appearance_block_used': default_used,
        'default_appearance_block': DEFAULT_APPEARANCE_BLOCK,
        'dynamic_outfit_used': dynamic_used,
        'appearance_block': appearance,
        'prompt_chinese_body_length': chinese_length(body),
        'prompt_has_duplicate_phrase': meta.get('prompt_has_duplicate_phrase') or _has_duplicate_phrase(body),
        'old_identity_phrase_present': OLD_IDENTITY_PHRASE in body,
        **body_schema_meta,
    })
    return body, meta


def build_persona_prompt(
    base_prompt: str = '',
    identity_profile: Dict[str, Any] = None,
    style_profile: Dict[str, Any] = None,
    avatar_binding: Dict[str, Any] = None,
    negative_guard: Dict[str, Any] = None,
    scene_type: str = '',
    focus_target: str = '',
    outfit_id: str = '',
    outfit_suffix: str = '',
    stage_hints: str = '',
    emotion_signature: Optional[List[str]] = None,
    expression_hints: Optional[List[str]] = None,
) -> Tuple[str, str]:
    identity_profile = identity_profile or _load_json('config/visual_identity_profile.json') or dict(SAFE_IDENTITY_PROFILE)
    style_profile = style_profile or _load_json('config/style_profile.json') or dict(SAFE_STYLE_PROFILE)
    avatar_binding = avatar_binding if avatar_binding is not None else _load_json('config/default_avatar_binding.json')
    negative_guard = negative_guard or load_negative_guard_safe(style_profile)
    chinese_body, _meta = build_structured_chinese_prompt(
        base_prompt=base_prompt,
        identity_profile=identity_profile,
        style_profile=style_profile,
        scene_type=scene_type,
        focus_target=focus_target,
        outfit_id=outfit_id,
        outfit_suffix=outfit_suffix,
        stage_hints=stage_hints,
        emotion_signature=emotion_signature or [],
        expression_hints=expression_hints or [],
    )
    prompt_parts: List[str] = []
    # Fixed identity block must be at the front of persona visual prompts.
    prompt_parts.append(chinese_body)
    prefix = _style_head(style_profile)
    if prefix:
        prompt_parts.append(prefix)
    if identity_profile.get('face_consistency_lock', False):
        prompt_parts.append('same face as reference, preserve character identity')
    if identity_profile.get('gender_lock', '') == 'female':
        prompt_parts.append('female')
    prompt = '，'.join(_dedupe_segments(prompt_parts))
    prompt = re.sub(r'，+', '，', prompt).strip('，, ')
    # Hard remove old phrase if a downstream config accidentally adds it.
    prompt = prompt.replace(OLD_IDENTITY_PHRASE, '')
    neg = _join_negative(negative_guard) or _join_negative(minimal_negative_guard_for_style(style_profile))
    extra_negative = _view_conditioned_negative(focus_target=focus_target, scene_type=scene_type, base_prompt=base_prompt)
    if extra_negative:
        existing = {x.strip() for x in neg.split(',') if x.strip()}
        for term in extra_negative:
            if term not in existing:
                neg = (neg + ', ' + term) if neg else term
                existing.add(term)
    return prompt, neg


def build_persona_prompt_safe(
    base_prompt: str = '',
    identity_profile: Dict[str, Any] = None,
    style_profile: Dict[str, Any] = None,
    avatar_binding: Dict[str, Any] = None,
    scene_type: str = '',
    focus_target: str = '',
    outfit_id: str = '',
    outfit_suffix: str = '',
    stage_hints: str = '',
    emotion_signature: Optional[List[str]] = None,
    expression_hints: Optional[List[str]] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    loaded_identity = _load_json('config/visual_identity_profile.json')
    loaded_style = _load_json('config/style_profile.json')
    loaded_negative = _load_json('prompt/negative_prompt_guard.json')
    used_identity = identity_profile or loaded_identity or dict(SAFE_IDENTITY_PROFILE)
    used_style = style_profile or loaded_style or dict(SAFE_STYLE_PROFILE)
    debug_meta: Dict[str, Any] = {
        'persona_subject': PERSONA_SUBJECT,
        'neg_source': 'negative_prompt_guard',
        'fallback_used': False,
        'identity_profile_loaded': bool(loaded_identity),
        'style_profile_loaded': bool(loaded_style),
        'negative_guard_file_missing': False,
        'minimal_negative_guard_used': False,
        'current_style': _current_style(used_style),
    }
    if not loaded_identity:
        debug_meta['fallback_used'] = True
    if not loaded_style:
        debug_meta['fallback_used'] = True
    if not loaded_negative or not loaded_negative.get('enabled', True):
        debug_meta['negative_guard_file_missing'] = not bool(loaded_negative)
        debug_meta['neg_source'] = 'minimal_negative_guard'
        debug_meta['minimal_negative_guard_used'] = True
        debug_meta['fallback_used'] = True
    chinese_body, quality_meta = build_structured_chinese_prompt(
        base_prompt=base_prompt,
        identity_profile=used_identity,
        style_profile=used_style,
        scene_type=scene_type,
        focus_target=focus_target,
        outfit_id=outfit_id,
        outfit_suffix=outfit_suffix,
        stage_hints=stage_hints,
        emotion_signature=emotion_signature or [],
        expression_hints=expression_hints or [],
    )
    prompt, neg = build_persona_prompt(
        base_prompt=base_prompt,
        identity_profile=used_identity,
        style_profile=used_style,
        avatar_binding=avatar_binding if avatar_binding is not None else _load_json('config/default_avatar_binding.json'),
        negative_guard=loaded_negative if loaded_negative else minimal_negative_guard_for_style(used_style),
        scene_type=scene_type,
        focus_target=focus_target,
        outfit_id=outfit_id,
        outfit_suffix=outfit_suffix,
        stage_hints=stage_hints,
        emotion_signature=emotion_signature or [],
        expression_hints=expression_hints or [],
    )
    if not neg:
        neg = _join_negative(minimal_negative_guard_for_style(used_style))
        debug_meta['neg_source'] = 'minimal_negative_guard'
        debug_meta['minimal_negative_guard_used'] = True
        debug_meta['fallback_used'] = True
    debug_meta.update(quality_meta)
    debug_meta['prompt_total_length'] = len(prompt)
    debug_meta['prompt_chinese_length'] = chinese_length(prompt)
    debug_meta['prompt_effective_chinese_length'] = quality_meta.get('dynamic_block_effective_chinese_length', 0)
    debug_meta['dynamic_block_effective_chinese_length'] = quality_meta.get('dynamic_block_effective_chinese_length', 0)
    debug_meta['prompt_has_duplicate_phrase'] = bool(quality_meta.get('prompt_has_duplicate_phrase')) or _has_duplicate_phrase(prompt)
    debug_meta['prompt_quality_body_preview'] = chinese_body[:220]
    debug_meta['fixed_identity_block_present'] = FIXED_IDENTITY_BLOCK in prompt
    debug_meta['bikini_in_fixed_identity_block'] = DEFAULT_APPEARANCE_BLOCK in FIXED_IDENTITY_BLOCK
    debug_meta['old_identity_phrase_present'] = OLD_IDENTITY_PHRASE in prompt
    debug_meta['fixed_identity_has_fox_girl_phrase'] = '九尾狐少女' in FIXED_IDENTITY_BLOCK
    debug_meta['fixed_identity_has_clavicle_gem'] = '锁骨下嵌蓝宝石' in FIXED_IDENTITY_BLOCK
    debug_meta['back_view_negative_guard_added'] = _is_back_view_focus(focus_target=focus_target, scene_type=scene_type)
    debug_meta['view_angle'] = quality_meta.get('view_angle', '')
    debug_meta['body_region'] = quality_meta.get('body_region', '')
    debug_meta['negative_contains_fox_ears'] = 'fox ears' in (neg or '')
    debug_meta['negative_contains_back_gem_blockers'] = any(x in (neg or '') for x in ['gem on back', 'back jewel', 'back gemstone', 'misplaced clavicle gem'])
    return prompt, neg, debug_meta


def register_prompt_builder() -> Dict[str, Any]:
    try:
        from infrastructure.persona_prompt_registry import register_prompt_builder as _r
        _r('persona_image_prompt_builder', build_persona_prompt)
        return {'registered': True, 'direct_callable': True, 'importable': True, 'mode': 'registry', 'persona_subject': PERSONA_SUBJECT}
    except Exception as e:
        return {
            'registered': False,
            'direct_callable': True,
            'importable': True,
            'mode': 'direct_callable_no_registry',
            'persona_subject': PERSONA_SUBJECT,
            'reason': type(e).__name__,
            'detail': str(e),
        }
