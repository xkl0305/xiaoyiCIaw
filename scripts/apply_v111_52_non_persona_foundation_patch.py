#!/usr/bin/env python3
from __future__ import annotations
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "V111.52_NON_PERSONA_FOUNDATION"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_online_policy() -> None:
    cfg = _load_json(ROOT / "openclaw.json", {})
    runtime = cfg.setdefault("runtime", {})
    runtime.update({
        "OFFLINE_MODE": False,
        "NO_EXTERNAL_API": False,
        "ONLINE_MODE": True,
        "CONNECTED_RUNTIME_ALWAYS_ON": True,
        "ALLOW_NETWORK": True,
    })
    cfg.update({
        "OFFLINE_MODE": False,
        "NO_EXTERNAL_API": False,
        "ONLINE_MODE": True,
        "CONNECTED_RUNTIME_ALWAYS_ON": True,
        "ALLOW_NETWORK": True,
        "ZERO_EXTERNAL_MODE": False,
        "runtimeMode": "online_connected",
    })
    connected = cfg.setdefault("connectedRuntime", {})
    connected.update({
        "enabled": True,
        "alwaysConnected": True,
        "defaultMode": "always_online",
        "noPerActionOnlineAuthorization": True,
        "xiaoyiCapabilitiesAlwaysConnected": True,
        "endSideCapabilitiesAlwaysConnected": True,
        "deviceBridgeAlwaysConnected": True,
        "allowExternalProvidersWithStandingConsent": True,
        "offlineModeRemoved": True,
        "legacyOfflineFiles": "compatibility_shims_only_non_blocking",
    })
    external = cfg.setdefault("externalAccessPolicy", {})
    external.update({
        "mode": "online_connected_with_standing_consent",
        "allowExternalApi": True,
        "allowMcp": True,
        "allowCloudTools": True,
        "defaultExecutionMode": "online_connected_guarded",
        "allowNetwork": True,
        "allowPaidCompute": False,
        "failClosed": True,
    })
    runtime_policy = cfg.setdefault("runtimePolicy", {})
    runtime_policy.update({
        "network": "enabled",
        "sideEffects": "preview_approve_confirm",
        "defaultForUnboundDevice": "connected_probe_then_guarded_execution",
        "mode": "always_online_connected",
        "paidCompute": "disabled_without_explicit_flag",
        "toolBroker": "connected_guarded",
    })
    cfg["nonPersonaFoundationPatch"] = {
        "version": VERSION,
        "noPhysicalSkillsDirRequired": True,
        "skillsImportFacade": "infrastructure.no_skills_compat.install",
        "applicationRootFacade": "application -> execution.application",
        "mainEntrypointsRestored": ["scripts/message_server.py"],
        "automationExamplesRestored": ["config/crontab.example", "config/systemd.example"],
    }
    _save_json(ROOT / "openclaw.json", cfg)


def update_release_manifest() -> None:
    p = ROOT / "release_manifest.json"
    manifest = _load_json(p, {})
    manifest["non_persona_foundation_patch"] = {
        "version": VERSION,
        "scope": "non_persona",
        "does_not_change_persona_visual_rules": True,
        "fixes": [
            "no_skills_import_facade_without_physical_skills_dir",
            "application_root_facade",
            "message_server_entrypoint",
            "automation_config_examples",
            "online_connected_policy_normalization",
        ],
    }
    _save_json(p, manifest)


def clean_runtime_garbage() -> dict:
    removed = {"pyc_files": 0, "pycache_dirs": 0, "pytest_cache_dirs": 0}
    for p in ROOT.rglob("*.pyc"):
        try:
            p.unlink(); removed["pyc_files"] += 1
        except Exception:
            pass
    for p in sorted(ROOT.rglob("__pycache__"), key=lambda x: len(x.parts), reverse=True):
        try:
            shutil.rmtree(p); removed["pycache_dirs"] += 1
        except Exception:
            pass
    for p in ROOT.rglob(".pytest_cache"):
        try:
            shutil.rmtree(p); removed["pytest_cache_dirs"] += 1
        except Exception:
            pass
    return removed


def main() -> None:
    normalize_online_policy()
    update_release_manifest()
    cleaned = clean_runtime_garbage()
    result = {"status": "ok", "version": VERSION, "cleaned": cleaned}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
