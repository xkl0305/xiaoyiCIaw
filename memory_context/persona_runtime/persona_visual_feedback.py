"""Feedback learning for persona visual output.
Stores user feedback as candidate preferences. It never rewrites core code.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, Optional
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".visual_persona_state"
STATE.mkdir(parents=True, exist_ok=True)
FEEDBACK = STATE / "visual_feedback.jsonl"
PREFERENCES = STATE / "visual_preferences.json"
def load_visual_preferences() -> Dict[str, Any]:
    if not PREFERENCES.exists(): return {"mood_feedback": {}, "rules": [], "note": "candidate preferences; no direct core rewrite"}
    try: return json.loads(PREFERENCES.read_text(encoding="utf-8"))
    except Exception: return {"mood_feedback": {}, "rules": []}
def record_visual_feedback(image_path: Optional[str], feedback_text: str, *, mood: Optional[str] = None, rating: Optional[int] = None) -> Dict[str, Any]:
    event = {"ts": time.time(), "image_path": image_path, "feedback_text": feedback_text, "mood": mood, "rating": rating, "decision": "candidate_preference_only"}
    with FEEDBACK.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    prefs = load_visual_preferences()
    if mood:
        prefs.setdefault("mood_feedback", {}).setdefault(mood, []).append({"text": feedback_text, "rating": rating, "ts": event["ts"]})
    PREFERENCES.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    return event
