from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "V111.52.5_SECRET_CLEAN_RUNTIME_PROOF_FINAL"
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bark-[A-Za-z0-9_-]{20,}\b"),
)
SKIP_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".zip", ".tar", ".gz", ".tgz"}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _secret_hits():
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() in SKIP_SUFFIXES or p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(pat.search(text) for pat in SECRET_PATTERNS):
            hits.append(str(p.relative_to(ROOT)))
    return hits


def main() -> int:
    checks = {}
    details = {}
    release = _load_json(ROOT / "release_manifest.json")
    openclaw = _load_json(ROOT / "openclaw.json")
    hook = _load_json(ROOT / ".openclaw/hooks/manifest.json")
    version = _load_json(ROOT / "xiaoyi_persona_visual/version.json")

    checks["release_version"] = release.get("version") == VERSION
    checks["hook_manifest_version"] = hook.get("version") == VERSION
    checks["enterprise_version"] = version.get("personal_os_enterprise_version") == VERSION
    checks["openclaw_enterprise_version"] = openclaw.get("personalOSEnterpriseVersion") == VERSION
    checks["zero_cost_no_payment"] = openclaw.get("ZERO_COST_MODE") is True and openclaw.get("NO_REAL_PAYMENT") is True

    forbidden_dirs = [
        ".openclaw/state", ".openclaw/hook_state", ".v98_state", ".v107_state", ".lazy_state", ".context_state", "logs", "generated-images"
    ]
    existing_forbidden = [p for p in forbidden_dirs if (ROOT / p).exists()]
    details["existing_forbidden_dirs"] = existing_forbidden
    checks["no_forbidden_runtime_dirs"] = not existing_forbidden

    jsonl = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.jsonl")]
    pycache = [str(p.relative_to(ROOT)) for p in ROOT.rglob("__pycache__")]
    pyc = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.pyc")]
    ds = [str(p.relative_to(ROOT)) for p in ROOT.rglob(".DS_Store")]
    overlay_payloads = [str(p.relative_to(ROOT)) for p in ROOT.glob("overlay_payload*")]
    secret_hits = _secret_hits()
    details.update({
        "jsonl": jsonl[:20], "pycache": pycache[:20], "pyc": pyc[:20], "ds_store": ds[:20],
        "overlay_payloads": overlay_payloads[:20], "secret_hits": secret_hits[:20]
    })
    checks["no_jsonl"] = not jsonl
    checks["no_pycache"] = not pycache
    checks["no_pyc"] = not pyc
    checks["no_ds_store"] = not ds
    checks["no_overlay_payload_residue"] = not overlay_payloads
    checks["no_secret_literals"] = not secret_hits

    try:
        from infrastructure.packaging.source_runtime_boundary import package_clean_check
        clean = package_clean_check(ROOT)
        details["source_runtime_boundary"] = clean
        checks["source_runtime_boundary_clean"] = clean.get("clean") is True
        checks["source_boundary_secret_scan"] = clean.get("secret_literal_count") == 0
    except Exception as exc:
        details["source_runtime_boundary_error"] = str(exc)
        checks["source_runtime_boundary_clean"] = False
        checks["source_boundary_secret_scan"] = False

    overall = all(checks.values())
    print(json.dumps({"overall": "passed" if overall else "failed", "version": VERSION, "checks": checks, "details": details}, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
