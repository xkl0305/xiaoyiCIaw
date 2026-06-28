from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .local_capability_registry import assert_declared_capabilities, list_capabilities
from .local_runtime_probe import probe_all_capabilities, probe_capability


def health_check(capabilities: Iterable[str] | None = None, root: Optional[str | Path] = None) -> Dict[str, Any]:
    registry = assert_declared_capabilities()
    probes_all = probe_all_capabilities(root=root)
    probes = probes_all['probes']
    if capabilities:
        wanted = set(capabilities)
        probes = {k: v for k, v in probes.items() if k in wanted}
    required_not_ready = [k for k, v in probes.items() if not v.get('ready')]
    return {
        'overall': 'ready' if registry.get('ok') and not required_not_ready else 'degraded',
        'registry_ok': registry.get('ok'),
        'registry': registry,
        'required_not_ready': required_not_ready,
        'network_egress_attempted': False,
        'allow_external_fallback': False,
        'probes': probes,
    }


def require_capabilities(capabilities: Iterable[str], root: Optional[str | Path] = None) -> Dict[str, Any]:
    caps = list(capabilities)
    checks = {cap: probe_capability(cap, root=root) for cap in caps}
    missing = [cap for cap, out in checks.items() if not out.get('ready')]
    return {
        'ok': not missing,
        'missing': missing,
        'blocked': bool(missing),
        'blocked_reason': 'capability_not_available' if missing else '',
        'allow_external_fallback': False,
        'checks': checks,
    }
