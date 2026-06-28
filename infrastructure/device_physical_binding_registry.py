
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, Optional
ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / 'infrastructure' / 'device_physical_binding_registry.json'
def load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists(): return {'version':'V111.35','routes':{}}
    return json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
def save_registry(data: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True); REGISTRY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def get_binding(route_id: str) -> Optional[Dict[str, Any]]: return (load_registry().get('routes') or {}).get(route_id)
def is_real_execution_supported(route_id: str) -> bool:
    b = get_binding(route_id) or {}; return bool(b.get('real_execution_supported') and b.get('physical_adapter'))
def record_receipt(route_id: str, receipt: Dict[str, Any]) -> Dict[str, Any]:
    data = load_registry(); routes=data.setdefault('routes',{}); b=routes.setdefault(route_id, {'route_id':route_id}); b['last_real_receipt']={'ts':time.time(), **receipt}; save_registry(data); return b
def dry_run(route_id: str, **kwargs: Any) -> Dict[str, Any]:
    b=get_binding(route_id) or {'route_id':route_id}; return {'status':'dry_run_only','route_id':route_id,'real_execution_supported':bool(b.get('real_execution_supported')),'physical_adapter':b.get('physical_adapter'),'reason':'zero_external_mode_or_no_physical_adapter','kwargs':kwargs}
