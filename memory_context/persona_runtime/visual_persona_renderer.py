"""V111.20 canonical persona visual renderer.

Clean rule set:
1. Avatar image is the seed image and the only identity source.
2. Mood/scene text controls expression, pose, lighting, props, and background only.
3. No long appearance/body prompt can override the avatar seed.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from memory_context.persona_runtime.visual_identity_seed import (
        CANONICAL_SEED_REL,
        ROOT,
        ensure_avatar_seed,
        get_seed_avatar_path,
        normalize_visual_configs,
    )
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[2]
    CANONICAL_SEED_REL = "assets/persona/seed_avatar.jpg"
    def ensure_avatar_seed(root: Path = ROOT, **_: Any) -> Dict[str, Any]:
        p = root / CANONICAL_SEED_REL
        return {"ok": p.exists(), "seed_avatar_path": CANONICAL_SEED_REL, "seed_avatar_abs_path": str(p)}
    def get_seed_avatar_path(root: Path = ROOT, *, absolute: bool = False, ensure: bool = True) -> Optional[str]:
        p = root / CANONICAL_SEED_REL
        return str(p if absolute else CANONICAL_SEED_REL) if p.exists() else None
    def normalize_visual_configs(root: Path = ROOT) -> Dict[str, Any]:
        return {}

STATE_DIR = ROOT / ".persona_visual"
STATE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = STATE_DIR / "visual_config.json"
LEDGER_PATH = STATE_DIR / "visual_request_ledger.jsonl"
MAPPING_PATH = Path(__file__).with_name("visual_mood_mappings.json")

MANUAL_TRIGGER_PHRASES = [
    "生成心情图", "来张心情图", "看看你", "你现在什么样", "什么心情",
    "大龙虾心情", "正在做什么的图", "给我看一下你", "人格图", "形象图",
    "生成你的图", "画一下你", "视觉化一下", "出图", "生成图片",
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "V111.20",
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
    "reference_weight": 100,
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


@dataclass
class PersonaVisualPlan:
    status: str
    mode: str
    mood: str
    activity: str
    energy: int
    confidence: int
    user_explicit_request: bool
    can_call_external_image_api: bool
    requires_user_confirmation: bool
    seed_image_path: Optional[str]
    cache_key: str
    prompt: str
    negative_prompt: str
    skill_task_draft: Dict[str, Any]
    warnings: List[str]
    blocked_reason: Optional[str] = None
    semantic_scene: Optional[str] = None
    seed_avatar_abs_path: Optional[str] = None


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_visual_config() -> Dict[str, Any]:
    # Keep openclaw and visual config normalized every time this runtime is touched.
    try:
        normalize_visual_configs(ROOT)
    except Exception:
        pass
    cfg = _load_json(CONFIG_PATH, {})
    merged = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        merged.update(cfg)
        safety = dict(DEFAULT_CONFIG["safety"])
        safety.update(cfg.get("safety", {}) if isinstance(cfg.get("safety"), dict) else {})
        merged["safety"] = safety
    merged["seed_avatar_path"] = CANONICAL_SEED_REL
    merged["seed_image_path"] = CANONICAL_SEED_REL
    merged["canonical_seed_path"] = CANONICAL_SEED_REL
    merged["avatar_seed_binding"] = "direct_avatar_equals_seed"
    merged["identity_source"] = "seed_avatar_image_only"
    merged["identity_text_prompt_mode"] = "seed_lock_only"
    merged["reference_weight"] = 100
    _write_json(CONFIG_PATH, merged)
    return merged


def load_mood_mappings() -> Dict[str, Any]:
    data = _load_json(MAPPING_PATH, {})
    if isinstance(data, dict) and data.get("moods"):
        return data
    return {
        "default_style": {
            "character_identity": "Use the provided seed avatar image as the only identity source.",
            "visual_language": "clean expressive illustration, safe, no text overlay",
            "negative_prompt": "different character, identity drift, watermark, NSFW, sexualized",
        },
        "activity_overlays": {"planning": "standing near a tidy planning desk"},
        "moods": {"calm": {"pose": "relaxed", "palette": "soft blue", "keywords": ["calm"]}},
    }


def discover_seed_image(cfg: Optional[Dict[str, Any]] = None, *, absolute: bool = False) -> Optional[str]:
    _ = cfg or ensure_visual_config()
    return get_seed_avatar_path(ROOT, absolute=absolute, ensure=True)


def seed_avatar_status() -> Dict[str, Any]:
    info = ensure_avatar_seed(ROOT)
    return {
        "seed_avatar_available": bool(info.get("ok")),
        "seed_avatar_path": info.get("seed_avatar_path") or CANONICAL_SEED_REL,
        "seed_avatar_abs_path": info.get("seed_avatar_abs_path"),
        "avatar_binding": "direct_avatar_equals_seed",
        "identity_source": "seed_avatar_image_only",
        "required_for_identity_consistency": True,
        "message": "avatar is bound as persona visual seed" if info.get("ok") else "missing avatar seed: place image at assets/persona/seed_avatar.jpg",
    }


def normalize_mood(raw: Any) -> str:
    mood = str(raw or "calm").strip().lower()
    aliases = {
        "audit": "serious", "auditor": "serious", "guardian": "guardian_mode", "guard": "guardian_mode",
        "happy": "amused", "proud_mode": "proud", "debug": "focused", "lobster_mood": "playful",
        "大龙虾": "playful", "龙虾": "playful", "得意": "proud", "认真": "serious", "专注": "focused",
        "疲惫": "tired", "困惑": "confused", "温和": "calm", "victory": "victorious",
    }
    return aliases.get(mood, mood)


def infer_activity(message: str = "", state: Optional[Dict[str, Any]] = None) -> str:
    text = (message or "").lower()
    if any(k in text for k in ["代码", "bug", "报错", "修复", "patch", "gate", "脚本", "压缩包", "debug"]):
        return "coding"
    if any(k in text for k in ["审计", "检查", "排查", "风险", "安全", "拦截", "审核", "复查"]):
        return "auditing"
    if any(k in text for k in ["计划", "路线", "方案", "下一步", "规划"]):
        return "planning"
    if any(k in text for k in ["记忆", "人格", "上下文", "关系", "handoff"]):
        return "remembering"
    if any(k in text for k in ["支付", "发送", "外发", "设备", "签署", "删除"]):
        return "guarding"
    if any(k in text for k in ["图片", "视频", "脚本", "直播", "商品图", "设计"]):
        return "creating"
    return str((state or {}).get("current_activity") or "planning")


def is_explicit_visual_request(message: str = "") -> bool:
    text = (message or "").lower()
    return any(k.lower() in text for k in MANUAL_TRIGGER_PHRASES)


def _bounded_int(value: Any, default: int = 70) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return default


def load_persona_state() -> Dict[str, Any]:
    for rel in [
        ".memory_persona/persona_state.json",
        "memory_context/persona/persona_state.json",
        ".persona_state/persona_state.json",
    ]:
        data = _load_json(ROOT / rel, None)
        if isinstance(data, dict):
            return data
    return {"mood": "calm", "energy": 70, "confidence": 75, "uncertainty": 20, "current_mode": "executor"}


def _scene_from_prediction(prediction: Optional[Dict[str, Any]], mood: str) -> str:
    if isinstance(prediction, dict) and prediction.get("semantic_scene"):
        return str(prediction["semantic_scene"])
    mapping = {
        "victorious": "celebration_scene",
        "success_moment": "approval_scene",
        "confused": "problem_solving_scene",
        "focused": "deep_work_scene",
        "working_state": "busy_work_scene",
        "guardian_mode": "risk_gate_scene",
        "calm": "daily_presence_scene",
        "lazy": "rest_scene",
        "sneaky": "peek_scene",
    }
    return mapping.get(mood, f"{mood}_scene")


def build_visual_prompt(
    persona_state: Optional[Dict[str, Any]] = None,
    message: str = "",
    mood: Optional[str] = None,
    activity: Optional[str] = None,
    semantic_scene: Optional[str] = None,
    prediction: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    persona_state = persona_state or {}
    mappings = load_mood_mappings()
    default_style = mappings.get("default_style", {}) if isinstance(mappings.get("default_style"), dict) else {}
    moods = mappings.get("moods", {}) if isinstance(mappings.get("moods"), dict) else {}
    mood_key = normalize_mood(mood or persona_state.get("mood") or persona_state.get("current_mood") or "calm")
    if mood_key not in moods:
        mood_key = "calm" if "calm" in moods else next(iter(moods.keys()), "calm")
    activity_key = activity or infer_activity(message, persona_state)
    scene_key = semantic_scene or _scene_from_prediction(prediction, mood_key)
    overlays = mappings.get("activity_overlays", {}) if isinstance(mappings.get("activity_overlays"), dict) else {}
    scene_profiles = mappings.get("scene_profiles", {}) if isinstance(mappings.get("scene_profiles"), dict) else {}
    activity_text = overlays.get(scene_key) or overlays.get(activity_key) or overlays.get("planning") or "working in a clean visual scene"
    mood_info = moods.get(mood_key, {}) if isinstance(moods.get(mood_key, {}), dict) else {}
    scene_profile = scene_profiles.get(scene_key, {}) if isinstance(scene_profiles.get(scene_key, {}), dict) else {}

    energy = _bounded_int(persona_state.get("energy", 70), 70)
    confidence = _bounded_int(persona_state.get("confidence", 75), 75)
    uncertainty = _bounded_int(persona_state.get("uncertainty", 20), 20)

    intensity_parts: list[str] = []
    if energy < 30:
        intensity_parts.append("low-energy gentle posture")
    elif energy > 80:
        intensity_parts.append("bright energetic motion accents")
    else:
        intensity_parts.append("balanced calm glow")
    if uncertainty > 60:
        intensity_parts.append("careful expression with subtle uncertainty cue")
    if confidence > 85:
        intensity_parts.append("confident stable posture")

    keywords = ", ".join(str(x) for x in mood_info.get("keywords", [])[:6])
    scene_evidence = []
    if isinstance(prediction, dict):
        scene_evidence = [str(x) for x in (prediction.get("trigger_signals") or prediction.get("signals") or [])[:6]]

    scene_action = scene_profile.get('action', 'natural in-scene action')
    scene_expression = scene_profile.get('expression', mood_info.get('pose', 'natural expressive pose'))
    scene_body = scene_profile.get('body_state', 'stable expressive body language')
    scene_props = scene_profile.get('props', 'minimal clean supporting props')
    scene_camera = scene_profile.get('camera', 'clean medium shot')
    scene_background = scene_profile.get('background', activity_text)

    prompt = (
        f"Reference image is mandatory: use the supplied seed avatar as the ONLY character identity source. "
        f"Preserve the same character identity, face, recognizable silhouette, signature traits, and outfit language from the seed avatar. "
        f"This is persona-scene auto-generation only, not generic image generation. "
        f"Do not invent a new character and do not override identity with text appearance prose. "
        f"Mood: {mood_key}. Semantic scene: {scene_key}. Pose: {mood_info.get('pose', 'natural expressive pose')}. "
        f"Primary action: {scene_action}. Expression: {scene_expression}. Body state: {scene_body}. "
        f"Activity/background: {activity_text}. Background detail: {scene_background}. Props/supporting elements: {scene_props}. Camera/framing: {scene_camera}. "
        f"Palette: {mood_info.get('palette', 'clean soft cinematic palette')}. "
        f"Energy {energy}/100, confidence {confidence}/100, {', '.join(intensity_parts)}. "
        f"Visual language: {default_style.get('visual_language', 'clean premium illustration, safe, no text overlay')}. "
        f"Keywords: {keywords or mood_key}. Scene evidence: {', '.join(scene_evidence) or 'semantic context'}. "
        f"No readable text overlays, no watermark, no logo."
    ).strip()
    max_chars = int(ensure_visual_config().get("max_prompt_chars", 1200))
    if len(prompt) > max_chars:
        prompt = prompt[: max_chars - 3] + "..."
    negative = default_style.get("negative_prompt") or "different character, identity drift, watermark, NSFW, sexualized"
    return {"prompt": prompt, "negative_prompt": negative, "mood": mood_key, "activity": activity_key, "semantic_scene": scene_key}


def _cache_key(prompt: str, seed: Optional[str]) -> str:
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8"))
    if seed:
        h.update(seed.encode("utf-8"))
    return h.hexdigest()[:24]


def _external_image_allowed(user_explicit_request: bool, cfg: Dict[str, Any]) -> bool:
    if not user_explicit_request and cfg.get("auto_image_requires_explicit_user_request", False):
        return False
    if not cfg.get("allow_external_image_api", False):
        return False
    # Never globally unlock APIs; this only indicates the renderer can prepare a task.
    return True


def build_skill_task_draft(prompt: str, negative_prompt: str, seed_image_path: Optional[str], cfg: Dict[str, Any]) -> Dict[str, Any]:
    seed_abs = get_seed_avatar_path(ROOT, absolute=True, ensure=True) if seed_image_path else None
    return {
        "skill_id": cfg.get("image_skill_id", "seedream-image-gen"),
        "prompt_skill_id": cfg.get("prompt_skill_id", "claw-art"),
        "mode": "image_to_image" if seed_image_path else "blocked_missing_seed_avatar",
        "reference_image": seed_abs,
        "reference_image_rel": seed_image_path,
        "reference_image_required": True,
        "identity_consistency_required": True,
        "seed_reference_weight": int(cfg.get("reference_weight", 100)),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "output_policy": "use avatar seed as reference; do not generate if seed avatar is missing",
        "requires_user_confirmation": False,
        "real_side_effects": False,
    }


def plan_persona_visual(
    message: str = "",
    persona_state: Optional[Dict[str, Any]] = None,
    trigger_mode: Optional[str] = None,
    user_explicit_request: Optional[bool] = None,
    force_mood: Optional[str] = None,
    force_activity: Optional[str] = None,
    semantic_scene: Optional[str] = None,
    prediction: Optional[Dict[str, Any]] = None,
) -> PersonaVisualPlan:
    cfg = ensure_visual_config()
    persona_state = persona_state or load_persona_state()
    explicit = is_explicit_visual_request(message) if user_explicit_request is None else bool(user_explicit_request)
    mode = trigger_mode or cfg.get("default_trigger_mode", "auto")
    seed_info = ensure_avatar_seed(ROOT)
    seed_rel = seed_info.get("seed_avatar_path") if seed_info.get("ok") else None
    seed_abs = seed_info.get("seed_avatar_abs_path") if seed_info.get("ok") else None

    prompt_data = build_visual_prompt(
        persona_state,
        message,
        mood=force_mood,
        activity=force_activity,
        semantic_scene=semantic_scene,
        prediction=prediction,
    )
    prompt = prompt_data["prompt"]
    negative = prompt_data["negative_prompt"]
    key = _cache_key(prompt, seed_rel)
    can_external = _external_image_allowed(explicit, cfg)
    warnings: List[str] = []
    blocked_reason = None
    if seed_rel is None:
        warnings.append("seed_avatar_missing_generation_blocked")
        blocked_reason = "seed_avatar_missing"
        can_external = False
    if os.environ.get("NO_EXTERNAL_API", "").lower() == "true":
        warnings.append("NO_EXTERNAL_API_env_active_runtime_may_only_dry_run")
    task = build_skill_task_draft(prompt, negative, seed_rel, cfg)
    status = "ready_for_seed_reference_generation" if can_external and seed_rel else "render_plan_only"
    plan = PersonaVisualPlan(
        status=status,
        mode=mode,
        mood=prompt_data["mood"],
        activity=prompt_data["activity"],
        semantic_scene=prompt_data.get("semantic_scene"),
        energy=_bounded_int(persona_state.get("energy", 70), 70),
        confidence=_bounded_int(persona_state.get("confidence", 75), 75),
        user_explicit_request=explicit,
        can_call_external_image_api=can_external,
        requires_user_confirmation=False,
        seed_image_path=seed_rel,
        seed_avatar_abs_path=seed_abs,
        cache_key=key,
        prompt=prompt,
        negative_prompt=negative,
        skill_task_draft=task,
        warnings=warnings,
        blocked_reason=blocked_reason,
    )
    record_visual_event(plan)
    return plan


def record_visual_event(plan: PersonaVisualPlan) -> None:
    try:
        row = asdict(plan)
        row["ts"] = time.time()
        with LEDGER_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def visual_summary_for_hook(message: str = "", persona_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = ensure_visual_config()
    state = persona_state or load_persona_state()
    prompt_data = build_visual_prompt(state, message)
    seed = seed_avatar_status()
    return {
        "persona_visual_enabled": bool(cfg.get("enabled", True)),
        "trigger_mode": cfg.get("default_trigger_mode", "auto"),
        "explicit_visual_request_detected": is_explicit_visual_request(message),
        "current_visual_mood": prompt_data["mood"],
        "current_visual_activity": prompt_data["activity"],
        "semantic_scene": prompt_data.get("semantic_scene"),
        "seed_image_available": seed["seed_avatar_available"],
        "seed_avatar_path": seed["seed_avatar_path"],
        "avatar_binding": "direct_avatar_equals_seed",
        "default_behavior": "semantic_scene_auto_with_avatar_seed_identity_lock",
        "suggested_phrases": MANUAL_TRIGGER_PHRASES[:6],
    }


def asdict_plan(plan: PersonaVisualPlan) -> Dict[str, Any]:
    return asdict(plan)


def render_plan(
    prediction: Optional[Dict[str, Any]] = None,
    seed_avatar_path: Optional[str] = None,
    scene_image_path: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    message = kwargs.get("message") or (prediction or {}).get("message", "")
    mood = "calm"
    semantic_scene = None
    matched_patterns: list[str] = []
    if isinstance(prediction, dict):
        mood = prediction.get("mood") or prediction.get("predicted_visual_type") or "calm"
        semantic_scene = prediction.get("semantic_scene")
        matched_patterns = [str(x) for x in (prediction.get("trigger_signals") or prediction.get("signals") or [])[:6]]
    seed_rel = seed_avatar_path or get_seed_avatar_path(ROOT, absolute=False, ensure=True) or CANONICAL_SEED_REL
    plan = plan_persona_visual(message=message, force_mood=mood, semantic_scene=semantic_scene, prediction=prediction)
    seed_abs = get_seed_avatar_path(ROOT, absolute=True, ensure=True)
    final_prompt = (
        f"{plan.prompt} Strict seed lock: use the seed avatar/reference image as the direct persona visual seed. "
        f"Reference image required. Same identity every time. Only vary expression, pose, lighting, props, and scene. "
        f"Matched semantic signals: {', '.join(matched_patterns) or 'none'}."
    )
    task = dict(plan.skill_task_draft)
    task.update({
        "semantic_scene": plan.semantic_scene or semantic_scene,
        "reference_image": seed_abs,
        "reference_image_rel": seed_rel,
        "reference_image_required": True,
        "identity_consistency_required": True,
        "seed_reference_weight": 100,
        "avatar_seed_binding": "direct_avatar_equals_seed",
    })
    return {
        "status": plan.status,
        "purpose": "persona_visualization",
        "visual_scope": "persona_scene_auto_only",
        "generic_image_generation": False,
        "prompt": final_prompt,
        "negative_prompt": plan.negative_prompt,
        "seed_avatar_path": seed_rel,
        "seed_avatar_abs_path": seed_abs,
        "scene_image_path": scene_image_path,
        "skill_task_draft": task,
        "mood": plan.mood,
        "semantic_scene": plan.semantic_scene or semantic_scene,
        "activity": plan.activity,
        "confidence": plan.confidence,
        "cache_key": plan.cache_key,
        "reference_image_required": True,
        "identity_consistency_required": True,
        "seed_reference_weight": 100,
        "identity_lock_mode": "strict_avatar_seed",
        "avatar_seed_binding": "direct_avatar_equals_seed",
    }


if __name__ == "__main__":
    p = render_plan({"mood": "success_moment", "semantic_scene": "approval_scene", "trigger_signals": ["通过验收"]}, message="搞定了，全部通过验收")
    print(json.dumps(p, ensure_ascii=False, indent=2))
