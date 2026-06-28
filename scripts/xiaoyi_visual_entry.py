#!/usr/bin/env python3
"""Unified persona visual entry. V111.23 adds assistant/lobster turn observer."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
def _print(obj): print(json.dumps(obj, ensure_ascii=False, indent=2))
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['health','status','seed','test-mood','test-turn','test-render','test-generate','ledger','budget','online'])
    ap.add_argument('text', nargs='?', default='搞定了，全部通过验收！大功告成')
    ap.add_argument('--assistant-message', default=None)
    ap.add_argument('--lobster-message', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ns = ap.parse_args()
    if ns.command in {'health','status'}:
        import platform
        from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed
        from memory_context.persona_runtime.persona_visual_ledger import visual_status
        from governance.persona_visual_budget_guard import load_persona_visual_config
        from infrastructure.online_runtime_policy import online_runtime_status
        _print({'status':'ok','platform':platform.system(),'runtime_version':'V111.23','personaVisual':load_persona_visual_config(),'seed':ensure_avatar_seed(ROOT),'ledger':visual_status(),'online_runtime':online_runtime_status()}); return
    if ns.command == 'online':
        from infrastructure.online_runtime_policy import online_runtime_status
        _print(online_runtime_status()); return
    if ns.command == 'seed':
        from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed
        _print(ensure_avatar_seed(ROOT)); return
    if ns.command == 'test-mood':
        from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
        _print(predict_visual_intent(user_message=ns.text, context={}, persona_state={})); return
    if ns.command == 'test-turn':
        from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
        _print(observe_turn(user_message=ns.text, assistant_message=ns.assistant_message, lobster_message=ns.lobster_message, context={}, persona_state={})); return
    if ns.command == 'test-render':
        from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
        from memory_context.persona_runtime.visual_persona_renderer import render_plan
        obs = observe_turn(user_message=ns.text, assistant_message=ns.assistant_message, lobster_message=ns.lobster_message, context={}, persona_state={})
        _print(render_plan(prediction=obs.get('prediction'), message=obs.get('selected_text') or ns.text)); return
    if ns.command == 'test-generate':
        from memory_context.persona_runtime.persona_visual_rccam_loop import process_persona_visual_turn
        _print(process_persona_visual_turn(ns.text, {}, assistant_message=ns.assistant_message, lobster_message=ns.lobster_message, dry_run=ns.dry_run)); return
    if ns.command == 'ledger':
        from memory_context.persona_runtime.persona_visual_ledger import visual_status, read_visual_events
        _print({'status': visual_status(), 'events': read_visual_events(20)}); return
    if ns.command == 'budget':
        from governance.persona_visual_budget_guard import load_persona_visual_config, check_visual_budget
        cfg = load_persona_visual_config(); _print(check_visual_budget(cfg, confidence=0.54, auto=True)); return
if __name__ == '__main__': main()
