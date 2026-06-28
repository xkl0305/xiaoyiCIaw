#!/usr/bin/env python3
"""V111.20 persona visual cleanup gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _run(args: list[str]) -> dict:
    p = subprocess.run(args, cwd=str(ROOT), text=True, capture_output=True, timeout=60)
    parsed = None
    generation_status = None
    try:
        parsed = json.loads(p.stdout)
        if isinstance(parsed, dict):
            generation_status = (parsed.get("action") or {}).get("generation_status") or parsed.get("generation_status")
    except Exception:
        parsed = None
    return {
        "cmd": args,
        "returncode": p.returncode,
        "generation_status": generation_status,
        "parsed_ok": parsed is not None,
        "stdout_tail": p.stdout[-4000:],
        "stderr": p.stderr[-4000:],
    }


def main() -> int:
    from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed, CANONICAL_SEED_REL
    from memory_context.persona_runtime.visual_persona_renderer import render_plan
    from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
    from governance.persona_visual_budget_guard import load_persona_visual_config, check_visual_budget

    seed = ensure_avatar_seed(ROOT)
    cfg = load_persona_visual_config()
    pred_success = predict_visual_intent(user_message="搞定了，全部通过验收！大功告成", context={}, persona_state={})
    pred_confused = predict_visual_intent(user_message="这什么玩意儿，为什么报错了", context={}, persona_state={})
    pred_sneaky = predict_visual_intent(user_message="偷偷看看你在干嘛", context={}, persona_state={})
    plan = render_plan(prediction=pred_success, message="搞定了，全部通过验收！大功告成")
    dry_run = _run([sys.executable, "scripts/xiaoyi_visual_entry.py", "test-generate", "偷偷看看你在干嘛", "--dry-run"])

    prompt = plan.get("prompt", "")
    forbidden_prompt_fragments = ["胸部丰满", "丁字", "比基尼", "腹股沟", "两乳", "极致身材", "裸"]
    failures: list[str] = []
    if not seed.get("ok"):
        failures.append("seed_avatar_not_bound")
    if cfg.get("seedAvatarPath") != CANONICAL_SEED_REL:
        failures.append("openclaw_seedAvatarPath_not_canonical")
    if plan.get("seed_avatar_path") != CANONICAL_SEED_REL:
        failures.append("render_plan_seed_not_canonical")
    if not plan.get("reference_image_required") or not plan.get("identity_consistency_required"):
        failures.append("render_plan_missing_identity_lock")
    if int(plan.get("seed_reference_weight", 0)) != 100:
        failures.append("seed_reference_weight_not_100")
    for frag in forbidden_prompt_fragments:
        if frag in prompt:
            failures.append(f"unsafe_or_stale_identity_prompt_fragment:{frag}")
            break
    if dry_run.get("returncode") != 0 or dry_run.get("generation_status") != "dry_run_ready":
        failures.append("dry_run_generation_not_ready")

    budget = check_visual_budget(cfg, confidence=float(pred_success.get("confidence", 0)), auto=True)
    report = {
        "version": "V111.20",
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "seed": seed,
        "config_seed": cfg.get("seedAvatarPath"),
        "predictions": {
            "success": pred_success,
            "confused": pred_confused,
            "sneaky": pred_sneaky,
        },
        "render_plan": {
            "status": plan.get("status"),
            "seed_avatar_path": plan.get("seed_avatar_path"),
            "identity_lock_mode": plan.get("identity_lock_mode"),
            "seed_reference_weight": plan.get("seed_reference_weight"),
            "prompt_len": len(prompt),
            "negative_prompt": plan.get("negative_prompt"),
        },
        "budget": budget,
        "dry_run": dry_run,
    }
    out = ROOT / "reports" / "V111_20_PERSONA_VISUAL_CLEANUP_GATE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
