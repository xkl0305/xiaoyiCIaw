"""V111.6 self-reflection log — records introspection entries for learning.

Stores timestamped reflection entries that can be reviewed to understand
how the persona evaluated its own performance over time.
"""

from __future__ import annotations

import json
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
LOG_PATH = ROOT / ".memory_persona" / "self_reflection_log.json"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_ENTRIES = 30


def load() -> List[Dict[str, Any]]:
    try:
        if LOG_PATH.exists():
            data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def append(entry: Dict[str, Any]) -> None:
    entries = load()
    entry["timestamp"] = time.time()
    entries.append(entry)
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    LOG_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def recent(limit: int = 5) -> List[Dict[str, Any]]:
    entries = load()
    return entries[-limit:]


def clear() -> None:
    LOG_PATH.write_text("[]", encoding="utf-8")


__all__ = ["load", "append", "recent", "clear"]
