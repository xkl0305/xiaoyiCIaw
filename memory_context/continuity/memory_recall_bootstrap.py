"""V111.8 memory recall bootstrap — guides session recovery from compacted context.

from __future__ import annotations

Responsible for: creating recall hints from compact summary, context capsule,
and session state to guide continuity restoration.

Does not: operate on databases, write to core/agent_kernel, or trigger tools.
"""

__version__ = "V111.8"

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecallHint:
    """A single hint about what to recall."""
    key: str = ""
    reason: str = ""
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecallPlan:
    """Collection of recall hints and metadata about the recall context."""
    source: str = "memory_recall_bootstrap"
    hints: List[MemoryRecallHint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


_HINT_QUEUE: List[MemoryRecallHint] = []


def build_memory_recall_plan(
    compact_summary: Optional[str] = None,
    context_capsule: Optional[Dict[str, Any]] = None,
    session_state: Optional[Dict[str, Any]] = None,
    *,
    max_hints: int = 12,
) -> MemoryRecallPlan:
    """Build a recall plan from available compacted context sources."""
    hints: List[MemoryRecallHint] = []
    has_compact = False
    has_capsule = False
    has_session = False

    if compact_summary:
        hint = MemoryRecallHint(
            key="compact_summary",
            reason="Recover from compacted conversation summary.",
            priority=100,
            metadata={"text_preview": compact_summary[:500]},
        )
        hints.append(hint)
        has_compact = True

    if context_capsule:
        for field_name in ("goal", "active_task", "last_decision", "pending_actions", "user_preferences"):
            val = context_capsule.get(field_name)
            if val:
                priority = 80
                hints.append(MemoryRecallHint(
                    key=f"capsule_{field_name}",
                    reason=f"Recover {field_name} from context capsule.",
                    priority=priority,
                    metadata={"value": str(val)[:300]},
                ))
        has_capsule = True

    if session_state:
        for field_name in ("session_id", "task_id", "current_stage", "open_loops"):
            val = session_state.get(field_name)
            if val:
                hints.append(MemoryRecallHint(
                    key=f"session_{field_name}",
                    reason=f"Recover {field_name} from session state.",
                    priority=60,
                    metadata={"value": str(val)[:300]},
                ))
        has_session = True

    hints.sort(key=lambda h: h.priority, reverse=True)
    hints = hints[:max_hints]
    _HINT_QUEUE.clear()
    _HINT_QUEUE.extend(hints)

    return MemoryRecallPlan(
        source="memory_recall_bootstrap",
        hints=hints,
        metadata={
            "compact_summary_present": has_compact,
            "context_capsule_present": has_capsule,
            "session_state_present": has_session,
            "decision": "minimal_compatible_real_implementation",
            "source": "memory_context.continuity.memory_recall_bootstrap",
        },
    )


def bootstrap_memory_recall(*args: Any, **kwargs: Any) -> MemoryRecallPlan:
    """Compatibility alias for build_memory_recall_plan."""
    return build_memory_recall_plan(*args, **kwargs)


__all__ = [
    "MemoryRecallHint",
    "MemoryRecallPlan",
    "build_memory_recall_plan",
    "bootstrap_memory_recall",
]
