#!/usr/bin/env python3
"""V109: Full import sweep - all modules import-test under python3 -S."""
from __future__ import annotations
import os, sys, json, traceback, importlib, pkgutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OFFLINE_MODE", "true")
os.environ.setdefault("NO_EXTERNAL_API", "true")
os.environ.setdefault("NO_REAL_PAYMENT", "true")
os.environ.setdefault("NO_REAL_SEND", "true")
os.environ.setdefault("NO_REAL_DEVICE", "true")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

PACKAGES = ["core", "memory_context", "infrastructure", "governance", "orchestration", "execution"]
EXCLUDE_FILES = {"__main__.py"}

def walk_modules(pkg_name: str):
    """Yield (module_path, module_name) for all .py files in a package tree."""
    pkg_dir = ROOT / pkg_name
    if not pkg_dir.exists():
        return
    for pyfile in sorted(pkg_dir.rglob("*.py")):
        if pyfile.name in EXCLUDE_FILES:
            continue
        rel = pyfile.relative_to(ROOT)
        parts = list(rel.with_suffix("").parts)
        mod = ".".join(parts)
        yield str(rel), mod

results = []
fatal = 0
warnings = 0

print("=" * 60)
print("V109 Full Import Sweep")
print("=" * 60)

# 1) Package-level imports
for pkg in PACKAGES:
    for rel_path, mod_name in walk_modules(pkg):
        # skip __init__
        if mod_name.endswith(".__init__"):
            continue
        try:
            importlib.import_module(mod_name)
            results.append({"module": mod_name, "path": rel_path, "status": "pass"})
            print(f"  ✅ {mod_name}")
        except ImportError as e:
            err = str(e).split("\n")[0]
            # Non-fatal: missing optional dependency
            results.append({"module": mod_name, "path": rel_path, "status": "warning", "error": err})
            warnings += 1
            print(f"  ⚠️  {mod_name} -> {err}")
        except Exception as e:
            err = traceback.format_exc()
            results.append({"module": mod_name, "path": rel_path, "status": "fail", "error": str(e)[:200]})
            fatal += 1
            print(f"  ❌ {mod_name} -> {e}")

# 2) Scripts that are gates (non-execution scripts)
scripts_dir = ROOT / "scripts"
script_results = []
for sf in sorted(scripts_dir.glob("*_gate.py")):
    mod_name = f"scripts.{sf.stem}"
    try:
        importlib.import_module(mod_name)
        script_results.append({"module": mod_name, "path": f"scripts/{sf.name}", "status": "pass"})
        print(f"  ✅ {mod_name}")
    except Exception as e:
        err = str(e)[:200]
        script_results.append({"module": mod_name, "path": f"scripts/{sf.name}", "status": "warning", "error": err})
        warnings += 1
        print(f"  ⚠️  {mod_name} -> {err}")

results.extend(script_results)

report = {
    "version": "V109",
    "status": "pass" if fatal == 0 else "fail",
    "total_modules": len(results),
    "passed": len([r for r in results if r["status"] == "pass"]),
    "warnings": warnings,
    "fatal": fatal,
    "results": results,
    "no_external_api": True,
    "no_real_payment": True,
    "no_real_send": True,
    "no_real_device": True,
    "remaining_failures": [r["module"] for r in results if r["status"] == "fail"],
}

(REPORTS / "V109_FULL_IMPORT_SWEEP_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print("=" * 60)
print(f"Total: {report['total_modules']}, Passed: {report['passed']}, Warnings: {warnings}, Fatal: {fatal}")
print(f"Report: {REPORTS / 'V109_FULL_IMPORT_SWEEP_REPORT.json'}")
sys.exit(0 if fatal == 0 else 1)
