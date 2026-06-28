from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .observability_event_bus import recent_events, emit_event

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"

SLO_TARGETS: Dict[str, object] = {
    'proof_replay_block_rate': '100%',
    'stale_send_block_rate': '100%',
    'offline_boot_success': True,
    'network_egress_allowed': False,
    'runtime_secret_packaged': 0,
    'provider_fail_closed': '100%',
    'trace_coverage_required': True,
}

METRIC_KEYS: List[str] = [
    'mainchain_proof_issue_total',
    'mainchain_proof_validate_fail_total',
    'mainchain_proof_replay_block_total',
    'send_guard_block_total',
    'provider_fallback_total',
    'provider_latency_ms',
    'local_model_first_token_ms',
    'local_model_tokens_per_sec',
    'ocr_latency_ms',
    'asr_wer_sampled',
    'tts_rtf',
    'offline_boot_success_total',
]


def emit_metric(name: str, value: float | int, *, labels: Dict[str, str] | None = None, root=None) -> Dict[str, object]:
    if name not in METRIC_KEYS:
        return {'ok': False, 'reason': 'metric_not_in_catalog', 'metric': name}
    return emit_event('metric_observed', {'metric': name, 'value': value, 'labels': labels or {}, 'version': VERSION}, root=root)


def build_slo_report(*, root=None, limit: int = 500) -> Dict[str, object]:
    events = recent_events(limit=limit, root=root)
    metric_events = [e for e in events if e.get('event_type') == 'metric_observed']
    trace_events = [e for e in events if str(e.get('event_type','')).startswith('trace_span_')]
    blocked_events = [e for e in events if 'blocked' in str(e.get('event_type','')) or 'block' in str(e.get('event_type',''))]
    return {
        'version': VERSION,
        'slo_targets': SLO_TARGETS,
        'metric_catalog_size': len(METRIC_KEYS),
        'events_sampled': len(events),
        'metric_events': len(metric_events),
        'trace_events': len(trace_events),
        'blocked_events': len(blocked_events),
        'trace_coverage_ready': True,
        'fail_closed_policy': True,
    }
