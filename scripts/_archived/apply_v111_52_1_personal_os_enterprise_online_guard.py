from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

VERSION = "V111.52.1_PERSONAL_OS_ENTERPRISE_ONLINE_GUARD"
SCRIPT = Path(__file__).resolve()
PACKAGE_ROOT = SCRIPT.parent.parent
PAYLOAD = PACKAGE_ROOT / "overlay_payload_v111_52_1"
PROJECT_ROOT = Path.cwd().resolve()

SKIP_COPY_NAMES = set()


def copy_payload() -> list[str]:
    copied: list[str] = []
    for src in PAYLOAD.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(PAYLOAD)
        if rel.name in SKIP_COPY_NAMES:
            continue
        dest = PROJECT_ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(str(rel).replace("\\", "/"))
    return copied


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        backup = path.with_suffix(path.suffix + f".broken_before_{VERSION}.bak")
        shutil.copy2(path, backup)
        return {}


def merge_openclaw() -> dict:
    path = PROJECT_ROOT / "openclaw.json"
    data = load_json(path)
    runtime = data.setdefault("runtime", {})
    runtime.update({
        "ONLINE_MODE": True,
        "CONNECTED_RUNTIME_ALWAYS_ON": True,
        "ALLOW_NETWORK": True,
        "OFFLINE_MODE": False,
        "NO_EXTERNAL_API": False,
    })
    # Keep top-level compatibility flags aligned without touching payment/send/device flags.
    data["ONLINE_MODE"] = True
    data["ALLOW_NETWORK"] = True
    data["OFFLINE_MODE"] = False
    data["NO_EXTERNAL_API"] = False

    poe = data.setdefault("personalOSEnterprise", {})
    poe.update({
        "enabled": True,
        "version": VERSION,
        "defaultProfile": "always_connected_enterprise",
        "standingConnectionMode": "always_connected",
        "connectorAuthPromptPolicy": "once_per_connector_or_config_change",
        "requireSideEffectProof": True,
        "proofOneTimeUse": True,
        "runtimeSecretPath": ".openclaw/state/personal_os_enterprise/secrets",
        "runtimeSecretPackaged": False,
        "sourceRuntimeSeparation": True,
    })

    pv = data.get("personaVisual")
    if isinstance(pv, dict):
        pv.setdefault("requiresPerImageOnlineApproval", False)
        pv.setdefault("onlineProviderAllowed", True)
        pv.setdefault("preventDuplicateImageSend", True)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"path": "openclaw.json", "personalOSEnterprise": poe, "runtime": runtime}


def write_report(copied: list[str], openclaw_result: dict) -> Path:
    report_dir = PROJECT_ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "version": VERSION,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "copied_count": len(copied),
        "copied_files": copied,
        "openclaw_merge": openclaw_result,
        "notes": [
            "default enterprise profile is always_connected_enterprise",
            "runtime secrets are not packaged and will be created under .openclaw/state only when needed",
            "V111.52.0 observability_event_bus SyntaxError is overwritten by fixed file",
        ],
    }
    out = report_dir / "v111_52_1_personal_os_enterprise_online_guard_apply_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def main() -> int:
    if not PAYLOAD.exists():
        raise SystemExit(f"payload not found: {PAYLOAD}")
    copied = copy_payload()
    openclaw_result = merge_openclaw()
    report = write_report(copied, openclaw_result)
    print(json.dumps({
        "overall": "applied",
        "version": VERSION,
        "copied_count": len(copied),
        "report": str(report.relative_to(PROJECT_ROOT)),
        "next_verify": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_1_personal_os_enterprise_online_guard.py",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
