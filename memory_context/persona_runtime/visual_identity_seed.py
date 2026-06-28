"""V111.20 canonical avatar seed resolver for persona visuals.

One rule: the avatar image is the persona visual seed image. Text may describe
mood and scene, but never becomes the source of character identity.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

CANONICAL_SEED_REL = "assets/persona/seed_avatar.jpg"
MANIFEST_REL = "assets/persona/persona_avatar_manifest.json"
VISUAL_CONFIG_REL = ".persona_visual/visual_config.json"


def get_workspace_root(file: str | None = None) -> Path:
    cur = Path(file).resolve() if file else Path.cwd().resolve()
    start = cur if cur.is_dir() else cur.parent
    for p in [start] + list(start.parents):
        if (p / "openclaw.json").exists() or (p / "scripts").exists() or (p / "skills").exists():
            return p
    return Path.cwd().resolve()


ROOT = get_workspace_root(__file__)


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_abs(path_like: str | Path | None, root: Path = ROOT) -> Optional[Path]:
    if not path_like:
        return None
    p = Path(str(path_like)).expanduser()
    if not p.is_absolute():
        p = root / p
    return p


def candidate_seed_paths(root: Path = ROOT) -> list[Path]:
    """Return possible avatar files, canonical path first."""
    candidates: list[Path] = []
    env_path = os.environ.get("XIAOYI_PERSONA_AVATAR") or os.environ.get("PERSONA_AVATAR_PATH")
    if env_path:
        p = _as_abs(env_path, root)
        if p:
            candidates.append(p)

    openclaw = _read_json(root / "openclaw.json", {})
    pv = openclaw.get("personaVisual") or openclaw.get("persona_visual") or {}
    if isinstance(pv, dict):
        for key in ("seedAvatarPath", "seed_avatar_path", "canonicalSeedPath", "avatarPath"):
            p = _as_abs(pv.get(key), root)
            if p:
                candidates.append(p)

    vcfg = _read_json(root / VISUAL_CONFIG_REL, {})
    if isinstance(vcfg, dict):
        for key in ("seed_avatar_path", "seed_image_path", "avatar_seed_path"):
            p = _as_abs(vcfg.get(key), root)
            if p:
                candidates.append(p)
        for rel in vcfg.get("seed_image_search_paths", []) if isinstance(vcfg.get("seed_image_search_paths"), list) else []:
            p = _as_abs(rel, root)
            if p:
                candidates.append(p)

    common = [
        CANONICAL_SEED_REL,
        "assets/persona/seed_avatar.png",
        "assets/persona/seed_avatar.webp",
        "assets/persona/avatar.jpg",
        "assets/persona/avatar.png",
        "assets/persona/avatar.webp",
        ".persona_visual/seed_avatar.jpg",
        ".persona_visual/seed_avatar.png",
        ".persona_visual/avatar_seed.jpg",
        ".persona_visual/avatar_seed.png",
        "memory_context/persona/assets/seed_avatar.jpg",
        "memory_context/persona/assets/avatar.jpg",
    ]
    candidates.extend(_as_abs(x, root) for x in common if _as_abs(x, root))

    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def locate_seed_avatar(root: Path = ROOT) -> Optional[Path]:
    for p in candidate_seed_paths(root):
        if p and p.exists() and p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            return p
    return None


def canonical_seed_path(root: Path = ROOT, *, absolute: bool = False) -> str:
    p = root / CANONICAL_SEED_REL
    return str(p if absolute else CANONICAL_SEED_REL)


def write_seed_manifest(seed_path: Path, root: Path = ROOT, source: str = "existing") -> Dict[str, Any]:
    rel = seed_path.relative_to(root).as_posix() if seed_path.is_relative_to(root) else str(seed_path)
    payload: Dict[str, Any] = {
        "version": "V111.24",
        "status": "bound",
        "seed_role": "persona_visual_seed_image",
        "avatar_binding": "direct_avatar_equals_seed",
        "canonical_seed_avatar_path": CANONICAL_SEED_REL,
        "resolved_seed_avatar_path": rel,
        "sha256": _sha256(seed_path),
        "size_bytes": seed_path.stat().st_size,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "identity_rules": [
            "Use this avatar image as the only character identity source.",
            "Text prompts may only control mood, pose, lighting, props, and scene.",
            "Never replace identity with long body/appearance prose.",
            "Every generated persona visual must include this seed/reference image.",
        ],
    }
    _write_json(root / MANIFEST_REL, payload)
    return payload


def normalize_visual_configs(root: Path = ROOT) -> Dict[str, Any]:
    """Force all config surfaces to point to the same avatar seed path."""
    # openclaw.json
    openclaw_path = root / "openclaw.json"
    openclaw = _read_json(openclaw_path, {})
    if not isinstance(openclaw, dict):
        openclaw = {}
    pv = openclaw.get("personaVisual")
    if not isinstance(pv, dict):
        pv = {}
    pv.update({
        "enabled": True,
        "predictiveSuggestion": True,
        "generationConsentMode": "auto_with_budget",
        "autoGenerate": True,
        "autoGenerateRequiresBudget": True,
        "confidenceThreshold": float(pv.get("confidenceThreshold", 0.82)),
        "strongThreshold": float(pv.get("strongThreshold", 0.82)),
        "midHighThreshold": float(pv.get("midHighThreshold", 0.65)),
        "midLowThreshold": float(pv.get("midLowThreshold", 0.50)),
        "recordOnlyThreshold": float(pv.get("recordOnlyThreshold", 0.30)),
        "cooldownTurns": int(pv.get("cooldownTurns", 0)),
        "dailyAutoGenerateLimit": int(pv.get("dailyAutoGenerateLimit", 100)),
        "externalProvider": "seedream",
        "seedAvatarPath": CANONICAL_SEED_REL,
        "canonicalSeedPath": CANONICAL_SEED_REL,
        "avatarSeedBinding": "direct_avatar_equals_seed",
        "identitySource": "seed_avatar_image_only",
        "identityTextPromptMode": "seed_lock_only",
        "sceneTriggerMode": "semantic_scene",
        "seedIdentityConsistency": "strict",
        "seedReferenceRequired": True,
        "seedReferenceWeight": 100,
        "defaultMode": "auto_with_budget",
        "userStandingConsent": bool(pv.get("userStandingConsent", True)),
        "activeRuntime": "memory_context.persona_runtime",
        "legacyRuntimePolicy": "shim_only",
        "triggerSourcePolicy": "assistant_lobster_output_first",
        "fuzzyMatchingEnabled": True,
        "nearSynonymMatchingEnabled": True,
        "userStyleAdaptiveMatching": True,
        "visualScope": "persona_scene_auto_only",
        "autoTriggerScope": "persona_scene_auto_only",
        "genericImageGenerationUsesAvatarSeed": False,
        "avatarSeedNeverUsedForGenericImage": True,
    })
    openclaw["personaVisual"] = pv
    _write_json(openclaw_path, openclaw)

    # .persona_visual/visual_config.json
    vcfg = {
        "version": "V111.24",
        "enabled": True,
        "default_trigger_mode": "auto",
        "scene_trigger_mode": "semantic_scene",
        "auto_image_requires_explicit_user_request": False,
        "allow_external_image_api": True,
        "image_skill_id": "seedream-image-gen",
        "prompt_skill_id": "claw-art",
        "seed_avatar_required": True,
        "seed_avatar_path": CANONICAL_SEED_REL,
        "seed_image_path": CANONICAL_SEED_REL,
        "canonical_seed_path": CANONICAL_SEED_REL,
        "avatar_seed_binding": "direct_avatar_equals_seed",
        "identity_source": "seed_avatar_image_only",
        "identity_text_prompt_mode": "seed_lock_only",
        "reference_strategy": "always_use_avatar_seed_image",
        "visual_scope": "persona_scene_auto_only",
        "purpose": "persona_visualization",
        "generic_image_generation_policy": "never_use_persona_avatar_seed_unless_scope_is_persona_visualization",
        "generic_image_generation_uses_avatar_seed": False,
        "image_model_version": "seedream5",
        "image_action_name": "seedreamBatch5",
        "reference_weight": 100,
        "seed_image_search_paths": [
            CANONICAL_SEED_REL,
            "assets/persona/seed_avatar.png",
            "assets/persona/seed_avatar.webp",
            "assets/persona/avatar.jpg",
            "assets/persona/avatar.png",
            ".persona_visual/seed_avatar.jpg",
            ".persona_visual/avatar_seed.jpg",
        ],
        "cache_enabled": True,
        "cache_ttl_days": 30,
        "max_prompt_chars": 1200,
        "return_mode": "render_plan",
        "never_generate_without_user_trigger": False,
        "safety": {
            "no_real_payment": True,
            "no_real_send": True,
            "no_real_device": True,
            "no_external_api_global_unlock": True,
        },
    }
    _write_json(root / VISUAL_CONFIG_REL, vcfg)
    return {"openclaw_personaVisual": pv, "visual_config": vcfg}


def ensure_avatar_seed(root: Path = ROOT, *, copy_if_needed: bool = True) -> Dict[str, Any]:
    root = Path(root).resolve()
    canonical = root / CANONICAL_SEED_REL
    canonical.parent.mkdir(parents=True, exist_ok=True)

    found = locate_seed_avatar(root)
    source = "canonical_existing"
    if found is None:
        normalize_visual_configs(root)
        return {
            "ok": False,
            "status": "missing_seed_avatar",
            "canonical_seed_avatar_path": CANONICAL_SEED_REL,
            "absolute_path": str(canonical),
            "message": "Put the avatar image at assets/persona/seed_avatar.jpg, then rerun the gate.",
        }

    if found.resolve() != canonical.resolve():
        if copy_if_needed:
            shutil.copy2(found, canonical)
            found = canonical
            source = "copied_from_candidate"
        else:
            source = "candidate_found_not_copied"
    else:
        found = canonical

    manifest = write_seed_manifest(found, root, source=source)
    configs = normalize_visual_configs(root)
    return {
        "ok": True,
        "status": "avatar_bound_as_persona_visual_seed",
        "seed_avatar_path": CANONICAL_SEED_REL,
        "seed_avatar_abs_path": str(found),
        "sha256": manifest.get("sha256"),
        "size_bytes": manifest.get("size_bytes"),
        "manifest": manifest,
        "configs": configs,
    }


def get_seed_avatar_path(root: Path = ROOT, *, absolute: bool = False, ensure: bool = True) -> Optional[str]:
    if ensure:
        info = ensure_avatar_seed(root)
        if not info.get("ok"):
            return None
    p = root / CANONICAL_SEED_REL
    if not p.exists():
        return None
    return str(p if absolute else CANONICAL_SEED_REL)


__all__ = [
    "CANONICAL_SEED_REL",
    "MANIFEST_REL",
    "ROOT",
    "candidate_seed_paths",
    "canonical_seed_path",
    "ensure_avatar_seed",
    "get_seed_avatar_path",
    "locate_seed_avatar",
    "normalize_visual_configs",
    "write_seed_manifest",
]
