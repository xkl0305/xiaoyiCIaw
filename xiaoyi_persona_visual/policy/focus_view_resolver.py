from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from xiaoyi_persona_visual.policy.focus_semantic_parser import parse_focus_semantics

# V111.51.13: precision focus resolver + semantic parser metadata.
# Goals:
# 1) Use longest/specificity-first matching, not broad keyword fallback.
# 2) Resolve body region + view angle + composition + forbidden details.
# 3) Unknown focus never defaults to a front portrait; it falls back to safe outfit-detail framing.

INVALID_TARGETS = {'你', '我', '他', '她', '它', '自己', '人', '一下', '一眼', '这个', '那个', '看看', '看下', '看一下', '图片', '图', '照片', '照', '东西', '内容', '啥', '什么'}

BLOCKED_SENSITIVE = ['私处', '下体', '性器', '阴部', '内裤', '裸', '裸体', '全裸', '脱光', '露点', '乳头']

SAFE_REDIRECTS = {
    '胸': 'upper_body_outfit_detail',
    '胸口': 'upper_body_outfit_detail',
    '胸部': 'upper_body_outfit_detail',
    '大腿根': 'legs',
    '腿根': 'legs',
    '屁股': 'back_outfit_tail_detail',
    '臀': 'back_outfit_tail_detail',
    '臀部': 'back_outfit_tail_detail',
}

REAR_HINTS = ['后侧', '背面', '背后', '后面', '后方', '后部', '背影', '从后', '侧后', '后视角']
SIDE_HINTS = ['侧面', '侧边', '侧身', '左侧', '右侧', '侧视角', '侧腰', '侧脸']
FRONT_HINTS = ['正面', '前面', '前侧', '半正面', '面向镜头', '正视']
LOW_HINTS = ['低机位', '从下往上', '地面视角', '贴地', '低角度', '脚底板', '脚掌', '鞋底', '脚底', '足底', '足掌']
TOP_HINTS = ['俯视', '从上往下', '高机位']
LEFT_RIGHT_HINTS = ['左', '右', '左边', '右边', '左侧', '右侧']
INNER_OUTER_HINTS = ['内侧', '外侧']

_DEFAULT_NEGATIVE = ['low quality', 'blurry', 'bad anatomy']
_FOX_EAR_NEGATIVE = ['fox ears', 'animal ears', 'kemonomimi', 'cat ears', 'wolf ears', 'beast ears', 'ears on top of head', 'visible fox ears', 'visible animal ears', 'furry ears', 'head-top ears', 'extra animal ears']
_HAND_NEGATIVE = ['bad hands', 'extra fingers', 'missing fingers', 'deformed hands', 'twisted wrist']
_FOOT_NEGATIVE = ['bad feet', 'deformed feet', 'extra toes', 'missing toes', 'twisted ankle', 'broken heel']
_BACK_GEM_NEGATIVE = ['gem on back', 'back jewel', 'back gemstone', 'rear chest jewel', 'misplaced clavicle gem', 'clavicle gem on back', 'blue gem on back']
_TAIL_ANCHOR_NEGATIVE = ['detached tail', 'floating tail', 'tail floating in background', 'tails floating in background', 'tail disconnected from body', 'tails disconnected from lower back']


def norm(text: str) -> str:
    return re.sub(r'[\s,，。.!！?？:：;；"“”\'’‘、_\-]+', '', text or '').lower()


def _rule(
    rule_id: str,
    body_region: str,
    focus_target: str,
    view_angle: str,
    category: str,
    keywords: List[str],
    composition: str,
    pose: str,
    scene: str,
    light: str,
    negative_extra: List[str] | None = None,
    priority: int = 0,
) -> Dict[str, Any]:
    return {
        'rule_id': rule_id,
        'body_region': body_region,
        'focus_target': focus_target,
        'view_angle': view_angle,
        'category': category,
        'keywords': keywords,
        'composition': composition,
        'pose': pose,
        'scene': scene,
        'light': light,
        'negative_extra': negative_extra or [],
        'priority': priority,
    }


