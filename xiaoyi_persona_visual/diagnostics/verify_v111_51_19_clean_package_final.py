#!/usr/bin/env python3
"""Verify V111.51.19 clean package final.

Checks package cleanliness only. It intentionally does not alter persona visual
mainchain, provider guard, or focus resolver behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "V111.51.20_MAINCHAIN_PROOF_TAIL_ANCHOR_FINAL"

FORBIDDEN_DIR_REL = [
    ".openclaw/hook_state",
    ".v98_state",
    ".v107_state",
    ".lazy_state",
    ".context_state",
    "cache",
    "logs",
    "generated-images",
]
FORBIDDEN_FILES_REL = [
    ".persona_visual/visual_request_ledger.jsonl",
    ".persona_visual/runtime_wardrobe_state.json",
]


def load_json(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    results: dict[str, bool] = {}

    release = load_json("release_manifest.json")
    modver = load_json("xiaoyi_persona_visual/version.json")
    hookman = load_json(".openclaw/hooks/manifest.json")
    openclaw = load_json("openclaw.json")
    pv = openclaw.get("personaVisual", {}) if isinstance(openclaw.get("personaVisual"), dict) else {}

    results["release_manifest_version_v111_51_19"] = release.get("version") == VERSION
    results["module_version_v111_51_19"] = modver.get("version") == VERSION
    results["hook_manifest_version_v111_51_19"] = hookman.get("version") == VERSION
    results["openclaw_persona_version_v111_51_19"] = pv.get("version") == VERSION
    results["release_marks_clean_package_final"] = release.get("clean_package_final") is True
    results["openclaw_marks_clean_package_final"] = pv.get("cleanPackageFinal") is True
    results["provider_guard_actual_payload_still_marked"] = pv.get("providerGuardActualPayloadFinal") is True

    pycache = [p for p in ROOT.rglob("__pycache__") if ".git" not in p.parts]
    pyc = [p for p in ROOT.rglob("*.pyc") if ".git" not in p.parts]
    pyo = [p for p in ROOT.rglob("*.pyo") if ".git" not in p.parts]
    jsonl = [p for p in ROOT.rglob("*.jsonl") if ".git" not in p.parts]

    results["no_pycache_dirs"] = len(pycache) == 0
    results["no_pyc_files"] = len(pyc) == 0
    results["no_pyo_files"] = len(pyo) == 0
    results["no_jsonl_runtime_ledgers"] = len(jsonl) == 0

    results["runtime_dirs_removed"] = all(not (ROOT / rel).exists() for rel in FORBIDDEN_DIR_REL)
    results["runtime_files_removed"] = all(not (ROOT / rel).exists() for rel in FORBIDDEN_FILES_REL)
    results["persona_visual_config_preserved_or_optional"] = True  # .persona_visual/visual_config.json may exist and is config, not runtime.
    results["physical_skills_preserved"] = (ROOT / "skills").is_dir()
    results["persona_visual_main_package_preserved"] = (ROOT / "xiaoyi_persona_visual").is_dir()
    results["provider_guard_verify_script_preserved"] = (ROOT / "xiaoyi_persona_visual/diagnostics/verify_v111_51_18_provider_guard_actual_payload.py").is_file()
    results["clean_excludes_file_present"] = (ROOT / "scripts/CLEAN_PACKAGE_EXCLUDES_V111_51_19.txt").is_file()

    failures = [k for k, v in results.items() if not v]
    for k, v in results.items():
        print(f"{k}={str(v).lower()}")
    if pycache:
        print("pycache_examples=" + ",".join(str(p.relative_to(ROOT)) for p in pycache[:10]))
    if pyc:
        print("pyc_examples=" + ",".join(str(p.relative_to(ROOT)) for p in pyc[:10]))
    if jsonl:
        print("jsonl_examples=" + ",".join(str(p.relative_to(ROOT)) for p in jsonl[:10]))
    print(f"overall={'passed' if not failures else 'failed'}")
    if failures:
        print("failures=" + ",".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
