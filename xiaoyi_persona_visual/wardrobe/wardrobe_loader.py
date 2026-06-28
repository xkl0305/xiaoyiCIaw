from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

MODULE_ROOT = Path(__file__).resolve().parents[1]
WARDROBE_MANIFEST = MODULE_ROOT / 'wardrobe/wardrobe_manifest.json'
SCENE_OUTFIT_MAP = MODULE_ROOT / 'wardrobe/scene_outfit_map.json'
FOCUS_OUTFIT_MAP = MODULE_ROOT / 'wardrobe/focus_outfit_map.json'

# ── V111.49.1 synced: continuity and forbidden phrases ──
LAST_OUTFIT_CONTINUITY_PHRASES = [
    '还是刚才那身', '继续刚才', '不换', '保持上一套',
    '就用刚才那个', '还穿刚才那套', '别换衣服', '保持现在这身',
    '不变', '就穿这身', '不换衣服',
]
FORBID_LAST_OUTFIT_PHRASES = [
    '看看你的样子', '看看你现在什么样', '让我看看你', '展示一下',
    '看看全身', '看看腿', '看看造型', '给我看看整体效果', '露个面看看',
    '看看尾巴', '看看耳朵', '看看头发', '看看眼睛',
    '看看手', '看看腰', '看看鞋',
]

# ── V111.49.1 synced: bashful_scene forbidden fallback phrases ──
DISPLAY_APPEARANCE_PHRASES = [
    '看看你的样子', '让我看看你', '展示一下', '看看全身',
    '露个面看看', '看看现在什么样', '看看形象', '看下全身',
    '看全身照', '整体造型', '站好给我看看', '你什么样子',
    '现在看起来什么样', '看看今天穿什么', '给我看看造型',
    '让我看看现在的形象', '看看整体效果',
]


def _load_json(fp: Path) -> Dict[str, Any]:
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding='utf-8'))
        except:
            pass
    return {}


def load_wardrobe_manifest() -> Dict[str, Any]:
    return _load_json(WARDROBE_MANIFEST)


def load_scene_outfit_map() -> Dict[str, str]:
    data = _load_json(SCENE_OUTFIT_MAP)
    return data.get('scene_outfit_map', {})


def load_focus_outfit_map() -> Dict[str, List[str]]:
    data = _load_json(FOCUS_OUTFIT_MAP)
    return data.get('focus_outfit_map', {})


# ── V111.49.1: continuity detection ──
def is_last_outfit_continuity(text: str) -> bool:
    """Return True only for explicit continuity expressions."""
    if not text:
        return False
    t = text.strip().lower()
    for phrase in LAST_OUTFIT_CONTINUITY_PHRASES:
        if phrase.lower() in t:
            return True
    return False


def is_forbidden_last_outfit(text: str) -> bool:
    """Check if input must NOT use runtime_current/last_outfit."""
    if not text:
        return False
    t = text.strip().lower()
    for phrase in FORBID_LAST_OUTFIT_PHRASES:
        if phrase.lower() in t:
            return True
    return False


# ── V111.49.1: bashful_scene guard ──
def is_display_appearance_request(text: str) -> bool:
    """Check if text is a display-appearance request that must NOT fallback to bashful_scene."""
    if not text:
        return False
    t = text.strip().lower()
    for phrase in DISPLAY_APPEARANCE_PHRASES:
        if phrase.lower() in t:
            return True
    return False


# ── Runtime state helpers ──
def _runtime_state_path() -> Path:
    return MODULE_ROOT.parent / '.persona_visual/runtime_wardrobe_state.json'


def load_runtime_state() -> Dict[str, Any]:
    return _load_json(_runtime_state_path())


def current_outfit() -> str:
    st = load_runtime_state()
    return str(st.get('current_outfit', ''))


def save_current_outfit(outfit_id: str) -> Dict[str, Any]:
    fp = _runtime_state_path()
    fp.parent.mkdir(parents=True, exist_ok=True)
    st = load_runtime_state()
    st.update({'current_outfit': outfit_id, 'source': 'runtime_state', 'version': 'V111.51'})
    try:
        fp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'status': 'ok', 'current_outfit': outfit_id}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


