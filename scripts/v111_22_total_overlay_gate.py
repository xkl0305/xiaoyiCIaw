#!/usr/bin/env python3
from __future__ import annotations
import json, os, py_compile, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

passed = 0
failed = 0
failures = []

def check(name, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        failures.append({'name': name, 'detail': str(detail)[:700]})

from memory_context.persona_runtime.visual_identity_seed import ensure_avatar_seed
seed = ensure_avatar_seed(ROOT)
check('seed avatar exists', seed.get('ok') is True, seed)
check('seed avatar canonical path', seed.get('seed_avatar_path') == 'assets/persona/seed_avatar.jpg', seed)

from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
samples = [
    ('搞定了，全部通过验收！大功告成', {'success_moment', 'victorious'}),
    ('这什么玩意儿，为什么报错了', {'confused'}),
    ('偷偷看看你在干嘛', {'sneaky'}),
    ('在吗，早上好', {'calm'}),
]
for msg, expect in samples:
    pred = predict_visual_intent(user_message=msg, context={}, persona_state={})
    check(f'{msg} mood', pred.get('mood') in expect, pred)
    if pred.get('confidence', 0) >= 0.50:
        check(f'{msg} auto candidate', pred.get('auto_generation_candidate') is True, pred)

from governance.persona_visual_budget_guard import load_persona_visual_config
cfg = load_persona_visual_config()
check('daily limit 100', int(cfg.get('dailyAutoGenerateLimit', -1)) == 100, cfg)
check('cooldown 0', int(cfg.get('cooldownTurns', -1)) == 0, cfg)

from core.agent_kernel.autonomy import run_autonomy_cycle, init_autonomy_system, MemoryKernel
check('autonomy top-level exports complete', callable(run_autonomy_cycle) and callable(init_autonomy_system) and MemoryKernel is not None)

from core.agent_kernel.personal_agent import compile_goal, build_task_graph, run_personal_execution
check('personal_agent top-level exports complete', callable(compile_goal) and callable(build_task_graph) and callable(run_personal_execution))

check('nested autonomy package archived', not (ROOT/'core/agent_kernel/autonomy/autonomy').exists(), 'core/agent_kernel/autonomy/autonomy')
check('nested personal_agent package archived', not (ROOT/'core/agent_kernel/personal_agent/personal_agent').exists(), 'core/agent_kernel/personal_agent/personal_agent')

for rel_dir in [
    'governance/evidence_gate/approvals/legacy_conflicts',
    'governance/evidence_gate/audit/legacy_conflicts',
    'orchestration/skill_runtime/router/legacy_conflicts',
    'orchestration/skill_runtime/router/routing/legacy_conflicts',
]:
    check(f'{rel_dir} archived', not (ROOT/rel_dir).exists(), rel_dir)

check('new fusion doc persona visual exists', (ROOT/'governance/fused_modules/doc_fusion_persona_visual_semantic_autotrigger_v20260506.json').exists())
check('new fusion doc duplicate cleanup exists', (ROOT/'governance/fused_modules/doc_fusion_agent_kernel_duplicate_package_cleanup_v20260506.json').exists())

os.environ['NO_EXTERNAL_API'] = 'true'
from infrastructure.mainline_hook import run as mainline_run
dry = mainline_run(message='搞定了，全部通过验收！大功告成', goal='gate', mode='pre_reply', dry_run=True)
check('mainline persona visual result exists', isinstance(dry.get('persona_visual_auto_generation_result'), dict), dry)
check('mainline dry-run generation ready', dry.get('persona_visual_generation_status') in {'dry_run_ready', 'blocked_by_no_external_api', 'blocked_by_policy', 'skipped'}, dry.get('persona_visual_generation_status'))
check('mainline matched persona mood', dry.get('persona_visual_mood') in {'success_moment', 'victorious'}, dry.get('persona_visual_mood'))

compile_targets = [
    'core/agent_kernel/autonomy/__init__.py',
    'core/agent_kernel/personal_agent/__init__.py',
    'memory_context/persona_runtime/persona_visual_intent_predictor.py',
    'memory_context/persona_runtime/persona_visual_auto_generation_bridge.py',
    'infrastructure/mainline_hook.py',
    'scripts/v111_22_total_overlay_apply.py',
    'scripts/v111_22_total_overlay_gate.py',
]
ok = True
for rel in compile_targets:
    try:
        py_compile.compile(str(ROOT/rel), doraise=True)
    except Exception as e:
        ok = False
        failures.append({'name': 'compile', 'detail': f'{rel}: {e}'})
check('targeted compile ok', ok)

# cleanup pycache generated during gate
for p in list(ROOT.rglob('__pycache__')):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob('*.pyc')):
    try:
        p.unlink()
    except FileNotFoundError:
        pass
pyc_left = len(list(ROOT.rglob('*.pyc'))) + len(list(ROOT.rglob('__pycache__')))
check('no pycache after gate cleanup', pyc_left == 0, pyc_left)

report = {
    'version': 'V111.22',
    'status': 'pass' if failed == 0 else 'fail',
    'passed': passed,
    'failed': failed,
    'failures': failures,
    'seed_avatar_path': 'assets/persona/seed_avatar.jpg',
}
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports'/'V111_22_TOTAL_OVERLAY_GATE.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if failed == 0 else 1)
