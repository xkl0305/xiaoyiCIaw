#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from core.personal_os_enterprise.secret_workflow_guard import validate_secret_workflow
ROOT=Path(__file__).resolve().parents[2]
res=validate_secret_workflow(ROOT)
print(json.dumps({'overall':'passed' if res.get('ok') else 'failed', **res}, ensure_ascii=False, indent=2))
raise SystemExit(0 if res.get('ok') else 1)
