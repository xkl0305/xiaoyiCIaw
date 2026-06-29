#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from core.personal_os_enterprise.rootless_runtime_manager import detect_rootless_runtime, validate_rootless_layout
import json
print(json.dumps({'runtime': detect_rootless_runtime(), 'layout': validate_rootless_layout('.')}, ensure_ascii=False, indent=2))
PY
