from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# V111.51.13: lightweight semantic parser in front of focus_view_resolver.
# It extracts modifiers and multi-focus hints so unknown/compound requests do not
# collapse into a generic front-facing template.

PUNCT_RE = re.compile(r'[\s,，。.!！?？:：;；"“”\'’‘、_\-]+')

STOP_PREFIXES = ['鸽子王的', '你的', '你这个', '我的', '这个', '那个', '这边', '那边', '一下', '一张']
STOP_SUFFIXES = ['一下', '看看', '看一下', '照片', '图片', '图', '照', '给我看', '来一张', '来张']

COMMAND_WORDS = ['看看', '看一下', '给我看', '让我看', '来张', '拍张', '生成', '画', '出一张', '展示', '摆个', '比个', '摸摸', '摸一下', 'rua一下', 'rua', '低头看', '回头看']

AMBIGUOUS_TARGETS = {'那里', '那边', '这里', '这边', '下面', '上面', '里面', '外面', '附近', '旁边', '那个地方', '这个地方', '那块', '这块'}

LEFT_WORDS = ['左脚', '左手', '左腿', '左边', '左侧', '左']
RIGHT_WORDS = ['右脚', '右手', '右腿', '右边', '右侧', '右']
BOTH_WORDS = ['双脚', '双手', '双腿', '两只脚', '两只手', '两条腿', '左右']

REAR_WORDS = ['后侧', '背面', '背后', '后面', '后方', '后部', '背影', '从后', '侧后', '后视角', '后背', '后腰', '后颈', '后脚跟', '脚后跟', '膝盖后侧', '小腿后侧', '大腿后侧']
FRONT_WORDS = ['正面', '前面', '前侧', '半正面', '面向镜头', '正视', '锁骨', '颈窝', '脸', '眼睛']
SIDE_WORDS = ['侧面', '侧边', '侧身', '侧腰', '侧脸', '侧后', '侧视角']
LOW_WORDS = ['低机位', '低角度', '从下往上', '地面视角', '贴地', '脚底', '鞋底', '足底']
TOP_WORDS = ['俯视', '从上往下', '高机位', '头顶']

INNER_WORDS = ['内侧', '掌心', '手心', '腿内侧', '脚内侧']
OUTER_WORDS = ['外侧', '手背', '脚背', '腿外侧', '鞋面']
BACK_SURFACE_WORDS = ['手背', '后背', '背部', '背面', '脚后跟', '后脚踝', '膝盖后侧']
BOTTOM_SURFACE_WORDS = ['脚底', '鞋底', '足底', '鞋跟底部']
TOP_SURFACE_WORDS = ['头顶', '发顶', '肩头']

UPPER_WORDS = ['上半身', '脸', '眼睛', '头发', '头部', '脖子', '锁骨', '肩', '手', '手腕', '手背', '掌心', '指甲']
MID_WORDS = ['腰', '侧腰', '腹部', '肚子', '小腹', '后腰']
LOWER_WORDS = ['腿', '膝盖', '小腿', '大腿', '脚', '鞋', '脚踝', '脚后跟', '鞋底', '脚尖']

ACTION_HINTS = {
    'turn_around': ['回头', '转身', '背过身', '侧身', '回身'],
    'look_down': ['低头', '低头看'],
    'lift_foot': ['抬脚', '踮脚', '翘脚', '脚抬起来'],
    'raise_hand': ['抬手', '挥手', '比心', '比耶'],
    'sit': ['坐下', '坐着'],
    'squat': ['蹲下', '蹲着'],
    'headpat': ['摸摸头', '摸头', '被摸头', '揉揉头', '摸一下头', 'rua'],
}

