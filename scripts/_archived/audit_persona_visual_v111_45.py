#!/usr/bin/env python3
from __future__ import annotations
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from infrastructure.persona_visual_hook_bus import dispatch, status
    from memory_context.persona_runtime.persona_visual_dedupe_gate import clear_dedupe_state
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction

    # Prove raw no-skills package can self-heal hooks without running apply first.
    shutil.rmtree(ROOT / '.openclaw' / 'hooks', ignore_errors=True)
    clear_dedupe_state()
    first = dispatch('post_reply', user_message='probe', assistant_message='搞定了 🎉', reply_text='搞定了 🎉', dry_run=True)
    second = dispatch('post_reply', user_message='probe', assistant_message='搞定了 🎉', reply_text='搞定了 🎉', dry_run=True)
    pred = {'auto_generation_candidate': True, 'should_auto_generate': True, 'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization', 'mood': 'shy', 'semantic_scene': 'bashful_scene'}
    dry = generate_from_prediction(pred, text='（月羽云裳的薄纱裙摆随风飘了一下）', user_message='看看尾巴尖', dry_run=True)
    report = {
        'status': 'ok',
        'version': 'V111.45_NO_SKILLS_HOOK_SELFHEAL',
        'self_heal_first_status': first.get('status'),
        'self_heal_first_generation': (first.get('result') or {}).get('generation_status'),
        'self_heal_second_generation': (second.get('result') or {}).get('generation_status'),
        'hooks_after_self_heal': status(),
        'stealth_focus': detect_focus_request('偷偷看看你'),
        'tail_focus': detect_focus_request('看看尾巴尖'),
        'dry_run_status': dry.get('status'),
        'dry_run_focus_target': dry.get('focus_target'),
        'secondary_generation_planned': dry.get('secondary_generation_planned'),
        'max_images_this_turn': dry.get('max_images_this_turn'),
    }
    out = ROOT / 'reports/V111_45_NO_SKILLS_HOOK_SELFHEAL_AUDIT.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['self_heal_first_generation'] != 'dry_run_ready' or report['self_heal_second_generation'] != 'deduped_skip':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
