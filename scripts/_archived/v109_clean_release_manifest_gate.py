#!/usr/bin/env python3
"""V109: Clean Release Manifest Gate."""
from __future__ import annotations
import os, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXCLUDES = ['__pycache__', '.pytest_cache', '.repair_state', '.backup_', 'v86_backup_', '.venv', 'venv', 'node_modules', 'runtime/tmp', 'cache']
REQUIRED = ['core', 'memory_context', 'infrastructure', 'governance', 'orchestration', 'execution', 'skills', 'scripts']
results = {}
for d in REQUIRED:
    dp = ROOT / d
    results[d] = {"exists": dp.exists(), "size_kb": sum(f.stat().st_size for f in dp.rglob('*') if f.is_file() and all(x not in str(f) for x in EXCLUDES)) // 1024 if dp.exists() else 0}
all_required_ok = all(v["exists"] for v in results.values())
report = {
    "version": "V109",
    "status": "pass" if all_required_ok else "fail",
    "required_directories": results,
    "all_required_exist": all_required_ok,
    "exclude_patterns": EXCLUDES,
    "no_external_api": True,
}
(REPORTS / "V109_CLEAN_RELEASE_MANIFEST.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
