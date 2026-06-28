from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except Exception:
    tomllib = None

SYSTEM_VERSION = 'V111.52.11_LOCAL_RUNTIME_METADATA_AND_ACCEPTANCE_CLOSE_FINAL'

DEFAULT_STRICT_LOCAL_ENTERPRISE_PROFILE: Dict[str, Any] = {
    'profile_name': 'strict_local_enterprise',
    'ONLINE_MODE': False,
    'CONNECTED_RUNTIME_ALWAYS_ON': True,
    'CONNECTED_RUNTIME_SCOPE': 'local_private_only',
    'OFFLINE_MODE': True,
    'NO_EXTERNAL_API': True,
    'ALLOW_NETWORK': False,
    'ALLOW_PRIVATE_NETWORK': True,
    'NO_REAL_PAYMENT': True,
    'NO_REAL_SEND': True,
    'ZERO_COST_MODE': True,
    'ZERO_EXTERNAL_MODE': True,
    'LOCAL_MODEL_ONLY': True,
    'LOCAL_VECTOR_ONLY': True,
    'CONNECTOR_AUTH_PROMPT_POLICY': 'local_only_no_external',
    'REQUIRE_SIDE_EFFECT_PROOF': True,
    'PROOF_ONE_TIME_USE': True,
    'RUNTIME_SECRET_NOT_PACKAGED': True,
    'RUNTIME_SECRET_FAIL_CLOSED': True,
    'HIGH_RISK_REQUIRES_APPROVAL': True,
    'MEDIUM_RISK_REQUIRES_PROOF_ONLY': True,
    'SIDE_EFFECT_PROOF_FULL_FUSION': True,
    'ACTION_GUARD_MANDATORY': True,
    'OBSERVABILITY_EVENTS_ENABLED': True,
    'OBSERVABILITY_BACKEND': 'sqlite_wal',
    'SOURCE_RUNTIME_SEPARATION': True,
    'PROVIDER_FALLBACK_DOMAIN': 'local_only',
}

DEFAULT_OFFLINE_ENTERPRISE_PROFILE = dict(DEFAULT_STRICT_LOCAL_ENTERPRISE_PROFILE)
DEFAULT_ALWAYS_CONNECTED_ENTERPRISE_PROFILE = dict(DEFAULT_STRICT_LOCAL_ENTERPRISE_PROFILE, profile_name='strict_local_enterprise_compat_local_connected', OFFLINE_MODE=True, CONNECTED_RUNTIME_ALWAYS_ON=True, CONNECTED_RUNTIME_SCOPE='local_private_only')
DEFAULT_ENTERPRISE_PROFILE = dict(DEFAULT_STRICT_LOCAL_ENTERPRISE_PROFILE)


def project_root(root: Optional[str | Path] = None) -> Path:
    if root is not None:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[2]


def _flatten(base: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                out[sub_key] = sub_value
        else:
            out[key] = value
    return out


def _simple_parse(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current = data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = data.setdefault(line[1:-1].strip(), {})
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.lower() in ('true', 'false'):
            current[key] = value.lower() == 'true'
        else:
            current[key] = value
    return data


def _load_toml(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    if tomllib:
        return tomllib.loads(raw.decode('utf-8'))
    return _simple_parse(raw.decode('utf-8'))


def load_enterprise_profile(path: Optional[str | Path] = None, root: Optional[str | Path] = None) -> Dict[str, Any]:
    base = dict(DEFAULT_STRICT_LOCAL_ENTERPRISE_PROFILE)
    if path is None:
        path = project_root(root) / 'profiles' / 'strict_local_enterprise.toml'
    p = Path(path)
    if not p.exists():
        return base
    return _flatten(base, _load_toml(p))


def load_offline_profile(path: Optional[str | Path] = None, root: Optional[str | Path] = None) -> Dict[str, Any]:
    base = dict(DEFAULT_OFFLINE_ENTERPRISE_PROFILE)
    if path is None:
        path = project_root(root) / 'profiles' / 'offline_enterprise.toml'
    p = Path(path)
    if not p.exists():
        return base
    return _flatten(base, _load_toml(p))


def is_network_allowed(profile: Optional[Dict[str, Any]] = None) -> bool:
    profile = profile or DEFAULT_ENTERPRISE_PROFILE
    return bool(profile.get('ALLOW_NETWORK')) and not bool(profile.get('NO_EXTERNAL_API')) and not bool(profile.get('OFFLINE_MODE'))


def connector_prompt_policy(profile: Optional[Dict[str, Any]] = None) -> str:
    profile = profile or DEFAULT_ENTERPRISE_PROFILE
    return str(profile.get('CONNECTOR_AUTH_PROMPT_POLICY', 'local_only_no_external'))
