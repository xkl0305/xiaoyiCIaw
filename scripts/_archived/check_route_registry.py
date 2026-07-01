
#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

class RouteRegistryChecker:
    def __init__(self, registry_path: str | Path = 'infrastructure/route_registry.json', allow_virtual: bool = True):
        self.registry_path = Path(registry_path)
        if not self.registry_path.is_absolute():
            self.registry_path = ROOT / self.registry_path
        self.allow_virtual = allow_virtual
        self.report = {}

    def load_routes(self) -> dict:
        if not self.registry_path.exists():
            return {'routes': {}}
        data = json.loads(self.registry_path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'routes' in data:
            return data
        if isinstance(data, list):
            return {'routes': {str(i): item for i, item in enumerate(data)}}
        return {'routes': {}}

    def check_all(self) -> bool:
        data = self.load_routes(); broken=[]; virtual=[]; checked=0
        for route_id, spec in (data.get('routes') or {}).items():
            handler_type = spec.get('handler_type') or spec.get('type')
            handler = spec.get('handler') or spec.get('target') or spec.get('callable') or ''
            if handler_type == 'virtual_device_capability':
                virtual.append({'route_id': route_id, 'handler': handler, 'handler_type': handler_type})
                continue
            if not handler or '.' not in handler:
                broken.append({'route_id': route_id, 'handler': handler, 'reason': 'empty_or_invalid_handler'})
                continue
            mod_name, _, attr = handler.rpartition('.')
            try:
                mod = importlib.import_module(mod_name)
                if not hasattr(mod, attr):
                    broken.append({'route_id': route_id, 'handler': handler, 'reason': 'missing_attr'})
                else:
                    checked += 1
            except Exception as e:
                broken.append({'route_id': route_id, 'handler': handler, 'reason': type(e).__name__, 'error': str(e)})
        ok = not broken and (self.allow_virtual or not virtual)
        self.report = {
            'status': 'ok' if ok else 'fail',
            'checked_non_virtual_routes': checked,
            'broken_non_virtual_routes': broken,
            'virtual_device_routes': virtual,
            'virtual_device_count': len(virtual),
        }
        return ok

def load_routes() -> dict:
    path = ROOT / 'infrastructure' / 'route_registry.json'
    if not path.exists(): return {'routes': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'routes' in data: return data
    if isinstance(data, list): return {'routes': {str(i): item for i, item in enumerate(data)}}
    return {'routes': {}}
def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument('--allow-virtual', action='store_true'); ap.add_argument('--json', action='store_true'); args = ap.parse_args()
    data = load_routes(); broken=[]; virtual=[]; checked=0
    for route_id, spec in (data.get('routes') or {}).items():
        handler_type = spec.get('handler_type') or spec.get('type')
        handler = spec.get('handler') or spec.get('target') or spec.get('callable') or ''
        if handler_type == 'virtual_device_capability': virtual.append({'route_id':route_id,'handler':handler,'handler_type':handler_type}); continue
        if not handler or '.' not in handler: broken.append({'route_id':route_id,'handler':handler,'reason':'empty_or_invalid_handler'}); continue
        mod_name, _, attr = handler.rpartition('.')
        try:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, attr): broken.append({'route_id':route_id,'handler':handler,'reason':'missing_attr'})
            else: checked += 1
        except Exception as e: broken.append({'route_id':route_id,'handler':handler,'reason':type(e).__name__,'error':str(e)})
    report = {'status':'ok' if not broken and (args.allow_virtual or not virtual) else 'fail','checked_non_virtual_routes':checked,'broken_non_virtual_routes':broken,'virtual_device_routes':virtual,'virtual_device_count':len(virtual),'note':'Use --allow-virtual when virtual routes are covered by DevicePhysicalBindingRegistry.'}
    if args.json: print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('Route registry audit:', report['status']); print('checked_non_virtual_routes:', checked); print('broken_non_virtual_routes:', len(broken)); print('virtual_device_routes:', len(virtual))
        for item in broken: print('BROKEN', item)
        if virtual and not args.allow_virtual: print('Virtual device routes require DevicePhysicalBindingRegistry or --allow-virtual')
    return 0 if report['status']=='ok' else 1
if __name__ == '__main__': raise SystemExit(main())