FOCUS_ALIASES: List[Tuple[str, List[str]]] = [
    ('heel', ['脚后跟', '后脚跟', '脚跟', '足跟', '鞋跟', '后脚踝', '脚踝后侧', '膝盖后侧', '膝盖后面', '腿弯', '后膝', '小腿后侧', '大腿后侧', '后腿']),
    ('sole', ['脚底板', '脚掌', '脚底', '足底', '足掌', '鞋底', '脚板', '鞋底纹路', '鞋跟底部']),
    ('back_outfit_tail_detail', ['后背', '背影', '背部', '肩胛骨', '肩胛', '背脊', '脊背', '后腰', '腰背']),
    ('upper_body_outfit_detail', ['锁骨', '颈窝', '项链', '蓝宝石', '胸口饰品', '上半身', '衣领', '领口']),
    ('hands', ['手腕', '手背', '掌心', '手心', '指尖', '指甲', '手指', '手', '手肘', '肘窝']),
    ('waist', ['侧腰', '腰线', '腰身', '腰部', '腰', '腹部', '肚子', '小腹']),
    ('legs', ['膝盖后侧', '膝盖后面', '腿弯', '小腿后侧', '大腿后侧', '大腿', '小腿', '膝盖', '腿']),
    ('shoes', ['脚尖', '脚背', '脚趾', '脚踝', '鞋面', '鞋尖', '鞋子', '高跟鞋', '靴子', '脚', '鞋']),
    ('tail', ['九条尾巴', '尾巴尖', '尾巴毛', '尾巴']),
    ('hair', ['头发', '发丝', '长发', '刘海', '发饰', '发夹', '发尾']),
    ('eyes', ['眼睛', '眼神', '瞳孔', '睫毛', '眨眼']),
    ('face', ['表情', '笑脸', '侧脸', '害羞脸', '脸红', '脸', '嘴', '鼻子', '下巴']),
    ('ears', ['金环耳饰', '耳环', '耳饰', '耳垂', '耳朵']),
    ('wings', ['翅膀', '羽翼', '光翼', '蝴蝶翼']),
    ('headpat', ['摸摸头', '摸头', '被摸头', '揉揉头', '摸一下头', 'rua']),
]


def norm(text: str) -> str:
    return PUNCT_RE.sub('', text or '').lower()


def _contains_any(compact: str, words: List[str]) -> str:
    best = ''
    for word in words:
        nw = norm(word)
        if nw and nw in compact and len(nw) > len(norm(best)):
            best = word
    return best


