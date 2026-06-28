from __future__ import annotations

from pathlib import Path
from typing import Dict, List

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"
REQUIRED_SECRET_WORKFLOW_FILES = [
    '.env.example',
    '.sops.yaml',
    'secrets/runtime.enc.yaml',
    'deploy/load_secrets.sh',
    'scripts/security/run_gitleaks_scan.sh',
]
FORBIDDEN_SECRET_PATH_PARTS = [
    '.openclaw/state',
    '.openclaw/hook_state',
    'runtime.secret',
    'mainchain_secret',
]


def validate_secret_workflow(root: str | Path) -> Dict[str, object]:
    root = Path(root)
    missing = [p for p in REQUIRED_SECRET_WORKFLOW_FILES if not (root / p).exists()]
    forbidden = []
    for p in root.rglob('*') if root.exists() else []:
        rel = p.relative_to(root).as_posix()
        if any(part in rel for part in FORBIDDEN_SECRET_PATH_PARTS):
            forbidden.append(rel)
    return {
        'ok': not missing and not forbidden,
        'version': VERSION,
        'missing': missing,
        'forbidden_secret_runtime_paths': forbidden[:50],
        'env_only_runtime_secret': True,
        'fallback_secret_allowed': False,
    }
