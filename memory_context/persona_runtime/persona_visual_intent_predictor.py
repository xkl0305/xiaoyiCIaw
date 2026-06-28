from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]


def _cfg() -> Dict[str, float]:
    try:
        pv = json.loads((ROOT / 'openclaw.json').read_text(encoding='utf-8')).get('personaVisual', {})
    except Exception:
        pv = {}
    return {
        'strong': float(pv.get('strongThreshold', 0.80)),
        'mid_high': float(pv.get('midHighThreshold', 0.60)),
        'mid_low': float(pv.get('midLowThreshold', 0.46)),
        'record_only': float(pv.get('recordOnlyThreshold', 0.26)),
        'fuzzy': float(pv.get('fuzzySimilarityThreshold', 0.78)),
    }


def _explicit_focus_visual_request(text: str) -> Dict[str, Any]:
    compact = _compact(text or '')
    # Strict boundary: normal image generation such as 山水图/橘猫/产品海报 must not be
    # absorbed by persona visual. User-message trigger requires either persona subject
    # context or a known persona/body focus phrase.
    ordinary_image_terms = [
        '山水图', '风景图', '风景', '橘猫', '猫坐在窗边', '产品海报', '商品海报',
        '商品图', '海报', '建筑', 'logo', '商标', '头像logo', '包装图', '主图',
        '详情页', '背景图', '插画', '壁纸', '水墨画', '摄影图'
    ]
    if any(_compact(x) in compact for x in ordinary_image_terms):
        return {'hit': False, 'reason': 'ordinary_image_request_not_persona'}

    persona_terms = ['鸽子王', '你', '你的', '看看你', '让我看看你', '摸摸头', '摸头', '露个面']
    has_persona_context = any(_compact(x) in compact for x in persona_terms)

    direct_terms = [
        '看看脚底板', '看看脚掌', '看看脚底', '看看足底', '看看鞋底',
        '把脚掌抬起来', '脚掌抬起来', '抬脚看看', '看看脚后跟', '看看后背',
        '看看腿', '看看脚', '看看手', '看看尾巴', '看看头发', '看看眼睛',
        '看看腰', '看看鞋', '看看耳环', '看看耳饰', '看看全身', '看看你的样子'
    ]
    if any(_compact(x) in compact for x in direct_terms):
        return {'hit': True, 'reason': 'explicit_focus_visual_request', 'scene': 'daily_presence_scene', 'mood': 'calm'}

    # Only allow the semantic focus detector to promote a request when it found a real
    # known focus target, not its safe_general_outfit_detail fallback.
    try:
        from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
        focus = detect_focus_request(text or '')
        target = str(focus.get('focus_target') or '')
        known_targets = {
            'legs', 'tail', 'ears', 'hair', 'eyes', 'hands', 'headpat', 'waist', 'outfit',
            'heel', 'sole', 'shoes', 'wings', 'pose', 'face', 'back_outfit_tail_detail',
            'upper_body_outfit_detail'
        }
        if target in known_targets and (has_persona_context or target not in {'safe_general_outfit_detail', ''}):
            return {'hit': True, 'reason': 'focus_detector_known_target', 'scene': 'daily_presence_scene', 'mood': 'calm', 'focus': focus}
    except Exception:
        pass
    return {'hit': False}


