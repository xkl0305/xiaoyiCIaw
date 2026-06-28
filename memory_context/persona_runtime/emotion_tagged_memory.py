"""V111.6 emotion-tagged memory — stores key interaction moments with emotional context.

Each memory can be tagged with the persona's emotional state at the time,
allowing the voice renderer to reference past emotional highlights.
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
STATE_PATH = ROOT / ".memory_persona" / "persona_state.json"
MEMORY_PATH = ROOT / ".memory_persona" / "emotion_memories.json"
MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_MEMORIES = 50


def load_memories() -> List[Dict[str, Any]]:
    try:
        if MEMORY_PATH.exists():
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_memories(memories: List[Dict[str, Any]]) -> None:
    MEMORY_PATH.write_text(json.dumps(memories, indent=2, ensure_ascii=False), encoding="utf-8")


def record_memory(
    content: str,
    emotion_tag: str,
    intensity: float = 0.5,
    context: Optional[str] = None,
) -> None:
    """
    Record an emotionally significant moment.
    intensity: 0.0 to 1.0 (how strong the emotional signal was)
    """
    now = __import__("time").time()
    memories = load_memories()
    memories.append({
        "timestamp": now,
        "content": content[:200],
        "emotion_tag": emotion_tag,
        "intensity": round(min(1.0, max(0.0, intensity)), 2),
        "context": context[:100] if context else None,
    })
    # Keep only the most recent MAX_MEMORIES
    if len(memories) > MAX_MEMORIES:
        memories = memories[-MAX_MEMORIES:]
    save_memories(memories)


def recent_highlights(limit: int = 5, min_intensity: float = 0.4) -> List[Dict[str, Any]]:
    """Return recent emotionally significant memories."""
    memories = load_memories()
    filtered = [m for m in memories if m.get("intensity", 0) >= min_intensity]
    return filtered[-limit:]


def clear_memories() -> None:
    save_memories([])


__all__ = [
    "load_memories", "save_memories", "record_memory",
    "recent_highlights", "clear_memories",
]
