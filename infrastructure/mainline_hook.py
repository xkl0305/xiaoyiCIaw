from __future__ import annotations
from pathlib import Path
import json, os, time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.v98_state'
STATE.mkdir(exist_ok=True)
_last_goal = None

# V111.51.14: lightweight hook registry compatibility layer
_PRE_HOOKS = []
_POST_HOOKS = []

def register_pre_hook(fn):
    if callable(fn) and fn not in _PRE_HOOKS:
        _PRE_HOOKS.append(fn)
    return {'registered': True, 'hook_type': 'pre_reply', 'total': len(_PRE_HOOKS)}

def register_post_hook(fn):
    if callable(fn) and fn not in _POST_HOOKS:
        _POST_HOOKS.append(fn)
    return {'registered': True, 'hook_type': 'post_reply', 'total': len(_POST_HOOKS)}

def list_registered_hooks():
    return {
        'pre_reply': [getattr(fn, '__name__', repr(fn)) for fn in _PRE_HOOKS],
        'post_reply': [getattr(fn, '__name__', repr(fn)) for fn in _POST_HOOKS],
    }

def _run_registered_pre_hooks(payload):
    for fn in list(_PRE_HOOKS):
        try:
            updated = fn(payload)
            if isinstance(updated, dict):
                payload = updated
        except Exception as e:
            payload.setdefault('warnings', []).append(f'pre_hook_failed:{getattr(fn, "__name__", repr(fn))}:{e}')
    return payload

def _run_registered_post_hooks(context, payload):
    for fn in list(_POST_HOOKS):
        try:
            updated = fn(context, payload)
            if isinstance(updated, dict):
                payload = updated
        except Exception as e:
            payload.setdefault('warnings', []).append(f'post_hook_failed:{getattr(fn, "__name__", repr(fn))}:{e}')
    return payload


def set_last_goal(goal):
    global _last_goal
    _last_goal = goal
    return {'status': 'ok', 'last_goal': goal}


def _base_run(message=None, goal=None, mode='pre_reply'):
    if goal:
        set_last_goal(goal)
    try:
        from memory_context.unified_continuity_engine import bootstrap_for_reply
        from infrastructure.context_loading_engine import UnifiedContextLoadingEngine
        from governance.skill_intelligence_engine import recommend_skills
        loader = UnifiedContextLoadingEngine()
        p0 = loader.preload_p0()
        p1 = loader.warm_p1()
        continuity = bootstrap_for_reply(message or goal or '', {'mode': mode})
        skills = recommend_skills(message or goal or '', {'mode': mode}, top_k=5) if (message or goal) else []
    except Exception as e:
        p0 = []
        p1 = []
        continuity = {'status': 'warning', 'error': str(e)}
        skills = []
    try:
        from infrastructure.online_runtime_policy import online_runtime_status
        online_status = online_runtime_status()
    except Exception:
        online_status = {'online_runtime_enabled': True, 'policy': 'always_online_default'}
    payload = {
        'status': 'ok',
        'mode': mode,
        'context_summary': continuity,
        'guardrail_summary': {
            'offline': False,
            'online': True,
            'no_external_api': False,
            'connected_runtime_always_on': True,
            'no_per_action_online_authorization': True,
            'no_real_payment': os.environ.get('NO_REAL_PAYMENT') == 'true',
            'no_real_send': os.environ.get('NO_REAL_SEND') == 'true',
            'no_real_device': os.environ.get('NO_REAL_DEVICE') == 'true',
        },
        'online_runtime_status': online_status,
        'runtime_fusion_summary': {
            'p0_preloaded': len(p0),
            'p1_warmed': len(p1),
            'skill_recommendations': len(skills),
        },
        'proactive_skill_summary': skills[:3],
        'heavy_chain_triggered': False,
        'persona_mode': True,
        'persona_does_not_override_governance': True,
        'fail_soft': True,
        'last_goal': goal or _last_goal,
        'ts': time.time(),
    }
    with (STATE / 'mainline_hook_heartbeat.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')
    try:
        from infrastructure.persona_visual_runtime_hook import augment_hook_payload
        payload = augment_hook_payload(payload, message=message, context={'goal': goal, 'mode': mode})
    except Exception as e:
        payload.setdefault('warnings', []).append(f'persona_visual_hook_failed:{e}')
    try:
        from xiaoyi_persona_visual.registry.register_persona_visual import register_persona_visual
        register_persona_visual(app=None)
        payload['register_persona_visual_called'] = True
    except Exception:
        payload['register_persona_visual_called'] = False
        payload.setdefault('warnings', []).append('register_persona_visual_failed')
    return payload


def run(message=None, goal=None, mode='pre_reply', assistant_message=None, lobster_message=None, reply_text=None, **kwargs):
    result = _base_run(message=message, goal=goal, mode=mode)
    result = _run_registered_pre_hooks(result)
    visual_context = {'goal': goal, 'mode': mode, **kwargs}
    if assistant_message:
        visual_context['assistant_message'] = assistant_message
    if lobster_message:
        visual_context['lobster_message'] = lobster_message
    if reply_text:
        visual_context['reply_text'] = reply_text
    try:
        from infrastructure.persona_visual_prediction_hook import run as _visual_run
        visual = _visual_run(message=message, context=visual_context)
        result['visual_prediction_summary'] = visual.get('visual_prediction_summary')
        result['visual_suggestion_available'] = visual.get('visual_suggestion_available', False)
        result['visual_auto_generation_allowed'] = visual.get('auto_generation_allowed', False)
        result['visual_requires_confirmation'] = visual.get('visual_requires_confirmation', True)
        result['persona_visual_render_plan'] = visual.get('render_plan')
        result['persona_visual_trigger_source'] = visual.get('trigger_source')
        result['persona_visual_selected_text'] = visual.get('selected_trigger_text')
        result['persona_visual_turn_observer'] = visual.get('turn_observer')
        result['persona_visual_generation_status'] = 'delegated_to_post_reply_hook'
        result['persona_visual_generation_delegate'] = 'scripts/mainline_bootstrap.py post_reply hook'
    except Exception as e:
        result['visual_prediction_summary'] = {'status': 'fail_soft', 'error': str(e)}
        result['visual_suggestion_available'] = False
        result['visual_auto_generation_allowed'] = False
        result['visual_requires_confirmation'] = True
    result = _run_registered_post_hooks(visual_context, result)
    return result


def pre_reply(message=None, goal=None):
    return run(message=message, goal=goal, mode='pre_reply')


def post_reply(user_message=None, assistant_message=None, lobster_message=None, **kwargs):
    return run(message=user_message, assistant_message=assistant_message, lobster_message=lobster_message, mode='post_reply', **kwargs)


def on_pre_reply(user_message=None, assistant_message=None, lobster_message=None, draft_reply=None, reply_text=None, **kwargs):
    return run(message=user_message, assistant_message=assistant_message or draft_reply or reply_text, lobster_message=lobster_message, reply_text=reply_text or draft_reply, mode='pre_reply', **kwargs)


def on_post_reply(user_message=None, assistant_message=None, lobster_message=None, reply_text=None, **kwargs):
    return post_reply(user_message=user_message, assistant_message=assistant_message or reply_text, lobster_message=lobster_message, reply_text=reply_text, **kwargs)
