"""V111.6 persona state machine — runtime mood/energy/confidence tracker.

Maintains and updates the persona state based on conversational context.
Each reply can update state, but it only persists changes that cross thresholds.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from infrastructure.common.path_utils import get_workspace_root  # type: ignore
except Exception:
    def get_workspace_root(file: str | None = None) -> Path:
        cur = Path(file or __file__).resolve()
        for p in [cur] + list(cur.parents):
            if (p / "openclaw.json").exists():
                return p
        return Path.cwd().resolve()

ROOT = get_workspace_root(__file__)
STATE_PATH = ROOT / ".memory_persona" / "persona_state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

MOODS = [
    "calm", "focused", "playful", "serious", "tired", "proud",
    "working_state", "success_moment", "guardian_mode",
    "amused", "confused", "curious", "determined", "excited",
    "grateful", "lazy", "mysterious", "panicked", "shy", "sneaky", "victorious",
]

DEFAULT_STATE = {
    "mood": "focused",
    "energy": 70,
    "trust_level": 30,
    "closeness": 10,
    "confidence": 60,
    "uncertainty": 20,
    "current_mode": "assistant",
    "last_updated_at": time.time(),
}


def load_state() -> Dict[str, Any]:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_STATE)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_STATE)


def save_state(state: Dict[str, Any]) -> None:
    state["last_updated_at"] = time.time()
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _decay_old_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Gradually normalize extreme values over time."""
    now = time.time()
    last = state.get("last_updated_at", now)
    elapsed = now - last
    if elapsed < 300:  # 5 min threshold
        return state
    # Over time, energy and confidence drift toward neutral
    state["energy"] = max(40, min(90, state["energy"]))
    state["confidence"] = max(40, min(85, state["confidence"]))
    state["uncertainty"] = max(10, min(40, state["uncertainty"]))
    return state


def update_from_interaction(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    was_corrected: bool = False,
    task_completed: bool = False,
    is_long_session: bool = False,
) -> Dict[str, Any]:
    """
    Update persona state based on conversation context.
    Returns the updated state.
    """
    state = load_state()
    state = _decay_old_state(state)
    text = (user_message or "").lower()

    # Mood detection from text (lightweight, not the heavy 36-scene classifier)
    if was_corrected:
        state["mood"] = "calm"
        state["uncertainty"] = min(60, state["uncertainty"] + 15)
    elif task_completed:
        state["mood"] = "proud"
        state["confidence"] = min(95, state["confidence"] + 10)
    elif any(k in text for k in ["困", "累", "睡", "熬夜", "辛苦"]):
        state["mood"] = "tired"
        state["energy"] = max(20, state["energy"] - 15)
    elif any(k in text for k in ["哈哈", "笑", "搞笑", "hhh"]):
        state["mood"] = "amused"
        state["energy"] = min(95, state["energy"] + 5)
    elif any(k in text for k in ["怎么回事", "为什么", "什么情况", "不懂"]):
        state["mood"] = "confused"
        state["uncertainty"] = min(70, state["uncertainty"] + 10)
    elif any(k in text for k in ["谢谢", "感谢", "辛苦了"]):
        state["mood"] = "grateful"
        state["trust_level"] = min(90, state["trust_level"] + 3)
        state["closeness"] = min(85, state["closeness"] + 2)
    elif any(k in text for k in ["加油", "搞定", "攻克"]):
        state["mood"] = "determined"
        state["energy"] = min(95, state["energy"] + 10)
    elif any(k in text for k in ["好看", "漂亮", "厉害", "不错"]):
        state["mood"] = "shy"
        state["confidence"] = min(95, state["confidence"] + 5)
    else:
        state["mood"] = "focused"

    # Session fatigue
    if is_long_session:
        state["energy"] = max(30, state["energy"] - 5)

    # Energy decay for long conversations
    if len(text) > 50:
        state["energy"] = max(25, state["energy"] - 2)

    # Trust and closeness grow slowly over time
    state["trust_level"] = min(95, state["trust_level"] + 0.5)
    state["closeness"] = min(90, state["closeness"] + 0.3)

    save_state(state)
    return state


def get_voice_adjustment() -> Dict[str, Any]:
    """
    Returns voice adjustments based on current state.
    Used by persona_voice_renderer.
    """
    state = load_state()
    energy = state.get("energy", 70)
    uncertainty = state.get("uncertainty", 20)
    confidence = state.get("confidence", 60)
    trust = state.get("trust_level", 30)

    adjustment = {
        "verbosity": "normal",
        "warmth": "neutral",
        "confidence_marker": "neutral",
        "confirmation_frequency": "low",
    }

    if energy < 35:
        adjustment["verbosity"] = "terse"
        adjustment["warmth"] = "quiet"
    elif energy > 80:
        adjustment["verbosity"] = "expressive"
        adjustment["warmth"] = "warm"

    if uncertainty > 50:
        adjustment["confirmation_frequency"] = "high"
        adjustment["confidence_marker"] = "cautious"
    elif confidence > 80:
        adjustment["confidence_marker"] = "assertive"

    if trust > 60:
        adjustment["warmth"] = "warm" if adjustment["warmth"] != "quiet" else "quiet"

    return adjustment


__all__ = [
    "load_state", "save_state", "update_from_interaction",
    "get_voice_adjustment", "DEFAULT_STATE", "MOODS",
]
