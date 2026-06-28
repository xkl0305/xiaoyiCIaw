
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Dict
ROOT = Path(__file__).resolve().parents[1]
def _load() -> Dict[str, Any]:
    p = ROOT / 'openclaw.json'
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except Exception: return {}
def _truthy(v: Any) -> bool:
    if isinstance(v, str): return v.lower() in {'1','true','yes','on'}
    return bool(v)
def resolve_runtime_mode() -> Dict[str, Any]:
    cfg = _load(); runtime = cfg.get('runtime') if isinstance(cfg.get('runtime'), dict) else {}
    no_external = _truthy(os.environ.get('NO_EXTERNAL_API')) or _truthy(runtime.get('NO_EXTERNAL_API')) or _truthy(cfg.get('NO_EXTERNAL_API')) or _truthy(cfg.get('ZERO_EXTERNAL_MODE'))
    offline = _truthy(os.environ.get('OFFLINE_MODE')) or _truthy(runtime.get('OFFLINE_MODE')) or _truthy(cfg.get('OFFLINE_MODE')) or no_external
    online = _truthy(runtime.get('ONLINE_MODE')) or _truthy(cfg.get('ONLINE_MODE'))
    allow_network = _truthy(runtime.get('ALLOW_NETWORK')) or _truthy(cfg.get('ALLOW_NETWORK'))
    if no_external:
        online = False; allow_network = False; offline = True
    return {'mode':'zero_external_local_first' if no_external else ('offline' if offline else 'online'), 'zero_external':no_external, 'offline':offline, 'online':online and not offline and not no_external, 'allow_network':allow_network and not no_external, 'allow_external_api':not no_external and allow_network, 'allow_cloud_tools': bool((cfg.get('externalAccessPolicy') or {}).get('allowCloudTools')) and not no_external, 'allow_mcp': bool((cfg.get('externalAccessPolicy') or {}).get('allowMcp')) and not no_external}
def is_zero_external() -> bool: return bool(resolve_runtime_mode()['zero_external'])
def network_allowed() -> bool: return bool(resolve_runtime_mode()['allow_network'])
def external_api_allowed() -> bool: return bool(resolve_runtime_mode()['allow_external_api'])
