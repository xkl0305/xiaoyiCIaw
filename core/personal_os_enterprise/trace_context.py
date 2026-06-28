from __future__ import annotations
import contextlib, time, uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Iterator, Optional
from .observability_event_bus import emit_event
VERSION = 'V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'
@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str = ''
    request_id: str = ''
    entrypoint: str = 'personal_os'
def new_trace(*, request_id: str = '', entrypoint: str = 'personal_os') -> TraceContext:
    return TraceContext(str(uuid.uuid4()), str(uuid.uuid4()), request_id=request_id, entrypoint=entrypoint)
@contextlib.contextmanager
def span(name: str, *, trace: Optional[TraceContext] = None, root: Optional[str | Path] = None, **attrs) -> Iterator[TraceContext]:
    parent = trace or new_trace(entrypoint=attrs.get('entrypoint','personal_os'))
    cur = TraceContext(parent.trace_id, str(uuid.uuid4()), parent.span_id, parent.request_id, parent.entrypoint)
    started = time.time(); status = 'ok'; error = ''
    emit_event('trace_span_start', {'name': name, **asdict(cur), 'attrs': attrs, 'started_at': started, 'version': VERSION}, root=root)
    try:
        yield cur
    except Exception as e:
        status = 'error'; error = f'{type(e).__name__}: {e}'; raise
    finally:
        emit_event('trace_span_end', {'name': name, **asdict(cur), 'status': status, 'error': error, 'duration_ms': int((time.time()-started)*1000), 'version': VERSION}, root=root)
def trace_event(event_type: str, payload: Dict[str, Any], *, trace: Optional[TraceContext] = None, root: Optional[str | Path] = None) -> None:
    d = dict(payload)
    if trace:
        d.update({'trace_id': trace.trace_id, 'span_id': trace.span_id, 'request_id': trace.request_id, 'entrypoint': trace.entrypoint})
    emit_event(event_type, d, root=root)
