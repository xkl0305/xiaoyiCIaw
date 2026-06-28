"""V111.6 persona consistency checker — prevents persona drift across sessions.

Validates that the persona state remains consistent with identity definitions
and flags any unexpected drift for review.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from memory_context.persona_runtime.persona_state_machine import load_state
except Exception:
    def load_state() -> Dict[str, Any]:
        return {"mood": "focused", "energy": 70}

VALID_MOODS = {
    "calm", "focused", "playful", "serious", "tired", "proud",
    "working_state", "success_moment", "guardian_mode",
    "amused", "confused", "curious", "determined", "excited",
    "grateful", "lazy", "mysterious", "panicked", "shy", "sneaky", "victorious",
}


def check() -> List[str]:
    """Run consistency checks on persona state and return any violations."""
    state = load_state()
    issues = []
    mood = state.get("mood", "")
    if mood not in VALID_MOODS:
        issues.append(f"Invalid mood: {mood}")
    energy = state.get("energy", 70)
    if not (0 <= energy <= 100):
        issues.append(f"Energy out of range: {energy}")
    confidence = state.get("confidence", 60)
    if not (0 <= confidence <= 100):
        issues.append(f"Confidence out of range: {confidence}")
    uncertainty = state.get("uncertainty", 20)
    if not (0 <= uncertainty <= 100):
        issues.append(f"Uncertainty out of range: {uncertainty}")
    trust = state.get("trust_level", 30)
    if not (0 <= trust <= 100):
        issues.append(f"Trust level out of range: {trust}")
    return issues


def is_stable(report_issues: bool = False) -> bool:
    issues = check()
    if report_issues:
        return len(issues) == 0, issues
    return len(issues) == 0


__all__ = ["check", "is_stable"]
