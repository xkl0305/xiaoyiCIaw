from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, List

MODULE_ROOT = Path(__file__).resolve().parents[1]

_identity_profile = None
_style_profile = None
_avatar_binding = None
_persona_state = None


def _load_json(rel_path: str) -> Dict[str, Any]:
    fp = MODULE_ROOT / rel_path
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def load_all_profiles() -> Dict[str, bool]:
    global _identity_profile, _style_profile, _avatar_binding, _persona_state
    _identity_profile = _load_json('config/visual_identity_profile.json')
    _style_profile = _load_json('config/style_profile.json')
    _avatar_binding = _load_json('config/default_avatar_binding.json')
    _persona_state = _load_json('config/default_persona_visual_state.json')
    return {
        'identity_profile_loaded': bool(_identity_profile),
        'style_profile_loaded': bool(_style_profile),
        'avatar_binding_loaded': bool(_avatar_binding),
        'persona_state_loaded': bool(_persona_state),
    }


class PersonaVisualController:
    """Central controller for persona visualization pipeline.

    The controller enforces:
    - Identity lock (gender, face consistency)
    - Style lock (anime illustration only)
    - Avatar binding (always use seed_avatar as reference)
    - Debug field population
    """

    def __init__(self):
        self._initialized = False
        self._identity_loaded = False
        self._style_loaded = False
        self._pipeline_entry = 'persona_visual_controller'
        self._debug_fields = {}
        self._debug_fields_populated = False

    def initialize(self) -> Dict[str, bool]:
        load_results = load_all_profiles()
        self._identity_loaded = load_results.get('identity_profile_loaded', False)
        self._style_loaded = load_results.get('style_profile_loaded', False)
        self._initialized = True
        return {
            'persona_visual_controller_used': True,
            'identity_profile_loaded': self._identity_loaded,
            'style_profile_loaded': self._style_loaded,
            **load_results,
        }

    def enforce_identity_lock(self, prompt: str = '') -> str:
        """Apply identity-lock constraints to the prompt."""
        if not _identity_profile:
            return prompt
        identity = _identity_profile.get('identity_lock', False)
        gender = _identity_profile.get('gender_lock', 'female')
        if identity:
            prompt += ', preserve same face, preserve same identity, same character'
        if gender:
            prompt += f', {gender}'
        return prompt

    def enforce_style_lock(self, prompt: str = '') -> str:
        """Apply style-lock constraints to the prompt."""
        if not _style_profile:
            return prompt
        style = _style_profile.get('default_style', 'anime_illustration')
        style_head = _style_profile.get('style_prompt_head', '')
        if style_head and not prompt.startswith(style_head):
            prompt = style_head + ', ' + prompt
        return prompt

    def enforce_avatar_binding(self, prompt: str = '') -> str:
        """Apply avatar binding constraints."""
        if not _avatar_binding:
            return prompt
        if _avatar_binding.get('avatar_binding', False):
            prompt = '图片内角色不变，生成图片内的人物要和参考图内人物保持像素级一致性，进行生成。' + prompt
        return prompt

    def build_pipeline_prompt(self, base_prompt: str = '') -> str:
        p = base_prompt
        p = self.enforce_avatar_binding(p)
        p = self.enforce_style_lock(p)
        p = self.enforce_identity_lock(p)
        return p

    def populate_debug_fields(
        self,
        result: Dict[str, Any],
        scene_type: str = '',
        scene_confidence: float = 0.0,
        focus_target: str = '',
        outfit_source: str = '',
        outfit_id: str = '',
        prompt_builder_used: str = 'persona_image_prompt_builder',
        negative_prompt_guard_used: bool = True,
        fallback_used: bool = False,
        fallback_reason: str = '',
        visual_request_source: str = '',
    ) -> Dict[str, Any]:
        """Populate debug fields on the result dict."""
        result['visual_request_detected'] = True
        result['visual_request_source'] = visual_request_source
        result['pipeline_entry'] = self._pipeline_entry
        result['persona_visual_controller_used'] = True
        result['identity_profile_loaded'] = self._identity_loaded
        result['style_profile_loaded'] = self._style_loaded
        result['scene_type'] = scene_type
        result['scene_confidence'] = scene_confidence
        result['focus_target'] = focus_target
        result['outfit_source'] = outfit_source
        result['outfit_id'] = outfit_id
        result['prompt_builder_used'] = prompt_builder_used
        result['negative_prompt_guard_used'] = negative_prompt_guard_used
        result['fallback_used'] = fallback_used
        result['fallback_reason'] = fallback_reason
        result['gender_lock'] = _identity_profile.get('gender_lock', 'female') if _identity_profile else 'female'
        result['style_lock'] = _style_profile.get('style_lock', True) if _style_profile else True
        self._debug_fields_populated = True
        return result
