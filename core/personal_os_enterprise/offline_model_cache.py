from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_MODEL_CACHE_ROOT = '/srv/model-mirror'


def project_root(root: Optional[str | Path] = None) -> Path:
    return Path(root).resolve() if root is not None else Path(__file__).resolve().parents[2]


def load_prefetch_manifest(root: Optional[str | Path] = None) -> Dict[str, Any]:
    path = project_root(root) / 'profiles' / 'model_prefetch_manifest.json'
    if not path.exists():
        return {'models': [], 'offline_only': True}
    return json.loads(path.read_text(encoding='utf-8'))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check_model_cache(root: Optional[str | Path] = None) -> Dict[str, Any]:
    manifest = load_prefetch_manifest(root)
    models = manifest.get('models') or []
    results = []
    for item in models:
        local_dir = Path(str(item.get('local_dir') or ''))
        exists = local_dir.exists() if str(local_dir) else False
        results.append({
            'id': item.get('id'), 'capability': item.get('capability'),
            'local_dir': str(local_dir), 'exists': exists,
            'required': bool(item.get('required')), 'ready': exists or not item.get('required'),
        })
    missing_required = [r for r in results if r.get('required') and not r.get('exists')]
    return {'ok': not missing_required, 'offline_only': True, 'network_egress_attempted': False, 'missing_required': missing_required, 'results': results}