def detect_explicit_outfit(text: str, outfit_config: Dict[str, Any] = None) -> str:
    """Detect explicitly mentioned outfit from text."""
    t = (text or '').lower()
    if outfit_config is None:
        outfit_config = load_wardrobe_manifest()
    outfit_data = outfit_config.get('outfits', {})
    explicit_keywords = [
        ('moonfeather_robe', ['月羽云裳', '月羽', '云裳', '薄纱裙', '月白冰蓝']),
        ('stardust_dream', ['星尘织梦', '织梦', '亮片蕾丝', '挂脖连体衣']),
        ('galaxy_gown', ['银河缠纱礼服', '银河缠纱', '星河', '银河', '星空裙']),
        ('aurora_fox_set', ['极光狐毛套装', '极光', '狐狸', '狐系']),
        ('mermaid_gauze_set', ['人鱼纱幔套装', '人鱼', '纱裙', '海洋']),
        ('stardust_set', ['星尘银闪套装', '星尘', '害羞套装']),
        ('pajamas', ['睡衣', '晚安', '睡觉', '休息']),
        ('gown', ['深v幻彩纱裙', '礼服', '长裙', '正式']),
    ]
    for key, words in explicit_keywords:
        if any(str(w).lower() in t for w in words):
            return key
    return ''


def choose_outfit_by_focus(focus_target: str, focus_outfit_map: Dict[str, List[str]] = None,
                           outfit_config: Dict[str, Any] = None) -> str:
    """Choose outfit based on focus target using focus_outfit_map."""
    if focus_outfit_map is None:
        focus_outfit_map = load_focus_outfit_map()
    if not focus_target:
        return ''
    clean_target = focus_target.replace('dynamic:', '') if focus_target.startswith('dynamic:') else focus_target
    candidates = focus_outfit_map.get(clean_target, focus_outfit_map.get(focus_target, []))
    if not candidates:
        return ''
    return candidates[0]


# ── V111.49.2: bashful_scene guard — if text is a display-appearance request,
# FORCE semantic_scene to display_appearance_scene even if caller passed wrong scene.
_DISPLAY_APPEARANCE_PHRASES = [
    '看看你的样子', '让我看看你', '展示一下', '看看全身',
    '露个面看看', '看看现在什么样', '看看形象', '看下全身',
    '看全身照', '整体造型', '站好给我看看', '你什么样子',
    '现在看起来什么样', '看看今天穿什么', '给我看看造型',
    '让我看看现在的形象', '看看整体效果',
]


