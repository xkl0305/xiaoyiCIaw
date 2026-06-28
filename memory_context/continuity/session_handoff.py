"""V111.8 session handoff — cross-session task continuity packet.

from __future__ import annotations

Responsible for: saving handoff summary, current stage, pending actions,
and risk hints. Produces a serializable handoff packet.

Does not: execute tasks or trigger tool calls directly.
"""

__version__ = "V111.8"

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SessionHandoffPacket:
    """Serializable packet for cross-session handoff."""
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    current_stage: Optional[str] = None
    summary: str = ""
    pending_actions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return asdict(self)


def create_session_handoff(
    *,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    current_stage: Optional[str] = None,
    summary: str = "",
    pending_actions: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    decisions: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> SessionHandoffPacket:
    """Create a handoff packet with the given context."""
    _meta = dict(metadata or {})
    _meta["decision"] = "minimal_compatible_real_implementation"
    _meta["source"] = "memory_context.continuity.session_handoff"

    return SessionHandoffPacket(
        session_id=session_id,
        task_id=task_id,
        current_stage=current_stage,
        summary=summary,
        pending_actions=pending_actions or [],
        risks=risks or [],
        decisions=decisions or [],
        metadata=_meta,
    )


def load_session_handoff(payload: Dict[str, Any]) -> SessionHandoffPacket:
    """Restore a SessionHandoffPacket from a dict."""
    return SessionHandoffPacket(
        session_id=payload.get("session_id"),
        task_id=payload.get("task_id"),
        current_stage=payload.get("current_stage"),
        summary=payload.get("summary", ""),
        pending_actions=payload.get("pending_actions", []),
        risks=payload.get("risks", []),
        decisions=payload.get("decisions", []),
        metadata=payload.get("metadata", {}),
        created_at=payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


def build_handoff_packet(*args: Any, **kwargs: Any) -> SessionHandoffPacket:
    """Compatibility alias for create_session_handoff."""
    return create_session_handoff(*args, **kwargs)


__all__ = [
    "SessionHandoffPacket",
    "create_session_handoff",
    "load_session_handoff",
    "build_handoff_packet",
]
