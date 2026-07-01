#!/usr/bin/env python3
from __future__ import annotations
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VERSION = "V111.52_NON_PERSONA_FOUNDATION"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def main() -> None:
    cfg = _load(ROOT / "openclaw.json", {})
    connected = cfg.get("connectedRuntime", {}) if isinstance(cfg.get("connectedRuntime"), dict) else {}
    checks = {}
    try:
        importlib.import_module("application")
        importlib.import_module("application.task_service.scheduler")
        checks["application_facade"] = True
    except Exception as exc:
        checks["application_facade"] = str(exc)
    try:
        importlib.import_module("skills.registry")
        importlib.import_module("skills.runtime.skill_version_selector")
        importlib.import_module("skills.seedream_image_gen.scripts.generate_seedream")
        checks["no_skills_import_facade"] = True
    except Exception as exc:
        checks["no_skills_import_facade"] = str(exc)
    try:
        from core.skill_asset_registry import SkillScanner
        checks["logical_skill_scan_count_ge_100"] = len(SkillScanner().scan_all()) >= 100
    except Exception as exc:
        checks["logical_skill_scan_count_ge_100"] = str(exc)
    try:
        from scripts.check_route_registry import RouteRegistryChecker
        checks["route_registry_checker_class"] = RouteRegistryChecker("infrastructure/route_registry.json").check_all()
    except Exception as exc:
        checks["route_registry_checker_class"] = str(exc)
    try:
        from core.llm.provider_guard import scan
        checks["provider_guard_clean"] = scan() == []
    except Exception as exc:
        checks["provider_guard_clean"] = str(exc)

    checks.update({
        "physical_skills_dir_absent": not (ROOT / "skills").exists(),
        "skills_file_facade_exists": (ROOT / "skills.py").exists(),
        "workflow_registry_true_source_exists": (ROOT / "orchestration" / "workflows" / "WORKFLOW_REGISTRY.json").exists(),
        "message_server_exists": (ROOT / "scripts" / "message_server.py").exists(),
        "crontab_example_exists": (ROOT / "config" / "crontab.example").exists(),
        "systemd_example_exists": (ROOT / "config" / "systemd.example").exists(),
        "online_mode": bool(cfg.get("ONLINE_MODE")) and not bool(cfg.get("OFFLINE_MODE")),
        "zero_external_disabled": not bool(cfg.get("ZERO_EXTERNAL_MODE")) and not bool(cfg.get("NO_EXTERNAL_API")),
        "connected_always_on": bool(connected.get("alwaysConnected")),
        "no_per_action_online_authorization": bool(connected.get("noPerActionOnlineAuthorization")),
        "xiaoyi_capabilities_always_connected": bool(connected.get("xiaoyiCapabilitiesAlwaysConnected")),
        "end_side_capabilities_always_connected": bool(connected.get("endSideCapabilitiesAlwaysConnected")),
    })
    bad = [k for k, v in checks.items() if v is not True]
    result = {"status": "ok" if not bad else "fail", "version": VERSION, "checks": checks, "bad": bad}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