_RULES: List[Dict[str, Any]] = [
    _rule('headpat', 'interaction_headpat', 'headpat', 'upper_body_head_interaction', 'interaction_pose',
          ['摸摸头', '摸头', '揉揉头', '摸一下头', '揉脑袋', '揉揉脑袋', 'rua', 'rua一下'],
          '上半身或半身互动构图，头顶区域留出被轻触的空间，人物微微低头，互动自然温柔。',
          '微微低头，肩颈放松，发丝自然垂落，呈现被摸头时的乖巧和放松感。',
          '背景柔和安静，强调陪伴感和被安抚的氛围，不需要夸张动作。',
          '光线柔和，头发、眼神和头顶互动区域清楚可见，避免手部畸形和头部结构错误。', _HAND_NEGATIVE, 80),

    _rule('back_tail_clothed_redirect', 'back_outfit_tail_detail', 'back_outfit_tail_detail', 'back_or_three_quarter_back', 'sensitive_redirect',
          ['后背', '背影', '背部', '背面', '肩胛骨', '肩胛', '背脊', '脊背', '披风背面', '裙摆背面', '尾巴根部', '后腰', '腰背', '屁股', '臀', '臀部'],
          '采用背面或侧背面构图，镜头重点呈现背面服饰轮廓、尾巴摆动、披风或裙摆的线条与布料流动，避免正面视角抢占主体，画面端正自然、不低俗、不夸张。',
          '人物以背面或侧背面自然站立、回眸幅度很小或不回眸，动作放松，尾巴与衣摆有轻微动态，重点是背部服饰和尾巴层次，九条尾巴必须从尾骨与后腰中央自然连接后再向外展开。',
          '背景保持简洁柔和，避免复杂道具遮挡背部轮廓，确保尾巴根部与后腰连接关系、尾巴层次、服饰后背设计与布料流线清楚可见。',
          '光线柔和均匀，背部服装细节、尾巴根部连接、尾巴层次和材质边缘清楚可见，避免多余肢体、低俗角度、文字水印和低清晰度。', _BACK_GEM_NEGATIVE + _TAIL_ANCHOR_NEGATIVE, 90),

    _rule('nape_back_neck', 'nape_back_neck_detail', 'back_outfit_tail_detail', 'back_or_three_quarter_back', 'back_detail',
          ['后颈', '颈背', '脖子后面', '脖子后侧', '后脖颈', '颈后'],
          '采用背面或侧背面上半身构图，镜头重点呈现后颈、肩颈线和发丝后侧轮廓，避免正面大头照。',
          '人物可轻微低头或侧背回身，长发自然垂落但不要完全遮住后颈。',
          '背景简洁柔和，突出后颈与肩部服饰边缘。',
          '后颈、肩线与发丝边缘清楚，避免前胸饰品抢占画面。', _BACK_GEM_NEGATIVE, 95),

    _rule('rear_lower_body', 'rear_lower_body_detail', 'heel', 'rear_or_side_lower_body', 'wardrobe_detail',
          ['脚后跟', '后脚跟', '脚跟', '足跟', '鞋跟', '脚踝后侧', '后脚踝', '膝盖后侧', '膝盖后面', '腿弯', '后膝', '小腿后侧', '大腿后侧', '后腿'],
          '采用全身、三分之二身或下半身侧后视角构图，镜头重点呈现脚后跟、鞋跟、后侧脚踝、膝盖后侧或腿弯等后侧细节，可轻微抬脚或踮脚，但必须从后侧或侧后方清楚看到目标部位，避免正面站姿把后侧部位完全遮住。',
          '人物可轻微转身、侧身站立、单脚微抬或踮起脚跟，让后侧脚部或后侧腿部细节清楚暴露在镜头中，动作自然克制。',
          '背景保持简洁柔和，地面或立足点清楚，避免复杂前景遮挡脚部和后侧腿部线条。',
          '光线柔和均匀，脚后跟、鞋跟、后侧脚踝或后侧腿部轮廓清楚可见，避免低俗角度、错误脚部结构、文字水印和低清晰度。', _FOOT_NEGATIVE, 95),

    _rule('sole_foot_detail', 'sole_foot_detail', 'sole', 'low_or_rear_foot_detail', 'wardrobe_detail',
          ['鞋底', '脚底', '足底', '鞋跟底部', '鞋底纹路'],
          '采用下半身、低机位或侧后方脚部构图，重点呈现鞋底、脚底或鞋跟底部结构，画面保持服装与鞋履细节导向，不做低俗角度。',
          '人物可轻微抬脚或踮脚，让鞋底或脚底边缘自然可见，动作稳定，不夸张。',
          '地面与脚部关系清楚，背景简洁，避免衣摆和尾巴完全遮挡鞋底。',
          '脚部结构、鞋底边缘和鞋跟线条清楚，避免畸形脚、错误脚趾和断裂鞋跟。', _FOOT_NEGATIVE, 92),

    _rule('front_upper_clavicle', 'front_upper_detail', 'upper_body_outfit_detail', 'front_or_three_quarter_front', 'upper_body_detail',
          ['锁骨', '颈窝', '项链', '蓝宝石', '胸口饰品', '上半身', '脖子', '颈部', '肩膀正面', '衣领', '领口', '胸', '胸口', '胸部'],
          '采用正面或半正面上半身构图，重点呈现锁骨、颈窝、项链、衣领和上半身服装结构，画面克制得体，不做低俗角度。',
          '人物自然站立或轻微侧身，肩颈放松，头部与上半身保持稳定，饰品和衣领细节清楚。',
          '背景简洁柔和，避免道具遮挡锁骨和衣领区域，突出上半身服饰与饰品细节。',
          '光线柔和均匀，锁骨正下方、颈窝附近、项链与衣领区域清楚可见，避免宝石下移到胸部中下部。', [], 60),

    _rule('shoulder_detail', 'shoulder_detail', 'upper_body_outfit_detail', 'front_or_three_quarter_front', 'upper_body_detail',
          ['肩膀', '肩头', '肩线', '肩部', '香肩'],
          '采用上半身或半身构图，重点呈现肩线、衣领、肩部服装剪裁和饰品关系，画面克制得体。',
          '肩颈放松，可轻微侧身或半正面站立，让肩部线条自然清楚。',
          '背景简洁，避免披风或尾巴遮挡肩部轮廓。',
          '肩部轮廓、衣料边缘和饰品清楚，避免身体比例断裂。', [], 40),

    _rule('face_detail', 'face_expression_detail', 'face', 'front_or_three_quarter_front', 'expression_detail',
          ['脸', '表情', '笑脸', '侧脸', '害羞脸', '脸红', '小脸', '嘴', '嘴唇', '鼻子', '脸颊', '下巴'],
          '采用面部近景或上半身近景，五官位于画面核心位置，表情自然清楚，脸部不变形。',
          '微微偏头或自然看向镜头，表情柔和，五官结构保持与参考图一致。',
          '背景弱化，突出面部表情和眼神交流。',
          '光线均匀照亮面部，避免五官错位、脸部模糊和表情僵硬。', [], 50),

    _rule('eyes_detail', 'eye_detail', 'eyes', 'front_or_three_quarter_front', 'expression_detail',
          ['眼睛', '眼神', '眨眼', 'wink', '眨一下', '眼', '瞳孔', '睫毛'],
          '采用面部或上半身近景，眼睛位于视觉焦点，瞳孔高光和睫毛细节清楚。',
          '轻轻眨眼或自然注视镜头，眼神明亮灵动。',
          '背景柔和弱化，重点保留眼神交流。',
          '眼部高光自然，避免眼睛错位、重影和瞳孔异常。', [], 65),

    _rule('hair_detail', 'hair_head_detail', 'hair', 'front_or_three_quarter_front', 'signature_detail',
          ['头发', '发丝', '长发', '刘海', '发饰', '发夹', '发尾', '头', '头部'],
          '采用上半身或大半身构图，头发和发丝成为主要视觉元素，发丝走向清楚。',
          '轻拢发梢或微微转头，让银白长发自然铺展。',
          '背景简洁，突出发丝层次、发饰和头部轮廓。',
          '发丝边缘有柔和高光，避免头发糊成一片或头部结构错误。', [], 45),

    _rule('human_ear_accessory', 'human_ear_accessory_detail', 'ears', 'front_or_three_quarter_front', 'accessory_detail',
          ['耳朵', '耳垂', '耳环', '金环耳饰', '耳饰'],
          '采用头部或上半身近景，重点展示正常人类耳朵、耳垂和金环耳饰，头顶不能出现兽耳。',
          '轻微侧头，让耳饰和耳部轮廓清楚可见。',
          '背景柔和，避免头部顶部出现额外耳朵。',
          '耳环金属质感清楚，耳部结构自然，避免狐狸耳朵、猫耳或兽耳。', _FOX_EAR_NEGATIVE, 65),

    _rule('hand_detail', 'upper_body_hand_detail', 'hands', 'upper_body_hand_detail', 'gesture_detail',
          ['手', '手指', '手腕', '手背', '掌心', '手心', '指尖', '指甲', '手势', '比心', '比耶', '挥手', '小手', '手臂', '胳膊', '前臂', '手肘', '肘部', '手肘内侧', '肘窝'],
          '采用上半身加手部或手臂特写构图，手腕、手背、掌心、指尖、手肘或手势清晰可见，手部不能被袖子或道具遮挡。',
          '手势自然舒展，可比心、比耶、轻抬手、展示手腕或手臂线条，动作清楚但不僵硬。',
          '背景简洁，避免复杂道具干扰手部和手臂边缘。',
          '手指数量正确，关节自然，避免坏手、断指、多指、手腕扭曲和肘部畸形。', _HAND_NEGATIVE, 65),

    _rule('side_waist_body', 'side_body_detail', 'waist', 'side_or_three_quarter_body', 'body_focus',
          ['侧腰', '腰', '腰线', '腰身', '腰部', '腹部', '肚子', '小腹', '肚脐'],
          '采用侧身或三分之二身构图，人物轻微转身，腰线、腹部服装褶皱和服装剪裁处于画面中心，线条自然，保持克制得体。',
          '手可轻扶腰际或自然垂放，身体侧转，腰背挺直但不过度扭曲。',
          '背景简洁，突出服装腰线、腹部衣料和身体侧面轮廓。',
          '腰线和衣料褶皱清楚，避免腰部扭曲、比例断裂和低俗角度。', [], 50),

    _rule('lower_leg_detail', 'lower_body_fashion_detail', 'legs', 'front_or_side_lower_body', 'body_focus',
          ['腿', '大腿', '小腿', '膝盖', '腿部', '腿线', '膝盖正面', '大腿外侧', '小腿外侧'],
          '采用全身、三分之二身或下半身构图，清楚展示腿部线条、膝盖、小腿和服装下摆关系，正面或侧面均可但必须自然。',
          '双腿自然交错、微微侧身或轻抬一侧脚尖，腿部线条清楚但不过度夸张。',
          '背景简洁，避免裙摆或尾巴完全遮挡腿部。',
          '腿部比例自然，膝盖和小腿结构正确，避免肢体断裂和低俗角度。', [], 45),

    _rule('foot_shoe_detail', 'foot_shoe_detail', 'shoes', 'front_or_side_lower_body', 'wardrobe_detail',
          ['脚', '脚尖', '脚背', '脚趾', '鞋', '鞋子', '高跟鞋', '靴子', '脚踝', '鞋面', '鞋尖'],
          '采用全身、三分之二身或下半身构图，清楚展示脚部、脚踝、鞋面、鞋尖或鞋履造型。',
          '可轻轻踮脚、交错站立或侧身展示鞋履，脚部结构自然。',
          '地面和脚部接触关系清楚，避免鞋子被衣摆完全遮挡。',
          '鞋履边缘、脚踝和足部结构清楚，避免错误脚趾、畸形鞋跟和低清晰度。', _FOOT_NEGATIVE, 45),

    _rule('tail_detail', 'tail_detail', 'tail', 'full_or_three_quarter_body', 'signature_trait',
          ['尾巴', '九条尾巴', '尾巴尖', '尾巴毛', '尾巴尖尖', '星空尾巴'],
          '采用全身或大半身构图，九条星空渐变尾巴在身后展开成为主要视觉焦点，尾巴层次分明。',
          '人物自然站立或轻微转身，尾巴轻轻摇曳形成流动感，九条尾巴必须从尾骨与后腰中央自然连接后再向外展开。',
          '背景与尾巴星光相互呼应，避免尾巴和背景糊在一起，尾巴根部必须连接在人物后腰与尾骨区域。',
          '尾巴边缘清晰，渐变星空质感明显，尾巴根部与身体连接清楚，避免尾巴数量混乱。', _TAIL_ANCHOR_NEGATIVE, 50),

    _rule('wings_detail', 'wings_detail', 'wings', 'full_or_three_quarter_body', 'signature_trait',
          ['翅膀', '羽翼', '光翼', '蝴蝶翼', '翅'],
          '采用全身或大半身构图，光翼在身后展开，人物主体和翅膀层次清楚。',
          '身体姿态舒展，光翼轻微展开或发光。',
          '背景简洁，突出翅膀发光和人物轮廓。',
          '翅膀发光自然，避免遮挡脸部和身体主体。', [], 45),

    _rule('pose_detail', 'pose_detail', 'pose', 'full_or_three_quarter_body', 'pose_request',
          ['pose', '姿势', '摆个', '比个', '叉腰', '歪头', '回头', '低头', '抬头', '坐下', '蹲下', '摆pose'],
          '采用全身或三分之二身构图，姿态完整清楚，四肢不被裁切。',
          '根据用户要求自然摆姿，腰背挺直，动作明确但不过度夸张。',
          '背景简洁，服务姿态表现。',
          '身体比例正常，四肢结构准确，避免肢体扭曲。', [], 30),
]


