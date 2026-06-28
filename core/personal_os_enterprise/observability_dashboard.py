from __future__ import annotations

from typing import Any, Dict

from .metrics_catalog import list_metrics
from .observability_event_bus import recent_events


def dashboard_report(limit: int = 100, *, root=None) -> Dict[str, Any]:
    events = recent_events(limit=limit, root=root)
    counts: Dict[str, int] = {}
    for e in events:
        event_type = str(e.get('event_type') or e.get('type') or 'unknown')
        counts[event_type] = counts.get(event_type, 0) + 1
    return {
        'status': 'ok',
        'backend': 'sqlite_wal',
        'metrics_defined': list_metrics(),
        'event_counts': counts,
        'event_sample_count': len(events),
        'network_egress_attempted': False,
    }
