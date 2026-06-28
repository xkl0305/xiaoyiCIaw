"""V111.6 persona voice renderer — adjusts reply tone based on persona state.

Takes the current persona state (mood, energy, confidence) and returns
voice adjustment hints for the reply generation.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    from memory_context.persona_runtime.persona_state_machine import (
        load_state, get_voice_adjustment, MOODS
    )
except Exception:
    # Fallback if imported directly
    def load_state() -> Dict[str, Any]:
        return {"mood": "focused", "energy": 70, "confidence": 60, "uncertainty": 20}

    def get_voice_adjustment() -> Dict[str, Any]:
        return {"verbosity": "normal", "warmth": "neutral"}

    MOODS = ["focused", "calm"]


def render_voice_hints() -> Dict[str, Any]:
    """Return voice/style hints for the current persona state."""
    state = load_state()
    adj = get_voice_adjustment()
    return {
        "mood": state.get("mood", "focused"),
        "energy": state.get("energy", 70),
        "confidence": state.get("confidence", 60),
        "verbosity": adj.get("verbosity", "normal"),
        "warmth": adj.get("warmth", "neutral"),
        "confidence_marker": adj.get("confidence_marker", "neutral"),
        "confirmation_frequency": adj.get("confirmation_frequency", "low"),
    }


def get_mood_description() -> str:
    """Return a short description of current mood for voice guidance."""
    state = load_state()
    mood = state.get("mood", "focused")
    energy = state.get("energy", 70)
    confidence = state.get("confidence", 60)
    parts = [f"Mood: {mood}"]
    if energy < 35:
        parts.append("low energy")
    elif energy > 80:
        parts.append("high energy")
    if confidence > 80:
        parts.append("assertive")
    elif confidence < 40:
        parts.append("uncertain")
    return ", ".join(parts)


__all__ = ["render_voice_hints", "get_mood_description"]
