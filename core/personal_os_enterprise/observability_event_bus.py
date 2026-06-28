from __future__ import annotations

from typing import Any, Dict, List

from .enterprise_runtime_db import insert_event, read_events


def emit_event(event_type: str, payload: Dict[str, Any] | None = None, *, root=None) -> Dict[str, Any]:
    return insert_event(event_type, payload or {}, root=root)


def recent_events(limit: int = 100, *, root=None) -> List[Dict[str, Any]]:
    return read_events(limit=limit, root=root)
