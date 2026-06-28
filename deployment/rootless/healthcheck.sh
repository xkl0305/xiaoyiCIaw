#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=${PYTHONPATH:-.}
python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_13_report_remaining_close.py >/dev/null
printf 'healthcheck=ok\n'
