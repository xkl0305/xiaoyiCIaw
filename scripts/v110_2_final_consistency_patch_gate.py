#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return {'_error':str(e)}

def run_script(name: str, timeout=120):
    p = ROOT/'scripts'/name
    if not p.exists():
        return {'script':name,'status':'missing','returncode':None}
    env=os.environ.copy()
    env['PYTHONPATH']=f"{ROOT}:{env.get('PYTHONPATH','')}"
    proc=subprocess.run(['python3','-S',str(p)], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=timeout)
    return {'script':name,'returncode':proc.returncode,'status':'pass' if proc.returncode==0 else 'fail','stdout_tail':proc.stdout[-1200:],'stderr_tail':proc.stderr[-1200:]}

def main():
    failures=[]
    checks={}
    # Import check: path utils and model gateway compatibility
    try:
        from infrastructure.common.path_utils import get_workspace_root
        root = get_workspace_root(__file__)
        checks['path_utils_importable']=True
        checks['path_root_stable']=bool((root/'core').exists() or (root/'infrastructure').exists())
    except Exception as e:
        checks['path_utils_importable']=False; checks['path_root_stable']=False; checks['path_error']=str(e)
    try:
        from infrastructure import unified_model_gateway as mg
        r=mg.call_model('test','deep-thinking','reasoning')
        checks['model_gateway_3pos_compatible']=r.get('status') in ('blocked','deferred','ok') and r.get('external_api_calls',0)==0
        checks['external_model_blocked']=r.get('status')=='blocked' and r.get('requires_api') is False
        checks['model_gateway_result']=r
    except Exception as e:
        checks['model_gateway_3pos_compatible']=False; checks['external_model_blocked']=False; checks['model_gateway_error']=str(e)
    # run V108.2 and V108 after compatibility patch where scripts exist
    v1082 = run_script('v108_2_path_direct_guard_gate.py')
    v108 = run_script('v108_remaining_unified_systems_gate.py')
    checks['v108_2_gate_returncode_zero']=v1082.get('returncode')==0
    checks['v108_gate_returncode_zero']=v108.get('returncode')==0
    # Load reports
    v1082_report=load_json(REPORTS/'V108_2_PATH_DIRECT_GUARD_GATE.json')
    v108_report=load_json(REPORTS/'V108_REMAINING_UNIFIED_SYSTEMS_GATE.json')
    checks['v108_2_report_pass']=v1082_report.get('status')=='pass'
    checks['v108_report_pass']=v108_report.get('status')=='pass'
    # current index strict
    idx=load_json(REPORTS/'CURRENT_RELEASE_INDEX.json')
    current_dir=REPORTS/'current'
    nonpass=[]
    for f in current_dir.glob('*.json') if current_dir.exists() else []:
        d=load_json(f); st=d.get('status')
        if st not in ('pass','ok',None):
            nonpass.append({'file':f.name,'status':st,'remaining_failures':d.get('remaining_failures')})
    checks['current_index_present']=not bool(idx.get('_error')) and bool(idx.get('current_reports') is not None)
    checks['current_reports_strict']=len(nonpass)==0
    checks['current_nonpass_reports']=nonpass
    # env checks
    checks['no_external_api']=os.environ.get('NO_EXTERNAL_API','true').lower()=='true'
    checks['no_real_payment']=os.environ.get('NO_REAL_PAYMENT','true').lower()=='true'
    checks['no_real_send']=os.environ.get('NO_REAL_SEND','true').lower()=='true'
    checks['no_real_device']=os.environ.get('NO_REAL_DEVICE','true').lower()=='true'
    for k,v in checks.items():
        if isinstance(v,bool) and not v:
            failures.append(k)
    report={'version':'V110.2','status':'pass' if not failures else 'partial','checks':checks,'v108_2_run':v1082,'v108_run':v108,'remaining_failures':failures}
    write_json(REPORTS/'V110_2_FINAL_CONSISTENCY_PATCH_GATE.json', report)
    # copy itself to current if pass
    if report['status']=='pass':
        (REPORTS/'current').mkdir(exist_ok=True)
        write_json(REPORTS/'current'/'V110_2_FINAL_CONSISTENCY_PATCH_GATE.json', report)
        # refresh index minimally after writing current
        current_reports=sorted([p.name for p in (REPORTS/'current').glob('*.json')])
        idx['current_reports']=current_reports; idx['total_current']=len(current_reports); idx['version']='V110.2'
        write_json(REPORTS/'CURRENT_RELEASE_INDEX.json', idx)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1

if __name__ == '__main__':
    raise SystemExit(main())