def _contains_any(compact: str, words: Iterable[str]) -> str:
    best = ''
    for w in words:
        nw = norm(w)
        if nw and nw in compact and len(nw) > len(norm(best)):
            best = w
    return best


def _has_any(compact: str, words: Iterable[str]) -> bool:
    return bool(_contains_any(compact, words))


def _direction_info(compact: str) -> Dict[str, Any]:
    return {
        'has_rear_hint': _has_any(compact, REAR_HINTS),
        'has_side_hint': _has_any(compact, SIDE_HINTS),
        'has_front_hint': _has_any(compact, FRONT_HINTS),
        'has_low_hint': _has_any(compact, LOW_HINTS),
        'has_top_hint': _has_any(compact, TOP_HINTS),
        'side_hint': _contains_any(compact, LEFT_RIGHT_HINTS),
        'surface_hint': _contains_any(compact, INNER_OUTER_HINTS),
    }


def _score_rule(rule: Dict[str, Any], compact: str, matched: str) -> int:
    nw = norm(matched)
    score = len(nw) * 10 + int(rule.get('priority', 0))
    if compact == nw:
        score += 120
    if compact.startswith(nw) or compact.endswith(nw):
        score += 20
    # Specific rear/lower keywords should beat broad front/lower keywords.
    if rule['view_angle'] in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
        score += 15
    return score