def _is_display_appearance_text(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    for phrase in _DISPLAY_APPEARANCE_PHRASES:
        if phrase.lower() in t:
            return True
    return False


def choose_outfit(
    text: str = '',
    mood: str = '',
    semantic_scene: str = '',
    requested_outfit: str = '',
    focus_target: str = '',
    auto_mode: bool = True,
    scene_confidence: float = 0.0,
) -> Dict[str, Any]:
    """V111.49.2: Final protection against bashful_scene takeover."""
    # ── V111.49.2: Force display_appearance_scene if text matches ──
    if _is_display_appearance_text(text):
        semantic_scene = 'display_appearance_scene'
        # Don't let bashful_scene intercept
        if mood == 'shy':
            mood = 'calm'
    """V111.49.1 synced: Correct priority chain for outfit selection.

    Priority (highest → lowest):
      1. requested_outfit
      2. explicit_choice
      3. last_outfit_continuity (only if is_last_outfit_continuity(text) == True)
      4. focus_recommend
      5. scene_recommend
      6. mood_recommend
      7. safe_default_outfit
    """
    manifest = load_wardrobe_manifest()
    scene_map = load_scene_outfit_map()
    focus_map = load_focus_outfit_map()

    scene_choice = scene_map.get(semantic_scene)
    mood_choice = load_mood_outfit_map_static().get(mood) if mood else ''
    explicit_choice = detect_explicit_outfit(text)
    continuity = is_last_outfit_continuity(text)
    forbid_last = is_forbidden_last_outfit(text)
    current_choice = current_outfit()

    # ── Debug structure ──
    debug = {
        '_raw_input': {
            'text': text,
            'mood': mood,
            'semantic_scene': semantic_scene,
            'focus_target': focus_target,
        },
        '_detections': {
            'explicit_choice_found': bool(explicit_choice),
            'explicit_choice_id': explicit_choice or '',
            'is_last_outfit_continuity': continuity,
            'is_forbidden_from_last_outfit': forbid_last,
            'runtime_current_outfit': current_choice or '(none)',
        },
    }

    # Priority 1: requested_outfit
    if requested_outfit:
        info = _build_outfit_info(requested_outfit, manifest)
        info['choice_source'] = 'requested_outfit'
        info['_debug'] = {**debug, '_pipeline': 'requested_outfit → direct'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence or 0.0
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = continuity
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = False
        info['outfit_source'] = 'requested'
        info['outfit_selection_reason'] = '用户明确指定服装'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 2: explicit_choice
    if explicit_choice:
        info = _build_outfit_info(explicit_choice, manifest)
        info['choice_source'] = 'explicit_text'
        info['_debug'] = {**debug, '_pipeline': 'explicit_text → direct'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = continuity
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = False
        info['outfit_source'] = 'explicit_text'
        info['outfit_selection_reason'] = '文本中包含明确服装关键词'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 3: last_outfit_continuity (only explicit continuity phrases)
    if continuity and not forbid_last and current_choice:
        info = _build_outfit_info(current_choice, manifest)
        info['choice_source'] = 'last_outfit_continuity'
        info['_debug'] = {**debug, '_pipeline': 'last_outfit_continuity → runtime_current'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = True
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = True
        info['outfit_source'] = 'last_outfit'
        info['outfit_selection_reason'] = '用户明确要求保持上一套衣服'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 4: focus_recommend
    focus_choice = choose_outfit_by_focus(focus_target, focus_map)
    if focus_choice:
        info = _build_outfit_info(focus_choice, manifest)
        info['choice_source'] = 'focus_recommend'
        info['_debug'] = {**debug, '_pipeline': f'focus_recommend → {focus_target} → {focus_choice}'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = False
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = False
        info['outfit_source'] = 'focus_outfit_map'
        info['outfit_selection_reason'] = f'焦点目标={focus_target}，从焦点衣柜映射选择'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 5: scene_recommend
    if scene_choice:
        info = _build_outfit_info(scene_choice, manifest)
        info['choice_source'] = 'scene_recommend'
        info['_debug'] = {**debug, '_pipeline': f'scene_recommend → {semantic_scene} → {scene_choice}'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = False
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = False
        info['outfit_source'] = 'scene_outfit_map'
        info['outfit_selection_reason'] = f'场景={semantic_scene}，从场景衣柜映射选择，适合整体展示'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 6: mood_recommend (implemented via profiles)
    if mood_choice:
        info = _build_outfit_info(mood_choice, manifest)
        info['choice_source'] = 'mood_recommend'
        info['_debug'] = {**debug, '_pipeline': f'mood_recommend → {mood} → {mood_choice}'}
        info['scene_type'] = semantic_scene
        info['scene_confidence'] = scene_confidence
        info['focus_target'] = focus_target
        info['last_outfit_continuity'] = False
        info['runtime_current_outfit'] = current_choice
        info['runtime_current_used'] = False
        info['outfit_source'] = 'mood_outfit_map'
        info['outfit_selection_reason'] = f'心情={mood}，从心情衣柜映射选择'
        info['fallback_used'] = False
        info['fallback_reason'] = ''
        return info

    # Priority 7: safe_default_outfit
    default = manifest.get('default_outfit', 'moonfeather_robe')
    info = _build_outfit_info(default, manifest)
    info['choice_source'] = 'default'
    info['_debug'] = {**debug, '_pipeline': f'safe_default → {default}'}
    info['scene_type'] = semantic_scene
    info['scene_confidence'] = scene_confidence
    info['focus_target'] = focus_target
    info['last_outfit_continuity'] = False
    info['runtime_current_outfit'] = current_choice
    info['runtime_current_used'] = False
    info['outfit_source'] = 'default'
    info['outfit_selection_reason'] = '无任何匹配，使用安全默认服装'
    info['fallback_used'] = True
    info['fallback_reason'] = 'no matching rule in priority chain'
    return info


def _build_outfit_info(chosen: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Build outfit info dict for a given chosen outfit id."""
    outfits = manifest.get('outfits', {})
    u = outfits.get(chosen, {}) if isinstance(outfits.get(chosen, {}), dict) else {}
    info = {
        'outfit_id': chosen,
        'name': u.get('name') or chosen,
        'prompt_suffix': u.get('prompt_suffix') or 'identity unchanged',
        'manual_only': bool(u.get('manual_only', chosen in {'bikini', 'silver_bikini'})),
        'reference_image': u.get('reference_image') or manifest.get('default_reference', ''),
    }
    # Also inherit from manifest-level fallbacks
    ref = info.get('reference_image') or 'assets/persona/seed_avatar.jpg'
    info['reference_image'] = ref
    info['reference_image_exists'] = (MODULE_ROOT.parent / ref).exists() if ref else False
    return info


def load_mood_outfit_map_static() -> Dict[str, str]:
    """Load mood_outfit_map from V111.51 self-contained config only.

    V111.51.2 Final: no hidden dependency on legacy wardrobe profile files.
    """
    data = _load_json(SCENE_OUTFIT_MAP)
    mood_map = data.get('mood_outfit_map', {})
    if mood_map:
        return mood_map
    return {
        'tired': 'pajamas', 'lazy': 'pajamas', 'shy': 'moonfeather_robe',
        'victorious': 'stardust_dream', 'excited': 'stardust_dream',
        'mysterious': 'galaxy_gown', 'sad': 'pajamas', 'relaxed': 'pajamas',
        'happy': 'stardust_dream', 'grateful': 'moonfeather_robe',
        'curious': 'moonfeather_robe', 'playful': 'stardust_dream',
    }
