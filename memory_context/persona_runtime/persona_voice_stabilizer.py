"""V111.6 persona voice stabilizer — prevents dramatic tone swings between replies.

Ensures that mood/energy changes don't cause jarring tonal shifts
within a single conversation session.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from memory_context.persona_runtime.persona_state_machine import load_state, MOODS
except Exception:
    def load_state() -> Dict[str, Any]:
        return {"mood": "focused", "energy": 70, "confidence": 60}

    MOODS = ["focused", "calm"]


def smooth_state_change(
    current_state: Dict[str, Any],
    previous_mood: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply smoothing to prevent jarring mood transitions."""
    if previous_mood is None:
        return current_state
    current_mood = current_state.get("mood", "focused")
    if current_mood != previous_mood:
        # Allow mood changes but ensure they're reasonable
        prev_idx = MOODS.index(previous_mood) if previous_mood in MOODS else -1
        cur_idx = MOODS.index(current_mood) if current_mood in MOODS else -1
        if prev_idx >= 0 and cur_idx >= 0 and abs(cur_idx - prev_idx) > 5:
            # Large jump - cap energy change
            current_state["energy"] = max(30, min(90, current_state.get("energy", 70)))
    return current_state


def validate_reply_tone(
    mood: str,
    energy: int,
) -> bool:
    """Validate that a proposed mood/energy combination is coherent."""
    if mood in {"tired", "lazy", "calm"} and energy > 80:
        return False
    if mood in {"excited", "panicked", "victorious"} and energy < 30:
        return False
    if mood == "confused" and energy > 90:
        return False
    return True


__all__ = ["smooth_state_change", "validate_reply_tone"]
