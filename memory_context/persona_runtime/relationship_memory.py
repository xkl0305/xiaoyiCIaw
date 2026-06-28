"""V111.6 relationship memory — tracks user preferences and interaction patterns.

Each conversation extracts and stores user preferences, common phrases,
and interaction history to build a personalized experience over time.
"""

from __future__ import annotations

import json
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
STATE_PATH = ROOT / ".memory_persona" / "relationship_memory.json"


def _default() -> Dict[str, Any]:
    return {
        "user_long_term_goals": [],
        "user_dislikes": [],
        "user_preferred_style": [],
        "user_frequent_topics": [],
        "user_risk_preference": "conservative",
        "user_persona_expectations": [],
        "last_key_event": None,
        "last_failure_or_fix": None,
        "user_common_phrases": [],
        "user_do_not_repeat": [],
        "key_events": [],
        "interaction_count": 0,
        "correction_count": 0,
        "praise_count": 0,
        "last_updated_at": None,
        "first_met_at": None,
    }


def load() -> Dict[str, Any]:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            merged = _default()
            merged.update(data)
            return merged
    except Exception:
        pass
    return _default()


def save(data: Dict[str, Any]) -> None:
    import time
    data["last_updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    if data.get("first_met_at") is None:
        data["first_met_at"] = data["last_updated_at"]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def increment_interaction() -> int:
    data = load()
    data["interaction_count"] = (data.get("interaction_count") or 0) + 1
    save(data)
    return data["interaction_count"]


def add_preference(category: str, value: str) -> None:
    """Add a preference. category: user_long_term_goals | user_dislikes | user_frequent_topics | etc."""
    data = load()
    if category in data and isinstance(data[category], list):
        if value not in data[category]:
            data[category].append(value)
            if len(data[category]) > 50:
                data[category] = data[category][-50:]
        save(data)


def record_correction() -> None:
    data = load()
    data["correction_count"] = (data.get("correction_count") or 0) + 1
    save(data)


def record_praise() -> None:
    data = load()
    data["praise_count"] = (data.get("praise_count") or 0) + 1
    save(data)


def get_summary() -> Dict[str, Any]:
    data = load()
    return {
        "interactions": data.get("interaction_count", 0),
        "corrections": data.get("correction_count", 0),
        "praises": data.get("praise_count", 0),
        "risk_preference": data.get("user_risk_preference", "conservative"),
        "frequent_topics": data.get("user_frequent_topics", [])[-5:],
        "style": data.get("user_preferred_style", []),
        "dislikes": data.get("user_dislikes", []),
    }


__all__ = [
    "load", "save", "increment_interaction", "add_preference",
    "record_correction", "record_praise", "get_summary",
]