def _all_matches(compact: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for canonical, words in FOCUS_ALIASES:
        for word in words:
            nw = norm(word)
            if nw and nw in compact:
                out.append({'canonical': canonical, 'keyword': word, 'span_length': len(nw), 'score': len(nw) * 10})
    out.sort(key=lambda x: (x['score'], x['span_length']), reverse=True)
    # Deduplicate by canonical but keep strongest keyword.
    seen = set()
    deduped = []
    for item in out:
        if item['canonical'] in seen:
            continue
        seen.add(item['canonical'])
        deduped.append(item)
    return deduped


def _clean_query(text: str) -> str:
    compact = norm(text)
    for w in COMMAND_WORDS:
        compact = compact.replace(norm(w), '')
    for prefix in STOP_PREFIXES:
        np = norm(prefix)
        if compact.startswith(np):
            compact = compact[len(np):]
    for suffix in STOP_SUFFIXES:
        ns = norm(suffix)
        if compact.endswith(ns):
            compact = compact[:-len(ns)]
    return compact


def _lateral_side(compact: str) -> str:
    if _contains_any(compact, BOTH_WORDS):
        return 'both'
    if _contains_any(compact, LEFT_WORDS):
        return 'left'
    if _contains_any(compact, RIGHT_WORDS):
        return 'right'
    return ''


def _view_direction(compact: str) -> str:
    if _contains_any(compact, REAR_WORDS):
        return 'rear'
    if _contains_any(compact, SIDE_WORDS):
        return 'side'
    if _contains_any(compact, FRONT_WORDS):
        return 'front'
    return ''


def _camera_hint(compact: str) -> str:
    if _contains_any(compact, LOW_WORDS):
        return 'low_angle'
    if _contains_any(compact, TOP_WORDS):
        return 'top_down'
    if '特写' in compact or '近景' in compact:
        return 'closeup'
    if '全身' in compact:
        return 'full_body'
    return ''


def _surface_hint(compact: str) -> str:
    if _contains_any(compact, BOTTOM_SURFACE_WORDS):
        return 'bottom_surface'
    if _contains_any(compact, BACK_SURFACE_WORDS):
        return 'back_surface'
    if _contains_any(compact, INNER_WORDS):
        return 'inner_surface'
    if _contains_any(compact, OUTER_WORDS):
        return 'outer_surface'
    if _contains_any(compact, TOP_SURFACE_WORDS):
        return 'top_surface'
    return ''


def _vertical_zone(compact: str) -> str:
    if _contains_any(compact, UPPER_WORDS):
        return 'upper'
    if _contains_any(compact, MID_WORDS):
        return 'middle'
    if _contains_any(compact, LOWER_WORDS):
        return 'lower'
    return ''


def _action_hint(compact: str) -> str:
    hits = []
    for action, words in ACTION_HINTS.items():
        if _contains_any(compact, words):
            hits.append(action)
    return ','.join(hits)


def parse_focus_semantics(text: str = '', focus_target: str = '', focus_label: str = '') -> Dict[str, Any]:
    raw = ' '.join([x for x in [text, focus_target, focus_label] if isinstance(x, str) and x.strip()])
    compact = norm(raw)
    normalized_query = _clean_query(raw)
    matches = _all_matches(compact)
    primary = matches[0] if matches else {'canonical': '', 'keyword': '', 'score': 0}
    secondary = [m for m in matches[1:4]]
    ambiguous_tokens = {norm(x) for x in AMBIGUOUS_TARGETS}
    ambiguous = normalized_query in ambiguous_tokens or any(tok and tok in compact for tok in ambiguous_tokens) or not normalized_query
    modifiers = {
        'lateral_side': _lateral_side(compact),
        'view_direction': _view_direction(compact),
        'vertical_zone': _vertical_zone(compact),
        'surface_hint': _surface_hint(compact),
        'camera_hint': _camera_hint(compact),
        'action_hint': _action_hint(compact),
    }
    direction_flags = {
        'has_rear_hint': modifiers['view_direction'] == 'rear',
        'has_side_hint': modifiers['view_direction'] == 'side',
        'has_front_hint': modifiers['view_direction'] == 'front',
        'has_low_hint': modifiers['camera_hint'] == 'low_angle',
        'has_top_hint': modifiers['camera_hint'] == 'top_down',
    }
    if ambiguous:
        ambiguity_level = 'high'
        fallback_reason = 'ambiguous_deictic_target'
    elif not matches:
        ambiguity_level = 'medium'
        fallback_reason = 'no_known_focus_match'
    elif len(matches) > 1:
        ambiguity_level = 'low_multi_focus'
        fallback_reason = ''
    else:
        ambiguity_level = 'low'
        fallback_reason = ''
    return {
        'parsed_focus_text': raw,
        'normalized_query': normalized_query,
        'primary_focus': primary.get('canonical', ''),
        'primary_focus_keyword': primary.get('keyword', ''),
        'secondary_focuses': [{'focus': m['canonical'], 'keyword': m['keyword'], 'score': m['score']} for m in secondary],
        'multi_focus': len(matches) > 1,
        'focus_priority_reason': 'longest_specific_keyword_first' if matches else 'safe_unknown_or_ambiguous_fallback',
        'modifiers': modifiers,
        'direction_flags': direction_flags,
        'explicit_view_request': modifiers.get('view_direction') or modifiers.get('camera_hint') or '',
        'ambiguity_level': ambiguity_level,
        'fallback_reason': fallback_reason,
        'candidate_focus_matches': matches[:6],
        'focus_parse_trace': [f"normalize={normalized_query}", f"matches={[(m['canonical'], m['keyword']) for m in matches[:4]]}", f"modifiers={modifiers}"],
    }