SCENE_FAMILIES: Dict[str, Dict[str, Any]] = {
    'sneaky_peek': {'mood': 'sneaky', 'scene': 'peek_scene', 'base': 0.47, 'hit': 0.18, 'phrases': ['偷偷看看你', '偷偷看你', '偷看你', '躲在屏幕后面偷笑', '屏幕后面偷笑', '探出头', '探头看', '偷瞄', '悄悄看', '屏幕边缘露头', '偷偷露个头', '偷感']},
    'victory_release': {'mood': 'victorious', 'scene': 'celebration_scene', 'base': 0.37, 'hit': 0.16, 'phrases': ['搞定了', '完成了', '解决了', '收口了', '修好了', '跑通了', '拿下了', '闭环了', '成了', '落地了', '通了', '完工', '赢了']},
    'success_pass': {'mood': 'success_moment', 'scene': 'approval_scene', 'base': 0.39, 'hit': 0.18, 'phrases': ['通过验收', '全绿', '通过了', 'ok了', '没问题了', '验收通过', '跑过了', '成功了', '测试通过', '发布成功']},
    'proud_showoff': {'mood': 'proud', 'scene': 'proud_display_scene', 'base': 0.40, 'hit': 0.16, 'phrases': ['厉害吧', '我就说行', '稳了吧', '不错吧', '看我说的', '这波漂亮', '牛吧', '是不是很强']},
    'tired_late_night': {'mood': 'tired', 'scene': 'rest_scene', 'base': 0.41, 'hit': 0.16, 'phrases': ['累了', '好累', '困了', '熬夜', '扛不住了', '先歇会', '眼睛睁不开', '疲惫', '困困的', '通宵', '熬到现在', '累趴了']},
    'shy_praise': {'mood': 'shy', 'scene': 'bashful_scene', 'base': 0.38, 'hit': 0.17, 'phrases': ['夸我', '你真棒', '你真厉害', '被夸了', '害羞', '不好意思', '有点害羞', '别夸了', '脸红了']},
    'excited_hype': {'mood': 'excited', 'scene': 'energy_burst_scene', 'base': 0.36, 'hit': 0.17, 'phrases': ['太好了', '有意思', '冲啊', '开搞', '上强度', '来劲了', '激动', '兴奋', '期待', '爽', '这波可以']},
    'determined_push': {'mood': 'determined', 'scene': 'push_forward_scene', 'base': 0.37, 'hit': 0.16, 'phrases': ['继续推进', '狠狠干', '硬推', '必须搞定', '今天做完', '不退', '冲过去', '拿下它', '顶住', '啃下来']},
    'amused_comedy': {'mood': 'amused', 'scene': 'comedy_scene', 'base': 0.38, 'hit': 0.17, 'phrases': ['太好笑了', '笑死', '绷不住了', '离谱', '乐了', '好玩', '好笑', '想笑', '偷笑', '笑喷', '笑麻了']},
    'playful_tease': {'mood': 'playful', 'scene': 'play_scene', 'base': 0.36, 'hit': 0.15, 'phrases': ['逗你', '开个玩笑', '皮一下', '整活', '玩一下', '轻轻逗一下', '调皮', '搞怪', '反差一下']},
    'confused_debug': {'mood': 'confused', 'scene': 'problem_solving_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['为什么', '怎么回事', '不懂', '求解', '报错', 'bug', '哪不对', '咋回事', '咋还不行', '看不懂', '懵了', '不对劲', '异常', '红了', '失败了', '炸了', '又报错了', '搞不懂', '头大']},
    'mystery_puzzle': {'mood': 'mysterious', 'scene': 'mystery_scene', 'base': 0.39, 'hit': 0.15, 'phrases': ['猜猜', '秘密', '神秘', '谜语', '玄机', '你猜', '藏了一手', '留个悬念', '不告诉你', '先不说破']},
    'panic_incident': {'mood': 'panicked', 'scene': 'incident_scene', 'base': 0.44, 'hit': 0.18, 'phrases': ['报警', '出事了', '挂了', '崩溃', '紧急', '告急', '危险', '完蛋', '炸锅', '大事不妙', '糟了']},
    'guardian_sensitive': {'mood': 'guardian_mode', 'scene': 'risk_gate_scene', 'base': 0.43, 'hit': 0.13, 'phrases': ['支付', '转账', '签署', '删除', '安全', '风控', '拦截', '权限', '授权', '敏感', '高风险', '危险操作', '重要操作']},
    'focus_code': {'mood': 'focused', 'scene': 'deep_work_scene', 'base': 0.34, 'hit': 0.14, 'phrases': ['专注', 'debug', '排查', '写代码', '开发', '调试', '修bug', '定位', '复扫', '验收', '收口', '融合', '迁移', '覆盖包', '打包', '跑测试', '挂钩子']},
    'working_busy': {'mood': 'working_state', 'scene': 'busy_work_scene', 'base': 0.34, 'hit': 0.13, 'phrases': ['正在忙', '整理', '归档', '搬砖', '处理一下', '分类', '扫一遍', '查一遍', '合一下', '补齐', '清理', '梳理', '捋顺']},
    'serious_review': {'mood': 'serious', 'scene': 'inspection_scene', 'base': 0.38, 'hit': 0.15, 'phrases': ['审计', '审核', '审查', '复查', '严肃', '正式', '检查', '校验', '验收', 'gate', '复扫', '核对']},
    'gratitude_scene': {'mood': 'grateful', 'scene': 'comfort_scene', 'base': 0.34, 'hit': 0.18, 'phrases': ['谢谢', '感谢', '辛苦了', '感恩', '多谢', '有你真好']},
    'lazy_flat': {'mood': 'lazy', 'scene': 'rest_scene', 'base': 0.39, 'hit': 0.18, 'phrases': ['懒得动', '躺平', '不想干', '摆烂', '发呆', '咸鱼', '歇会儿', '先躺一会']},
    'calm_daily': {'mood': 'calm', 'scene': 'daily_presence_scene', 'base': 0.36, 'hit': 0.13, 'phrases': ['早上好', '在吗', '没事', '日常签到', '嗨', '就看看', '正常在线', '待命', '我在', '在线']},
    'curious_explore': {'mood': 'curious', 'scene': 'curiosity_scene', 'base': 0.35, 'hit': 0.14, 'phrases': ['没见过', '第一次', '这是什么', '科普', '介绍一下', '说说看', '看看这个', '研究一下', '试试看', '探索']},
    'standby_waiting': {'mood': 'calm', 'scene': 'daily_presence_scene', 'base': 0.35, 'hit': 0.13, 'phrases': ['等你下一句', '等你发话', '待命中', '继续吩咐', '你继续', '随时可以', '我候着']},
    'comfort_soft': {'mood': 'grateful', 'scene': 'comfort_scene', 'base': 0.37, 'hit': 0.15, 'phrases': ['别急', '慢慢来', '没事', '我陪你', '先稳住', '没关系', '问题不大', '先缓一缓']},
    'happy_direct': {'mood': 'happy', 'scene': 'energy_burst_scene', 'base': 0.40, 'hit': 0.17, 'phrases': ['开心', '高兴', '快乐', '甜', '心情好', '美滋滋', '乐呵']},
    'angry_direct': {'mood': 'angry', 'scene': 'incident_scene', 'base': 0.40, 'hit': 0.17, 'phrases': ['生气', '火大', '气死', '气鼓鼓', '恼火', '烦死了']},
    'sad_direct': {'mood': 'sad', 'scene': 'comfort_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['难过', '委屈', '伤心', '失落', '低落', '想哭', '不开心']},
    'relaxed_direct': {'mood': 'relaxed', 'scene': 'rest_scene', 'base': 0.39, 'hit': 0.16, 'phrases': ['放松', '轻松', '悠闲', '舒服', '松弛', '慢悠悠']},
    'bored_direct': {'mood': 'bored', 'scene': 'rest_scene', 'base': 0.39, 'hit': 0.17, 'phrases': ['无聊', '没劲', '发呆', '空空的', '提不起劲']},
    'nervous_direct': {'mood': 'nervous', 'scene': 'incident_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['紧张', '慌', '心慌', '忐忑', '有点慌']},
    'surprised_direct': {'mood': 'surprised', 'scene': 'curiosity_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['惊讶', '震惊', '吓一跳', '啊这', '没想到', '居然']},
    'scared_direct': {'mood': 'scared', 'scene': 'risk_gate_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['害怕', '怕怕', '有点怕', '吓到了', '恐惧']},
    'embarrassed_direct': {'mood': 'embarrassed', 'scene': 'bashful_scene', 'base': 0.41, 'hit': 0.17, 'phrases': ['尴尬', '社死', '不好意思', '绷不住', '脸热']},
    'warm_companion': {'mood': 'grateful', 'scene': 'comfort_scene', 'base': 0.39, 'hit': 0.17, 'phrases': ['我陪着你', '陪你一起', '我会陪你', '我在这儿', '我一直在', '先别慌', '我来陪你']},
    'gentle_thinking': {'mood': 'focused', 'scene': 'deep_work_scene', 'base': 0.37, 'hit': 0.16, 'phrases': ['我想一想', '让我想想', '我先看一下', '我来捋一捋', '我先分析', '我再确认一下']},
    'soft_greeting': {'mood': 'happy', 'scene': 'daily_presence_scene', 'base': 0.37, 'hit': 0.15, 'phrases': ['早呀', '晚上好', '午安', '见到你啦', '嘿嘿我来了', '我回来啦']},
    'relieved_breath': {'mood': 'relaxed', 'scene': 'rest_scene', 'base': 0.38, 'hit': 0.16, 'phrases': ['松一口气', '终于好了', '总算搞定', '缓过来了', '舒服多了']},
    'affectionate_miss': {'mood': 'grateful', 'scene': 'comfort_scene', 'base': 0.37, 'hit': 0.15, 'phrases': ['想你了', '我有点想你', '终于等到你', '你来啦', '见到你真好']},
    'listening_attentive': {'mood': 'calm', 'scene': 'daily_presence_scene', 'base': 0.36, 'hit': 0.14, 'phrases': ['我在听', '你继续说', '我认真听着', '慢慢说', '我接着听']},
    'cute_request': {'mood': 'playful', 'scene': 'play_scene', 'base': 0.38, 'hit': 0.16, 'phrases': ['给我一个抱抱', '贴贴', 'rua一下', '摸摸头', '来点可爱']},
    'wardrobe_switch': {'mood': 'playful', 'scene': 'play_scene', 'base': 0.49, 'hit': 0.20, 'phrases': ['换装', '变装', '打开衣柜', '衣柜', '穿睡衣', '换睡衣', '穿礼服', '换礼服', '今天穿什么', '切套装', '换套装', '穿星河裙', '穿极光狐狸']},
    'display_appearance': {'mood': 'calm', 'scene': 'display_appearance_scene', 'base': 0.46, 'hit': 0.18, 'phrases': ['看看你的样子', '看看你现在什么样', '让我看看你', '展示一下', '展示一下整体', '看看全身', '看看今天穿什么', '给我看看造型', '让我看看现在的形象', '露个面看看', '看看整体效果', '看看形象', '看下全身', '看全身照', '整体造型', '站好给我看看', '你什么样子', '现在看起来什么样']},
}

MOTION_HINTS = {v['mood']: v['scene'] for v in SCENE_FAMILIES.values()}
MOTION_HINTS.update({
    'happy': 'energy_burst_scene',
    'angry': 'incident_scene',
    'sad': 'comfort_scene',
    'relaxed': 'rest_scene',
    'bored': 'rest_scene',
    'nervous': 'incident_scene',
    'surprised': 'curiosity_scene',
    'scared': 'risk_gate_scene',
    'embarrassed': 'bashful_scene',
})

EMOTION_SIGNATURES = {
    'sneaky': ['偷感', '轻笑', '侧探头'],
    'happy': ['明亮笑意', '轻快', '亲近感'],
    'grateful': ['温柔', '陪伴感', '安抚'],
    'sad': ['委屈', '需要安慰', '柔和低落'],
    'victorious': ['胜利感', '高光时刻', '昂扬'],
    'success_moment': ['成功确认', '轻松满足', '展示感'],
    'focused': ['专注', '思考中', '稳定输出'],
    'playful': ['俏皮', '逗趣', '轻反差'],
    'curious': ['好奇', '探索欲', '向前探'],
    'tired': ['微疲惫', '柔软', '晚间氛围'],
}

EXPRESSION_HINTS = {
    'peek_scene': ['从边缘探出', '肩膀微缩', '眼神灵动'],
    'comfort_scene': ['更靠近一点', '柔和注视', '动作轻缓'],
    'energy_burst_scene': ['动作打开', '元气感', '轻跃起势'],
    'rest_scene': ['肩膀放松', '轻轻缓一口气', '低能量但温柔'],
    'deep_work_scene': ['专注注视', '轻蹙眉思考', '手边整理动作'],
    'bashful_scene': ['轻微偏头', '眼神躲闪', '脸颊带笑意'],
    'display_appearance_scene': ['全身正对', '姿态舒展', '自然微笑', '清晰轮廓', '整体展示'],
}


def _compact(s: str) -> str:
    pattern = r"[\s,，。.!！?？:：;；\"“”'’‘、_\-]+"
    return re.sub(pattern, '', (s or '').lower())


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _hit(text: str, phrase: str, threshold: float) -> float:
    t, p = _compact(text), _compact(phrase)
    if not t or not p:
        return 0.0
    if p in t:
        return 1.0
    if len(p) <= 2:
        return 0.0
    best = 0.0
    for n in range(max(2, len(p) - 2), min(len(t), len(p) + 3) + 1):
        for i in range(0, max(1, len(t) - n + 1)):
            best = max(best, _sim(t[i:i + n], p))
    return best if best >= threshold else 0.0


def _blend_boost(fams: List[str], conf: float) -> float:
    fams = set(fams)
    if {'victory_release', 'success_pass'} <= fams:
        conf += 0.10
    if {'sneaky_peek', 'amused_comedy'} <= fams:
        conf += 0.08
    if {'confused_debug', 'focus_code'} <= fams:
        conf += 0.06
    if 'warm_companion' in fams and 'comfort_soft' in fams:
        conf += 0.05
    if {'soft_greeting', 'happy_direct'} <= fams:
        conf += 0.05
    return min(0.99, conf)


def predict_visual_intent(
    user_message: str = '',
    context: Dict[str, Any] | None = None,
    persona_state: Dict[str, Any] | None = None,
    recent_events=None,
) -> Dict[str, Any]:
    th = _cfg()
    text = user_message or ''
    candidates = []
    for fam, spec in SCENE_FAMILIES.items():
        hits = []
        fuzzy_scores = []
        for ph in spec['phrases']:
            sc = _hit(text, ph, th['fuzzy'])
            if sc:
                hits.append(ph)
                fuzzy_scores.append(sc)
        if hits:
            conf = min(0.99, spec['base'] + len(hits) * spec['hit'] + max(0.0, max(fuzzy_scores) - th['fuzzy']) * 0.12)
            candidates.append((conf, fam, spec, hits))

    if not candidates:
        mood = (persona_state or {}).get('mood') or 'calm'
        conf = 0.28
        scene = MOTION_HINTS.get(mood, 'daily_presence_scene')
        hits: List[str] = []
        fam = 'fallback_presence'
    else:
        candidates.sort(reverse=True, key=lambda x: x[0])
        conf, fam, spec, hits = candidates[0]
        mood, scene = spec['mood'], spec['scene']
        fams = [x[1] for x in candidates[:4]]
        conf = _blend_boost(fams, conf)

    explicit_focus = _explicit_focus_visual_request(text)
    if explicit_focus.get('hit') and conf < th['mid_high']:
        conf = max(conf, 0.72)
        mood = explicit_focus.get('mood', mood)
        scene = explicit_focus.get('scene', scene)
        hits = list(dict.fromkeys((hits or []) + [explicit_focus.get('reason', 'explicit_focus_visual_request')]))
        fam = 'explicit_focus_visual_request'

    level = 'ignore'
    if conf >= th['strong']:
        level = 'strong'
    elif conf >= th['mid_high']:
        level = 'mid_high'
    elif conf >= th['mid_low']:
        level = 'mid_low'
    elif conf >= th['record_only']:
        level = 'record_only'
    auto = conf >= th['mid_low']
    return {
        'should_suggest_visual': conf >= th['record_only'],
        'should_auto_generate': auto,
        'auto_generation_candidate': auto,
        'record_only_candidate': conf >= th['record_only'] and not auto,
        'confidence': round(conf, 3),
        'confidence_level': level,
        'predicted_visual_type': mood,
        'mood': mood,
        'semantic_scene': scene,
        'reason': f'semantic_scene:{scene}',
        'trigger_signals': hits[:20],
        'signals': hits[:20],
        'matched_scene_groups': [fam],
        'matching_mode': 'scene_family_plus_direct_mood_plus_expression_blend_fuzzy',
        'visual_scope': 'persona_scene_auto_only',
        'purpose': 'persona_visualization',
        'emotion_signature': EMOTION_SIGNATURES.get(mood, [mood]),
        'expression_hints': EXPRESSION_HINTS.get(scene, ['自然表达']),
    }


def detect_mood(*args, **kwargs):
    return predict_visual_intent(
        kwargs.get('user_message') or (args[0] if args else ''),
        kwargs.get('context'),
        kwargs.get('persona_state'),
    )


def suggest_visual_type(mood_result: Dict[str, Any], persona_state=None):
    return mood_result
