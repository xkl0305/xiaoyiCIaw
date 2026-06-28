from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional


def deployment_files(root: Optional[str | Path] = None) -> Dict[str, str]:
    base = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
    return {
        'compose': str(base / 'deployment' / 'rootless' / 'compose.local.yaml'),
        'systemd_user_service': str(base / 'deployment' / 'rootless' / 'systemd-user' / 'xiaoyi-local.service'),
        'mode': 'rootless_local_only',
        'bind': '127.0.0.1',
    }
