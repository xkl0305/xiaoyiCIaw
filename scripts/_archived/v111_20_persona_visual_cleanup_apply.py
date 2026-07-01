#!/usr/bin/env python3
"""Apply V111.20 persona visual cleanup.

Actions:
- bind assets/persona/seed_avatar.jpg as the direct persona visual seed
- normalize openclaw.json and .persona_visual/visual_config.json
- remove unsafe long appearance prose from active mood mapping
- move superseded persona-visual gate scripts out of active scripts/ into archive
- clear pycache for persona visual runtime paths
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUPERSEDED_SCRIPT_PREFIXES = [
    "v111_persona_visualization_gate.py",
    "v111_apply_persona_visualization.py",
    "v111_1_persona_visual_seed_avatar_fix_apply.py",
    "v111_1_persona_visual_seed_avatar_fix_gate.py",
    "v111_2_persona_visual_external_approval_gate.py",
    "v111_2_3_persona_visual_approval_prediction_bundle_apply.py",
    "v111_2_3_persona_visual_approval_prediction_bundle_gate.py",
    "v111_3_persona_visual_prediction_gate.py",
    "v111_4_persona_visual_auto_consent_gate.py",
    "v111_13_persona_visual_auto_generation_gate.py",
    "v111_16_persona_visual_mood_trigger_gate.py",
    "v111_17_persona_visual_mood_trigger_gate.py",
    "v111_18_persona_visual_borrowed_gate.py",
    "v111_19_persona_visual_scene_consistency_gate.py",
]

ACTIVE_KEEP = {
    "xiaoyi_visual_entry.py",
    "v111_20_persona_visual_cleanup_apply.py",
    "v111_20_persona_visual_cleanup_gate.py",
}


def _copy_backup(path: Path, backup_root: Path) -> str | None:
    if not path.exists():
        return None
    rel = path.relative_to(ROOT)
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copy2(path, dst)
    elif path.is_dir():
        shutil.copytree(path, dst, dirs_exist_ok=True)
    return rel.as_posix()


def _remove_pycache(paths: Iterable[Path]) -> list[str]:
    removed: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for p in base.rglob("__pycache__"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                removed.append(p.relative_to(ROOT).as_posix())
        for p in base.rglob("*.pyc"):
            try:
                p.unlink()
                removed.append(p.relative_to(ROOT).as_posix())
            except FileNotFoundError:
                pass
    return removed


def _archive_superseded_scripts(backup_root: Path) -> list[str]:
    archived: list[str] = []
    archive_dir = ROOT / "archive" / "persona_visual_superseded_scripts" / backup_root.name
    archive_dir.mkdir(parents=True, exist_ok=True)
    for name in SUPERSEDED_SCRIPT_PREFIXES:
        src = ROOT / "scripts" / name
        if src.exists() and src.name not in ACTIVE_KEEP:
            _copy_backup(src, backup_root)
            dst = archive_dir / src.name
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            archived.append(src.relative_to(ROOT).as_posix())
    return archived


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_mood_mapping() -> None:
    src = ROOT / "memory_context" / "persona_runtime" / "visual_mood_mappings.json"
    dst = ROOT / "memory_context" / "persona" / "visual_mood_mappings.json"
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _reset_legacy_visual_config_aliases() -> Dict[str, Any]:
    # Remove stale per-token state that points at old absolute temp paths; keep ledger history.
    token_state = ROOT / ".visual_persona_state" / "visual_generation_token_state.json"
    before_count = 0
    if token_state.exists():
        data = _read_json(token_state, {"tokens": {}})
        before_count = len(data.get("tokens", {})) if isinstance(data, dict) else 0
        _write_json(token_state, {"tokens": {}, "reset_by": "V111.20", "reason": "clear stale one-time tokens after canonical seed rebinding"})
    return {"token_state_reset": token_state.exists(), "previous_token_count": before_count}


def main() -> int:
    ts = time.strftime("V111_20_%Y%m%d_%H%M%S")
    backup_root = ROOT / "archive" / "persona_visual_cleanup_backup" / ts
    backup_root.mkdir(parents=True, exist_ok=True)

    backup_targets = [
        ROOT / "openclaw.json",
        ROOT / ".persona_visual" / "visual_config.json",
        ROOT / "assets" / "persona" / "persona_avatar_manifest.json",
        ROOT / "memory_context" / "persona_runtime" / "visual_mood_mappings.json",
        ROOT / "memory_context" / "persona" / "visual_mood_mappings.json",
        ROOT / ".visual_persona_state" / "visual_generation_token_state.json",
    ]
    backed_up = [x for x in (_copy_backup(p, backup_root) for p in backup_targets) if x]

    from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed, normalize_visual_configs

    seed = ensure_avatar_seed(ROOT)
    configs = normalize_visual_configs(ROOT)
    _sync_mood_mapping()
    token_reset = _reset_legacy_visual_config_aliases()
    archived_scripts = _archive_superseded_scripts(backup_root)
    removed_cache = _remove_pycache([
        ROOT / "memory_context" / "persona_runtime",
        ROOT / "memory_context" / "persona",
        ROOT / "infrastructure",
        ROOT / "governance",
        ROOT / "scripts",
    ])

    report = {
        "version": "V111.20",
        "status": "applied" if seed.get("ok") else "applied_with_missing_seed_avatar",
        "root": str(ROOT),
        "seed": seed,
        "configs_normalized": bool(configs),
        "mood_mapping_policy": "clean_seed_avatar_identity_only",
        "active_runtime": "memory_context.persona_runtime",
        "legacy_paths": "shim_only",
        "backed_up": backed_up,
        "backup_root": backup_root.relative_to(ROOT).as_posix(),
        "archived_superseded_scripts": archived_scripts,
        "removed_cache_entries": removed_cache,
        "token_state": token_reset,
        "next_gate": "python scripts/v111_20_persona_visual_cleanup_gate.py",
    }
    out = ROOT / "reports" / "V111_20_PERSONA_VISUAL_CLEANUP_APPLY.json"
    _write_json(out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if seed.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
