#!/usr/bin/env python3
from __future__ import annotations
import json, os, py_compile, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
passed=0; failed=0; failures=[]
def check(name, cond, detail=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; failures.append({'name': name, 'detail': str(detail)[:700]})
data = json.loads((ROOT/'openclaw.json').read_text(encoding='utf-8'))
check('NO_EXTERNAL_API false', data.get('NO_EXTERNAL_API') is False, data.get('NO_EXTERNAL_API'))
check('OFFLINE_MODE false', data.get('OFFLINE_MODE') is False, data.get('OFFLINE_MODE'))
check('ONLINE_MODE true', data.get('ONLINE_MODE') is True, data.get('ONLINE_MODE'))
from infrastructure.online_runtime_policy import online_runtime_status, is_online_runtime_enabled
status = online_runtime_status()
check('online runtime enabled', is_online_runtime_enabled() is True, status)
check('xiaoyi always connected', status.get('xiaoyi_capabilities_always_connected') is True, status)
check('end side always connected', status.get('end_side_capabilities_always_connected') is True, status)
from memory_context.persona_runtime.persona_visual_turn_observer import observe_turn
obs = observe_turn(user_message='普通聊一句', assistant_message='我这边已经跑通了，全部通过验收，收口完成', context={}, persona_state={})
check('assistant output selected', obs.get('trigger_source') == 'assistant_message', obs)
check('assistant output auto candidate', obs.get('auto_generation_candidate') is True, obs)
check('assistant output mood success/victory', obs.get('mood') in {'victorious','success_moment','focused'}, obs)
obs2 = observe_turn(user_message='普通聊一句', lobster_message='跑通啦，没红，收尾完成', context={}, persona_state={})
check('lobster output selected', obs2.get('trigger_source') == 'lobster_message', obs2)
check('lobster fuzzy auto candidate', obs2.get('auto_generation_candidate') is True, obs2)
obs3 = observe_turn(user_message='普通聊一句', assistant_message='我偷瞄一下状态，悄咪咪探头看一眼', context={}, persona_state={})
check('sneaky fuzzy detected', obs3.get('mood') == 'sneaky', obs3)
check('sneaky fuzzy candidate', obs3.get('auto_generation_candidate') is True, obs3)
from infrastructure.mainline_hook import run as mainline_run
res = mainline_run(message='普通聊天', assistant_message='我这边已经跑通了，全部通过验收，收口完成', dry_run=True)
check('mainline has generation result', isinstance(res.get('persona_visual_auto_generation_result'), dict), res)
check('mainline trigger source assistant', res.get('persona_visual_trigger_source') == 'assistant_message', res)
check('mainline dry run ready', res.get('persona_visual_generation_status') in {'dry_run_ready','blocked_by_policy','missing_skill'}, res.get('persona_visual_generation_status'))
from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed
seed = ensure_avatar_seed(ROOT)
check('seed avatar canonical', seed.get('seed_avatar_path') == 'assets/persona/seed_avatar.jpg' and seed.get('ok') is True, seed)
targets = ['infrastructure/online_runtime_policy.py','memory_context/persona_runtime/persona_visual_intent_predictor.py','memory_context/persona_runtime/persona_visual_turn_observer.py','memory_context/persona_runtime/persona_visual_prediction_hook.py','memory_context/persona_runtime/persona_visual_auto_generation_bridge.py','memory_context/persona_runtime/persona_visual_rccam_loop.py','infrastructure/mainline_hook.py','scripts/xiaoyi_visual_entry.py','scripts/v111_23_total_online_autotrigger_apply.py','scripts/v111_23_online_lobster_autotrigger_gate.py']
compile_ok=True
for rel in targets:
    try: py_compile.compile(str(ROOT/rel), doraise=True)
    except Exception as e: compile_ok=False; failures.append({'name':'compile','detail':f'{rel}: {e}'})
check('targeted compile ok', compile_ok)
for p in list(ROOT.rglob('__pycache__')): shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob('*.pyc')):
    try: p.unlink()
    except Exception: pass
pyc_left = len(list(ROOT.rglob('*.pyc'))) + len(list(ROOT.rglob('__pycache__')))
check('no pycache after gate cleanup', pyc_left == 0, pyc_left)
report = {'version':'V111.23','status':'pass' if failed==0 else 'fail','passed':passed,'failed':failed,'failures':failures,'online_runtime':status,'seed_avatar_path':'assets/persona/seed_avatar.jpg'}
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports'/'V111_23_TOTAL_ONLINE_AUTOTRIGGER_GATE.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if failed==0 else 1)
