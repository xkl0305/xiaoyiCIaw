"""
V111.49.2: Compatibility bridge file.

This file no longer contains independent choose_outfit logic.
All real logic lives in:
    xiaoyi_persona_visual/wardrobe/wardrobe_loader.py

Functions below are re-exported from the new module to maintain
backward compatibility for existing callers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from xiaoyi_persona_visual.wardrobe.wardrobe_loader import (
    choose_outfit as _wardrobe_choose_outfit,
    is_last_outfit_continuity as _wardrobe_is_last_outfit_continuity,
    is_forbidden_last_outfit as _wardrobe_is_forbidden_last_outfit,
    is_display_appearance_request as _wardrobe_is_display_appearance_request,
    save_current_outfit as _wardrobe_save_current_outfit,
    current_outfit as _wardrobe_current_outfit,
    load_runtime_state as _wardrobe_load_runtime_state,
)

# ── Backward compat: used by audit/scripts ──
AUTO_SAFE_FORBIDDEN = {'bikini', 'silver_bikini'}


def _profiles() -> Dict[str, Any]:
    """Backward compat: load profiles (from the new module's companion file).
    
    V111.49.2: This is a bridge — only used for backward compat by scripts/diagnose_v111.py.
    """
    from xiaoyi_persona_visual.wardrobe.wardrobe_loader import load_wardrobe_manifest, load_scene_outfit_map, load_focus_outfit_map
    # Direct-provider package: do not read legacy visual_wardrobe_profiles.json.
    return {
        'wardrobe_manifest': load_wardrobe_manifest(),
        'scene_outfit_map': load_scene_outfit_map(),
        'focus_outfit_map': load_focus_outfit_map(),
    }


def choose_outfit(
    text: str = '',
    mood: str = '',
    semantic_scene: str = '',
    requested_outfit: str = '',
    focus_target: str = '',
    auto_mode: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Forward to new xiaoyi_persona_visual/wardrobe/wardrobe_loader.choose_outfit()"""
    return _wardrobe_choose_outfit(
        text=text,
        mood=mood,
        semantic_scene=semantic_scene,
        requested_outfit=requested_outfit,
        focus_target=focus_target,
        auto_mode=auto_mode,
        **kwargs,
    )


def is_last_outfit_continuity(text: str) -> bool:
    return _wardrobe_is_last_outfit_continuity(text)


def is_forbidden_last_outfit(text: str) -> bool:
    return _wardrobe_is_forbidden_last_outfit(text)


def is_display_appearance_request(text: str) -> bool:
    """Check if text is a display-appearance request that must NOT fallback to bashful_scene."""
    return _wardrobe_is_display_appearance_request(text)


def save_current_outfit(outfit_id: str) -> Dict[str, Any]:
    return _wardrobe_save_current_outfit(outfit_id)


def current_outfit() -> str:
    return _wardrobe_current_outfit()


def _state() -> Dict[str, Any]:
    """Legacy compat: return runtime state dict."""
    from xiaoyi_persona_visual.wardrobe.wardrobe_loader import load_runtime_state
    return load_runtime_state()
