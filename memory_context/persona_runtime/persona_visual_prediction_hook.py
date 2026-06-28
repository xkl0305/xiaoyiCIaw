"""V111.24 prediction hook — observes assistant/lobster output first and keeps persona visual scoped."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]

def _load_persona_state() -> Dict[str, Any]:
    for rel in ['.memory_persona/persona_state.json','memory_context/persona/persona_state.json','.context_state/persona_state.json']:
        p = ROOT / rel
        if p.exists():
            try: return json.loads(p.read_text(encoding='utf-8'))
            except Exception: pass
    return {'mood':'focused','energy':70,'confidence':80}

def run(message: str | None = None, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    context = dict(context or {})
    from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
    from memory_context.persona_runtime.visual_persona_renderer import render_plan
    from governance.persona_visual_budget_guard import load_persona_visual_config, check_visual_budget
    persona_state = _load_persona_state()
    obs = observe_turn(user_message=message, assistant_message=context.get('assistant_message'), lobster_message=context.get('lobster_message'), context=context, persona_state=persona_state)
    prediction = obs.get('prediction', {})
    selected_text = obs.get('selected_text') or message or ''
    plan = render_plan(prediction=prediction, message=selected_text)
    cfg = load_persona_visual_config()
    budget = check_visual_budget(cfg, confidence=float(prediction.get('confidence', 0.0)), auto=True)
    ready = bool(prediction.get('auto_generation_candidate') and plan.get('seed_avatar_path') and budget.get('ok'))
    return {
        'status':'ok',
        'visual_prediction_summary': prediction,
        'turn_observer': obs,
        'render_plan': plan,
        'ready_to_generate': ready,
        'auto_generation_allowed': ready,
        'visual_requires_confirmation': False,
        'budget_status': budget,
        'no_external_api_global_unlock': False,
        'trigger_source': obs.get('trigger_source'),
        'selected_trigger_text': selected_text,
        'visual_scope': 'persona_scene_auto_only',
        'purpose': 'persona_visualization',
        'generic_image_generation': False,
    }

__all__=['run']
