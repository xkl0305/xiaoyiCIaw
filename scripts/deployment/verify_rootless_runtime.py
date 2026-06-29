#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from core.personal_os_enterprise.rootless_deploy_smoke import rootless_deploy_plan
ROOT=Path(__file__).resolve().parents[2]
res=rootless_deploy_plan(ROOT)
print(json.dumps({'overall':'passed' if res.get('ok') else 'failed', **res}, ensure_ascii=False, indent=2))
raise SystemExit(0 if res.get('ok') else 1)
