from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "V111.52.4_SIDE_EFFECT_FUSION_CLEAN_REPAIR_FINAL"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    checks = {}
    details = {}
    release = _load_json(ROOT / "release_manifest.json")
    openclaw = _load_json(ROOT / "openclaw.json")
    hook = _load_json(ROOT / ".openclaw/hooks/manifest.json")

    checks["release_version"] = release.get("version") in {VERSION, "V111.52.5_SECRET_CLEAN_RUNTIME_PROOF_FINAL"}
    checks["release_seedream_direct_not_physical"] = release.get("seedream_provider_direct", {}).get("physical_skill_required") is False
    checks["release_package_mode"] = release.get("package_mode") == "with_physical_skills"
    checks["hook_manifest_version"] = hook.get("version") in {VERSION, "V111.52.5_SECRET_CLEAN_RUNTIME_PROOF_FINAL"}
    checks["openclaw_online"] = openclaw.get("ONLINE_MODE") is True and openclaw.get("OFFLINE_MODE") is False
    checks["openclaw_zero_cost_no_payment"] = openclaw.get("ZERO_COST_MODE") is True and openclaw.get("NO_REAL_PAYMENT") is True
    checks["always_connected"] = openclaw.get("CONNECTED_RUNTIME_ALWAYS_ON") is True and openclaw.get("connectedRuntime", {}).get("alwaysConnected") is True

    forbidden_dirs = [
        ".openclaw/state", ".openclaw/hook_state", ".v98_state", ".v107_state", ".lazy_state", ".context_state", "logs", "generated-images"
    ]
    existing_forbidden = [p for p in forbidden_dirs if (ROOT / p).exists()]
    details["existing_forbidden_dirs"] = existing_forbidden
    checks["no_forbidden_runtime_dirs"] = not existing_forbidden

    overlay_payloads = [str(p.relative_to(ROOT)) for p in ROOT.glob("overlay_payload*")]
    details["overlay_payloads"] = overlay_payloads
    checks["no_overlay_payload_residue"] = not overlay_payloads

    jsonl = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.jsonl")]
    pycache = [str(p.relative_to(ROOT)) for p in ROOT.rglob("__pycache__")]
    pyc = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.pyc")]
    ds = [str(p.relative_to(ROOT)) for p in ROOT.rglob(".DS_Store")]
    details.update({"jsonl": jsonl[:20], "pycache": pycache[:20], "pyc": pyc[:20], "ds_store": ds[:20]})
    checks["no_jsonl"] = not jsonl
    checks["no_pycache"] = not pycache
    checks["no_pyc"] = not pyc
    checks["no_ds_store"] = not ds

    try:
        from infrastructure.packaging.source_runtime_boundary import package_clean_check
        clean = package_clean_check(ROOT)
        details["source_runtime_boundary"] = clean
        checks["source_runtime_boundary_clean"] = clean.get("clean") is True
    except Exception as exc:
        details["source_runtime_boundary_error"] = str(exc)
        checks["source_runtime_boundary_clean"] = False

    overall = all(checks.values())
    print(json.dumps({"overall": "passed" if overall else "failed", "version": VERSION, "checks": checks, "details": details}, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
