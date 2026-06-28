"""V111.8 context capsule — compressable context snapshot for session recovery.

from __future__ import annotations

Responsible for: packing current context (goal, active task, key facts,
user preferences, pending actions) into a recoverable capsule.

Used by: memory_recall_bootstrap and session_handoff.
"""

__version__ = "V111.8"

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ContextCapsule:
    """Serializable capsule for context recovery."""
    goal: Optional[str] = None
    active_task: Optional[str] = None
    current_stage: Optional[str] = None
    key_facts: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    pending_actions: List[str] = field(default_factory=list)
    last_decision: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return asdict(self)


def create_context_capsule(
    *,
    goal: Optional[str] = None,
    active_task: Optional[str] = None,
    current_stage: Optional[str] = None,
    key_facts: Optional[List[str]] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    pending_actions: Optional[List[str]] = None,
    last_decision: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ContextCapsule:
    """Create a context capsule from the given parameters."""
    _meta = dict(metadata or {})
    _meta["decision"] = "minimal_compatible_real_implementation"
    _meta["source"] = "memory_context.continuity.context_capsule"

    return ContextCapsule(
        goal=goal,
        active_task=active_task,
        current_stage=current_stage,
        key_facts=key_facts or [],
        user_preferences=user_preferences or {},
        pending_actions=pending_actions or [],
        last_decision=last_decision,
        metadata=_meta,
    )


def load_context_capsule(payload: Dict[str, Any]) -> ContextCapsule:
    """Restore a ContextCapsule from a dict."""
    return ContextCapsule(
        goal=payload.get("goal"),
        active_task=payload.get("active_task"),
        current_stage=payload.get("current_stage"),
        key_facts=payload.get("key_facts", []),
        user_preferences=payload.get("user_preferences", {}),
        pending_actions=payload.get("pending_actions", []),
        last_decision=payload.get("last_decision"),
        metadata=payload.get("metadata", {}),
        created_at=payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


def capsule_to_dict(capsule: ContextCapsule) -> Dict[str, Any]:
    """Convenience alias for capsule.to_dict()."""
    return capsule.to_dict()


__all__ = [
    "ContextCapsule",
    "create_context_capsule",
    "load_context_capsule",
    "capsule_to_dict",
]
