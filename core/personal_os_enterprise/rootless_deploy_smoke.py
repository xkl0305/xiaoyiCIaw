from __future__ import annotations

from pathlib import Path
from typing import Dict

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"


def rootless_deploy_plan(root: str | Path) -> Dict[str, object]:
    root = Path(root)
    required = [
        'deployment/rootless/compose.local.yaml',
        'deployment/rootless/systemd-user/xiaoyi-local.service',
        'deployment/rootless/healthcheck.sh',
        'deployment/rootless/README.md',
    ]
    missing = [p for p in required if not (root / p).exists()]
    return {
        'ok': not missing,
        'version': VERSION,
        'missing': missing,
        'rootless_required': True,
        'model_mount_read_only': True,
        'data_mount_separate': True,
        'loopback_only': True,
        'secret_injection': 'env_or_tmpfs_only',
    }