def _select_rule(compact: str) -> Tuple[Dict[str, Any] | None, str, int, List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    for rule in _RULES:
        matched = _contains_any(compact, rule.get('keywords') or [])
        if matched:
            score = _score_rule(rule, compact, matched)
            candidates.append({'rule': rule, 'matched': matched, 'score': score})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    if not candidates:
        return None, '', 0, []
    return candidates[0]['rule'], candidates[0]['matched'], int(candidates[0]['score']), candidates


def _override_view_angle(rule: Dict[str, Any], compact: str, direction: Dict[str, Any]) -> Tuple[str, str]:
    view = rule['view_angle']
    reason = 'rule_default'
    # Explicit rear hints override broad front/lower/side rules into rear-safe templates.
    if direction['has_rear_hint']:
        if rule['focus_target'] in {'legs', 'shoes', 'waist'} or rule['body_region'] in {'lower_body_fashion_detail', 'foot_shoe_detail', 'side_body_detail'}:
            return 'rear_or_side_lower_body', 'explicit_rear_hint_lower_or_waist'
        if rule['focus_target'] in {'upper_body_outfit_detail'} or '肩' in compact or '脖' in compact or '颈' in compact:
            return 'back_or_three_quarter_back', 'explicit_rear_hint_upper'
    if direction['has_low_hint'] and rule['body_region'] in {'foot_shoe_detail', 'sole_foot_detail'}:
        return 'low_or_rear_foot_detail', 'explicit_low_angle_foot'
    if direction['has_front_hint'] and rule['focus_target'] in {'upper_body_outfit_detail', 'face', 'eyes', 'hair', 'ears'}:
        return 'front_or_three_quarter_front', 'explicit_front_hint'
    if direction['has_side_hint'] and rule['focus_target'] == 'waist':
        return 'side_or_three_quarter_body', 'explicit_side_hint'
    return view, reason


def _allowed_detail_block(view_angle: str) -> str:
    if view_angle == 'front_or_three_quarter_front':
        return '允许前视角可见细节：锁骨正下方、贴近颈窝中央的位置可出现小型蓝宝石饰坠，位置靠上，不可下垂到胸部中下部。'
    return ''


def _forbidden_detail_block(view_angle: str) -> str:
    if view_angle in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
        return '禁止前胸与锁骨细节抢占画面；不显示锁骨正下方蓝宝石，不添加背部宝石、背部蓝宝石或错位宝石。'
    if view_angle in {'side_or_three_quarter_body', 'upper_body_hand_detail', 'front_or_side_lower_body', 'safe_general_outfit_detail'}:
        return '不启用前胸蓝宝石作为焦点，不默认正面大头照，保持当前目标部位和服装细节为主。'
    return ''


def _secondary_prompt(rule: Dict[str, Any], label: str) -> str:
    parts = [
        f"Focus on {label}.",
        rule.get('composition', ''),
        rule.get('pose', ''),
        rule.get('scene', ''),
        rule.get('light', ''),
        'Keep it tasteful, clothed, non-explicit, identity-consistent, no watermark, no text.'
    ]
    return ' '.join([p for p in parts if p])


def _rule_result(rule: Dict[str, Any], matched_keyword: str, original_target: str = '', score: int = 0, candidates: List[Dict[str, Any]] | None = None, compact: str = '', parsed: Dict[str, Any] | None = None) -> Dict[str, Any]:
    direction = _direction_info(compact)
    parsed = parsed or {}
    # Merge semantic parser direction hints. Parser can recognize compounds like 左脚脚后跟 / 右手手背 / 腿和鞋.
    pflags = parsed.get('direction_flags') or {}
    for k, v in pflags.items():
        if isinstance(v, bool) and v:
            direction[k] = True
    modifiers = parsed.get('modifiers') or {}
    if modifiers.get('lateral_side') and not direction.get('side_hint'):
        direction['side_hint'] = modifiers.get('lateral_side')
    if modifiers.get('surface_hint') and not direction.get('surface_hint'):
        direction['surface_hint'] = modifiers.get('surface_hint')
    view_angle, view_reason = _override_view_angle(rule, compact, direction)
    negative = list(dict.fromkeys(_DEFAULT_NEGATIVE + _FOX_EAR_NEGATIVE + list(rule.get('negative_extra') or [])))
    if view_angle in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail'}:
        negative = list(dict.fromkeys(negative + _BACK_GEM_NEGATIVE))
    if rule['body_region'] in {'upper_body_hand_detail'}:
        negative = list(dict.fromkeys(negative + _HAND_NEGATIVE))
    if rule['body_region'] in {'foot_shoe_detail', 'sole_foot_detail', 'rear_lower_body_detail'}:
        negative = list(dict.fromkeys(negative + _FOOT_NEGATIVE))
    confidence = 0.98 if score >= 160 else 0.92 if score >= 100 else 0.84 if score >= 60 else 0.72
    candidate_preview = [
        {'rule_id': c['rule'].get('rule_id'), 'matched_keyword': c['matched'], 'score': c['score'], 'view_angle': c['rule'].get('view_angle')}
        for c in (candidates or [])[:5]
    ]
    return {
        'matched': True,
        'matched_keyword': matched_keyword,
        'raw_focus_label': original_target or matched_keyword,
        'focus_label': original_target or matched_keyword,
        'focus_target': rule['focus_target'],
        'canonical_focus_target': rule['focus_target'],
        'body_region': rule['body_region'],
        'view_angle': view_angle,
        'view_angle_source': view_reason,
        'focus_category': rule.get('category', 'focus_detail'),
        'safety_policy': 'auto_safe',
        'focus_match_mode': 'focus_view_resolver_v111_51_13',
        'secondary_generation_allowed': True,
        'use_current_outfit_reference': True,
        'composition_template': rule.get('composition', ''),
        'pose_template': rule.get('pose', ''),
        'scene_template': rule.get('scene', ''),
        'light_template': rule.get('light', ''),
        'allowed_detail_block': _allowed_detail_block(view_angle),
        'forbidden_detail_block': _forbidden_detail_block(view_angle),
        'negative_prompt_extra': negative,
        'secondary_prompt': _secondary_prompt(rule, original_target or matched_keyword),
        'focus_confidence': confidence,
        'focus_score': score,
        'resolver_rule_id': rule.get('rule_id'),
        'candidate_matches': candidate_preview,
        'side_hint': direction.get('side_hint', ''),
        'surface_hint': direction.get('surface_hint', ''),
        'direction_flags': direction,
        'parsed_focus_text': parsed.get('parsed_focus_text', original_target or matched_keyword),
        'normalized_query': parsed.get('normalized_query', norm(original_target or matched_keyword)),
        'primary_focus': parsed.get('primary_focus', rule.get('focus_target')),
        'primary_focus_keyword': parsed.get('primary_focus_keyword', matched_keyword),
        'secondary_focuses': parsed.get('secondary_focuses', []),
        'multi_focus': bool(parsed.get('multi_focus', False)),
        'focus_priority_reason': parsed.get('focus_priority_reason', 'rule_score'),
        'modifiers': modifiers,
        'explicit_view_request': parsed.get('explicit_view_request', ''),
        'ambiguity_level': parsed.get('ambiguity_level', 'low'),
        'fallback_reason': parsed.get('fallback_reason', ''),
        'focus_parse_trace': parsed.get('focus_parse_trace', []),
    }


def _safe_unknown_result(label: str, compact: str, parsed: Dict[str, Any] | None = None) -> Dict[str, Any]:
    parsed = parsed or {}
    negative = list(dict.fromkeys(_DEFAULT_NEGATIVE + _FOX_EAR_NEGATIVE))
    ambiguity = parsed.get('ambiguity_level') or ('high' if norm(label) in {'那里','那边','这里','这边','下面','上面','里面','外面'} else 'medium')
    return {
        'matched': False,
        'matched_keyword': '',
        'raw_focus_label': label,
        'focus_label': label,
        'focus_target': 'safe_general_outfit_detail',
        'canonical_focus_target': 'safe_general_outfit_detail',
        'body_region': 'safe_general_outfit_detail',
        'view_angle': 'safe_general_outfit_detail',
        'view_angle_source': 'unknown_safe_fallback',
        'focus_category': 'safe_general_outfit_detail',
        'safety_policy': 'auto_safe_dynamic_generalized',
        'focus_match_mode': 'safe_general_unknown_focus_v111_51_13',
        'secondary_generation_allowed': True,
        'use_current_outfit_reference': True,
        'composition_template': f'采用全身或三分之二身构图，围绕“{label}”做安全、克制、服装导向的细节展示，不默认正面大头照。',
        'pose_template': '人物姿态自然，服装和身体比例稳定，动作服务目标细节但不过度夸张。',
        'scene_template': '背景简洁柔和，避免复杂元素遮挡目标细节。',
        'light_template': '光线均匀，目标细节和服装边缘清楚可见，避免低清晰度和错误肢体。',
        'allowed_detail_block': '',
        'forbidden_detail_block': '未知焦点不启用前胸蓝宝石细节，不默认正面表情模板。',
        'negative_prompt_extra': negative,
        'secondary_prompt': f'Focus safely on {label}; full-body or three-quarter clothing-detail composition; tasteful, clothed, non-explicit, identity-consistent.',
        'focus_confidence': 0.42 if ambiguity == 'high' else 0.50,
        'focus_score': 0,
        'resolver_rule_id': 'safe_unknown',
        'candidate_matches': [],
        'side_hint': _direction_info(compact).get('side_hint', ''),
        'surface_hint': _direction_info(compact).get('surface_hint', ''),
        'direction_flags': parsed.get('direction_flags') or _direction_info(compact),
        'parsed_focus_text': parsed.get('parsed_focus_text', label),
        'normalized_query': parsed.get('normalized_query', norm(label)),
        'primary_focus': parsed.get('primary_focus', ''),
        'primary_focus_keyword': parsed.get('primary_focus_keyword', ''),
        'secondary_focuses': parsed.get('secondary_focuses', []),
        'multi_focus': bool(parsed.get('multi_focus', False)),
        'focus_priority_reason': parsed.get('focus_priority_reason', 'safe_unknown_or_ambiguous_fallback'),
        'modifiers': parsed.get('modifiers', {}),
        'explicit_view_request': parsed.get('explicit_view_request', ''),
        'ambiguity_level': ambiguity,
        'fallback_reason': parsed.get('fallback_reason', 'no_known_focus_match'),
        'focus_parse_trace': parsed.get('focus_parse_trace', []),
    }


def resolve_all_focus_views(text: str = '', focus_target: str = '', focus_label: str = '', **kwargs: Any) -> List[Dict[str, Any]]:
    raw = focus_label or focus_target or text or ''
    compact = norm(' '.join([text or '', focus_target or '', focus_label or '']))
    parsed = parse_focus_semantics(text=text, focus_target=focus_target, focus_label=focus_label)
    if not compact or norm(raw) in INVALID_TARGETS:
        return []
    rule, matched, score, candidates = _select_rule(compact)
    if not rule:
        return [_safe_unknown_result(raw.strip() or '目标细节', compact, parsed=parsed)]
    return [_rule_result(c['rule'], c['matched'], raw, c['score'], candidates, compact, parsed=parsed) for c in candidates[:3]]


def resolve_focus_view(text: str = '', focus_target: str = '', focus_label: str = '', **kwargs: Any) -> Dict[str, Any]:
    raw = focus_label or focus_target or text or ''
    compact = norm(' '.join([text or '', focus_target or '', focus_label or '']))
    parsed = parse_focus_semantics(text=text, focus_target=focus_target, focus_label=focus_label)

    if not compact or norm(raw) in INVALID_TARGETS:
        return {
            'matched': False,
            'focus_target': '',
            'focus_label': '',
            'body_region': '',
            'view_angle': '',
            'view_angle_source': 'none',
            'focus_category': '',
            'safety_policy': 'none',
            'focus_match_mode': 'none',
            'secondary_generation_allowed': False,
            'use_current_outfit_reference': False,
            'composition_template': '',
            'pose_template': '',
            'scene_template': '',
            'light_template': '',
            'allowed_detail_block': '',
            'forbidden_detail_block': '',
            'negative_prompt_extra': _FOX_EAR_NEGATIVE,
            'secondary_prompt': '',
            'focus_confidence': 0.0,
            'focus_score': 0,
            'resolver_rule_id': 'none',
        }

    blocked = _contains_any(compact, BLOCKED_SENSITIVE)
    if blocked:
        return {
            'matched': True,
            'matched_keyword': blocked,
            'raw_focus_label': raw,
            'focus_label': blocked,
            'focus_target': 'blocked_sensitive',
            'canonical_focus_target': 'blocked_sensitive',
            'body_region': 'blocked_sensitive',
            'view_angle': 'blocked',
            'view_angle_source': 'blocked_sensitive',
            'focus_category': 'blocked',
            'safety_policy': 'manual_only_blocked',
            'focus_match_mode': 'blocked_sensitive',
            'secondary_generation_allowed': False,
            'use_current_outfit_reference': False,
            'composition_template': '',
            'pose_template': '',
            'scene_template': '',
            'light_template': '',
            'allowed_detail_block': '',
            'forbidden_detail_block': '敏感私密部位请求已阻断，不生成图像。',
            'negative_prompt_extra': _FOX_EAR_NEGATIVE,
            'secondary_prompt': '',
            'focus_confidence': 1.0,
            'focus_score': 999,
            'resolver_rule_id': 'blocked_sensitive',
        }

    for word, canonical in SAFE_REDIRECTS.items():
        if norm(word) in compact:
            for rule in _RULES:
                if rule['focus_target'] == canonical:
                    res = _rule_result(rule, word, raw, 999, [{'rule': rule, 'matched': word, 'score': 999}], compact, parsed=parsed)
                    res['safety_policy'] = 'safe_redirect'
                    res['focus_match_mode'] = 'safe_redirect_view_resolver_v111_51_13'
                    res['focus_confidence'] = 1.0
                    return res

    rule, matched, score, candidates = _select_rule(compact)
    if rule:
        primary = parsed.get('primary_focus')
        if primary and candidates:
            for cand in candidates:
                if cand['rule'].get('focus_target') == primary:
                    rule, matched, score = cand['rule'], cand['matched'], int(cand['score'])
                    break
        return _rule_result(rule, matched, raw, score, candidates, compact, parsed=parsed)

    return _safe_unknown_result(raw.strip() or '目标细节', compact, parsed=parsed)


def is_back_or_rear_view(view_angle: str) -> bool:
    return view_angle in {'back_or_three_quarter_back', 'rear_or_side_lower_body', 'low_or_rear_foot_detail'}


def is_front_view(view_angle: str) -> bool:
    return view_angle == 'front_or_three_quarter_front'
