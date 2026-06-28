#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
checks=[]
def add(name, ok, details=None): checks.append({'name':name,'ok':bool(ok),'details':details})

data=json.loads((ROOT/'openclaw.json').read_text(encoding='utf-8'))
rt=data.get('runtime', {})
add('top_level_online_mode_true', data.get('ONLINE_MODE') is True)
add('top_level_offline_mode_false', data.get('OFFLINE_MODE') is False)
add('top_level_no_external_api_false', data.get('NO_EXTERNAL_API') is False)
add('nested_runtime_offline_false', rt.get('OFFLINE_MODE') is False)
add('nested_runtime_no_external_api_false', rt.get('NO_EXTERNAL_API') is False)
add('connected_runtime_always_on', data.get('connectedRuntime',{}).get('alwaysConnected') is True)
add('side_effect_policy_strong_confirmation', data.get('realSideEffectPolicy',{}).get('sendPaymentDeleteDevice')=='strong_confirmation_required')
try:
    from infrastructure.unified_runtime_config import get_runtime_config
    summary=get_runtime_config().summary()
    add('unified_runtime_config_online', summary.get('online_mode') is True and summary.get('offline_mode') is False, summary)
    add('unified_runtime_config_no_external_false', summary.get('no_external_api') is False, summary)
except Exception as e: add('unified_runtime_config_import', False, str(e))
try:
    from infrastructure.online_runtime_policy import online_runtime_status
    st=online_runtime_status()
    add('online_runtime_policy_enabled', st.get('online_runtime_enabled') is True and st.get('offline_mode') is False, st)
except Exception as e: add('online_runtime_policy_import', False, str(e))
try:
    from infrastructure.offline_runtime_guard import status, assert_safe_action
    st=status()
    add('legacy_offline_guard_is_online_shim', st.get('offline') is False and st.get('online_connected') is True, st)
    h=assert_safe_action('send email to customer')
    add('high_risk_requires_confirmation_not_offline_ban', h.get('requires_strong_confirmation') is True and h.get('mode')=='strong_confirmation_required', h)
except Exception as e: add('offline_guard_shim_import', False, str(e))
for k in ['NO_EXTERNAL_API','OFFLINE_MODE','NO_REAL_SEND','NO_REAL_PAYMENT','NO_REAL_DEVICE']:
    os.environ.pop(k, None)
try:
    import infrastructure.fusion_engine_v2  # noqa
    env_bad={k:os.environ.get(k) for k in ['NO_EXTERNAL_API','OFFLINE_MODE','NO_REAL_SEND','NO_REAL_PAYMENT','NO_REAL_DEVICE'] if os.environ.get(k)=='true'}
    add('fusion_engine_import_does_not_force_offline_env', not env_bad, env_bad)
except Exception as e: add('fusion_engine_import', False, str(e))
try:
    from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
    a=observe_turn(user_message='普通聊一句', assistant_message='我这边已经跑通了，全部通过验收，收口完成', context={}, persona_state={})
    add('assistant_output_auto_trigger', a.get('auto_generation_candidate') is True and a.get('trigger_source')=='assistant_message', a)
    l=observe_turn(user_message='普通聊一句', lobster_message='跑通啦，没红，收尾完成', context={}, persona_state={})
    add('lobster_output_auto_trigger', l.get('auto_generation_candidate') is True and l.get('trigger_source')=='lobster_message', l)
    f=observe_turn(user_message='普通聊一句', assistant_message='我偷瞄一下状态，悄咪咪探头看一眼', context={}, persona_state={})
    add('near_synonym_fuzzy_trigger', f.get('auto_generation_candidate') is True and f.get('mood')=='sneaky', f)
except Exception as e: add('visual_turn_observer_direct', False, str(e))
try:
    from memory_context.persona_runtime.persona_visual_rccam_loop import process_persona_visual_turn
    g=process_persona_visual_turn('普通聊一句', {}, assistant_message='我这边已经跑通了，全部通过验收，收口完成', dry_run=True)
    add('dry_run_generation_ready', g.get('action',{}).get('generation_status')=='dry_run_ready' or g.get('generation_status')=='dry_run_ready', g)
except Exception as e: add('dry_run_generation_ready', False, str(e))
try:
    from governance.runtime_commit_barrier_bridge import check_action
    c=check_action('send email to supplier')
    add('commit_action_requires_strong_confirmation', c.get('requires_strong_confirmation') is True and c.get('status')=='confirmation_required', c)
    c2=check_action('send email to supplier', payload={'strong_confirmation': True})
    add('confirmed_commit_action_can_pass', c2.get('status')=='ok' and not c2.get('commit_blocked'), c2)
except Exception as e: add('commit_barrier_online_policy', False, str(e))
failed=[c for c in checks if not c['ok']]
out={'version':'V111.24','status':'pass' if not failed else 'fail','passed':len(checks)-len(failed),'failed':len(failed),'failures':failed,'checks':checks}
print(json.dumps(out, ensure_ascii=False, indent=2))
sys.exit(0 if not failed else 1)
