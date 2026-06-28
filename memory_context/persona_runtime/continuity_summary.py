"""V111.6 continuity summary — generates and maintains conversation continuity summaries.

Periodically generates a short summary of the conversation context for
session handoff and continuity across compactions.
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
STATE_PATH = ROOT / ".memory_persona" / "continuity_summary.json"


def load() -> Dict[str, Any]:
    try:
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_summary": None, "updated_at": None, "session_count": 0, "total_interactions": 0}


def save(data: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def update(summary_text: str) -> None:
    data = load()
    data["last_summary"] = summary_text[:500]
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    data["session_count"] = (data.get("session_count") or 0) + 1
    save(data)


def get_latest() -> Optional[str]:
    data = load()
    return data.get("last_summary")


__all__ = ["load", "save", "update", "get_latest"]
