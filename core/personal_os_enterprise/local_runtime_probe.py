from __future__ import annotations

import json
import shutil
import socket
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .local_model_registry import load_local_model_registry


_STUB_SERVER_MARKER = 'status": "ok", "ready": true, "mode": "local_only"'
_STUB_ENDPOINTS = {8002, 8003, 8005, 8006}


def _path_ready(path: str) -> bool:
    if not path:
        return False
    return Path(path).expanduser().exists()


def _command_ready(command: str) -> bool:
    if not command:
        return False
    first = str(command).split()[0]
    return bool(shutil.which(first))


def _local_endpoint_ready(endpoint: str, timeout: float = 0.25) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    if parsed.scheme not in {'http', 'https'}:
        return False
    if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout):
            return True
    except Exception:
        return False


def _is_stub_endpoint(endpoint: str, timeout: float = 1.0) -> bool:
    """Check if the HTTP endpoint is the known stub server (not a real inference server)."""
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        return False
    port = parsed.port or 80
    if port not in _STUB_ENDPOINTS:
        return False
    health_url = 'http://{}:{}/health'.format(parsed.hostname, port)
    try:
        resp = urllib.request.urlopen(health_url, timeout=timeout)
        body = resp.read().decode('utf-8')
        resp.close()
        data = json.loads(body)
        # Stub server returns capability name and no real model info.
        # A real inference server (vLLM/Ollama/llama.cpp) would NOT return this exact signature.
        return data.get('capability') is not None and data.get('status') == 'ok' and data.get('endpoint', '').startswith('http://127.0.0.1:')
    except Exception:
        return False


def _is_command_stub(command: str) -> bool:
    if not command:
        return False
    low = command.lower()
    return (
        'print(' in low
        or 'print (' in low
        or 'xor' in low
        or 'stub' in low
    )


def probe_capability(capability: str, root: Optional[str | Path] = None) -> Dict[str, Any]:
    reg = load_local_model_registry(root)
    item = reg.get(capability)
    if not item:
        return {
            'capability': capability,
            'ready': False,
            'ready_kind': 'not_configured',
            'reason': 'unknown_capability',
            'allow_external_fallback': False,
        }
    checks = {
        'enabled_declared': bool(item.get('enabled')),
        'model_path_exists': _path_ready(str(item.get('model_path') or item.get('path') or '')),
        'command_exists': _command_ready(str(item.get('command') or '')),
        'local_endpoint_ready': _local_endpoint_ready(str(item.get('endpoint') or '')),
    }
    ready = checks['enabled_declared'] and (checks['model_path_exists'] or checks['command_exists'] or checks['local_endpoint_ready'])
    reason = 'ready' if ready else 'local_capability_not_available'

    if item.get('endpoint_rejected'):
        reason = item['endpoint_rejected']
        ready = False

    # Determine ready_kind
    ready_kind = 'not_configured'
    if not item.get('enabled'):
        ready_kind = 'disabled'
    elif not ready:
        ready_kind = 'environment_blocked' if item.get('enabled') else 'not_configured'
    elif checks['model_path_exists']:
        ready_kind = 'real_model_ready'
    elif checks['command_exists'] and _is_command_stub(str(item.get('command', ''))):
        ready_kind = 'stub_ready_only'
    elif checks['local_endpoint_ready'] and _is_stub_endpoint(str(item.get('endpoint', ''))):
        # Endpoint is the known stub server
        ready_kind = 'stub_ready_only'
    elif checks['local_endpoint_ready']:
        # Live endpoint that is NOT a known stub - could be real inference server
        ready_kind = 'real_model_ready'
    elif checks['command_exists']:
        ready_kind = 'real_model_ready'
    else:
        ready_kind = 'environment_blocked'

    return {
        'capability': capability,
        'ready': ready,
        'ready_kind': ready_kind,
        'reason': reason,
        'checks': checks,
        'connection_mode': 'local_only',
        'allow_external_fallback': False,
        'provider': item.get('provider') or item.get('name') or '',
    }


def probe_all_capabilities(root: Optional[str | Path] = None) -> Dict[str, Any]:
    reg = load_local_model_registry(root)
    probes = {cap: probe_capability(cap, root=root) for cap in reg}
    real_ready_count = sum(1 for p in probes.values() if p.get('ready_kind') == 'real_model_ready')
    return {
        'overall': 'ready' if all(p.get('ready') for p in probes.values()) else 'partial_or_unavailable',
        'real_model_ready': real_ready_count > 0,
        'ready_kinds': {cap: p.get('ready_kind') for cap, p in probes.items()},
        'network_egress_attempted': False,
        'allow_external_fallback': False,
        'probes': probes,
    }
