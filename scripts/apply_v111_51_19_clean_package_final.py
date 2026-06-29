#!/usr/bin/env python3
"""V111.51.19 clean package final apply script.

Only removes runtime/cache artifacts and updates package/version markers.
Does not change persona visual mainchain, provider guard, wardrobe, focus resolver,
or physical skills source files.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "V111.51.19_CLEAN_PACKAGE_FINAL"

RUNTIME_DIRS = [
    "__pycache__", ".pytest_cache", "cache", "logs", "generated-images",
    ".openclaw/hook_state", ".v98_state", ".v107_state", ".lazy_state", ".context_state",
]
RUNTIME_FILES = [
    ".persona_visual/visual_request_ledger.jsonl",
    ".persona_visual/runtime_wardrobe_state.json",
]
RUNTIME_GLOBS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
    "**/.pytest_cache",
    "**/*.jsonl",
]
PRESERVE_FILES = {
    str(Path(".persona_visual/visual_config.json")),
}

EXCLUDE_LINES = [
    "# V111.51.19 clean package final excludes",
    "*.pyc",
    "*.pyo",
    "__pycache__/",
    ".pytest_cache/",
    "*.jsonl",
    "cache/",
    "logs/",
    "generated-images/",
    ".openclaw/hook_state/",
    ".persona_visual/generated/",
    ".persona_visual/*.jsonl",
    ".persona_visual/runtime_wardrobe_state.json",
    ".v98_state/",
    ".v107_state/",
    ".lazy_state/",
    ".context_state/",
    "V*_overlay/",
    "V*_overlay.zip",
    "V*_overlay.tar.gz",
    "*_overlay/",
    "*_overlay.zip",
    "*_overlay.tar.gz",
]


def remove_path(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def cleanup_runtime() -> list[str]:
    removed: list[str] = []

    # Targeted runtime dirs/files first.
    for rel in RUNTIME_DIRS:
        path = ROOT / rel
        if remove_path(path):
            removed.append(rel)

    for rel in RUNTIME_FILES:
        path = ROOT / rel
        if remove_path(path):
            removed.append(rel)

    # Recursive residue cleanup.
    for pattern in RUNTIME_GLOBS:
        for path in list(ROOT.glob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            if rel in PRESERVE_FILES:
                continue
            if any(part in {".git", "node_modules", ".venv", "venv"} for part in path.parts):
                continue
            if remove_path(path):
                removed.append(rel)

    # Keep the config directory itself if it contains visual_config, otherwise no-op.
    (ROOT / ".persona_visual").mkdir(exist_ok=True)
    return sorted(set(removed))


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_versions() -> None:
    # release_manifest.json
    p = ROOT / "release_manifest.json"
    obj = load_json(p)
    obj["version"] = VERSION
    obj["persona_visual_version"] = VERSION
    obj["release_name"] = "pigeonking_persona_visual_clean_package_final"
    obj["clean_package_final"] = True
    obj["runtime_artifacts_excluded"] = True
    obj["provider_guard_actual_payload_final"] = True
    obj["mainchain_unchanged_from"] = "V111.51.18_PROVIDER_GUARD_ACTUAL_PAYLOAD_FINAL"
    dump_json(p, obj)

    # xiaoyi_persona_visual/version.json
    p = ROOT / "xiaoyi_persona_visual/version.json"
    obj = load_json(p)
    obj["version"] = VERSION
    obj["description"] = "鸽子王人格视觉清洁交付终版：在 V111.51.18 provider guard 终版基础上，仅清理缓存、运行态和打包残留，不改主链。"
    obj["clean_package_final"] = True
    obj["provider_guard_actual_payload_final"] = True
    dump_json(p, obj)

    # .openclaw/hooks/manifest.json
    p = ROOT / ".openclaw/hooks/manifest.json"
    obj = load_json(p)
    obj["version"] = VERSION
    obj["persona_visual_version"] = VERSION
    obj["clean_package_final"] = True
    obj["provider_guard_actual_payload_final"] = True
    dump_json(p, obj)

    # openclaw.json
    p = ROOT / "openclaw.json"
    obj = load_json(p)
    pv = obj.setdefault("personaVisual", {})
    pv["version"] = VERSION
    pv["cleanPackageFinal"] = True
    pv["runtimeArtifactsExcluded"] = True
    pv["providerGuardActualPayloadFinal"] = True
    obj["packageMode"] = "with_skills_clean_package_final"
    dump_json(p, obj)


def update_registry_versions() -> None:
    old_versions = (
        "V111.51.18_PROVIDER_GUARD_ACTUAL_PAYLOAD_FINAL",
        "V111.51.17_PROVIDER_GUARD_CANONICAL_MAINCHAIN",
    )
    rels = [
        "infrastructure/inventory/module_fusion_log.json",
        "infrastructure/inventory/module_registry.json",
        "infrastructure/inventory/fusion_index.json",
        "infrastructure/COMPONENT_REGISTRY.json",
        "infrastructure/SIX_LAYER_REGISTRY.json",
        "orchestration/INTEGRATION_REGISTRY.json",
    ]
    for rel in rels:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for old in old_versions:
            text = text.replace(old, VERSION)
        path.write_text(text, encoding="utf-8")


def update_gitignore() -> None:
    p = ROOT / ".gitignore"
    existing = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    seen = set(existing)
    out = list(existing)
    for line in EXCLUDE_LINES:
        if line not in seen:
            out.append(line)
            seen.add(line)
    p.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def write_exclude_file() -> None:
    p = ROOT / "scripts/CLEAN_PACKAGE_EXCLUDES_V111_51_19.txt"
    p.write_text("\n".join(EXCLUDE_LINES) + "\n", encoding="utf-8")


def main() -> int:
    removed = cleanup_runtime()
    update_versions()
    update_registry_versions()
    update_gitignore()
    write_exclude_file()
    print(f"[OK] V111.51.19 clean package final applied at: {ROOT}")
    print(f"[OK] removed runtime/cache artifacts: {len(removed)}")
    for item in removed[:80]:
        print(f"  - {item}")
    if len(removed) > 80:
        print(f"  ... {len(removed) - 80} more")
    print(f"[OK] version={VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
