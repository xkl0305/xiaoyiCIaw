#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from pathlib import Path

VERSION='V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL'
SCRIPT=Path(__file__).resolve()
ROOT=SCRIPT.parents[1]
PAYLOAD=ROOT/'overlay_payload_v111_52_13'

def load_json(path):
    p=ROOT/path
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {}

def save_json(path, obj):
    p=ROOT/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def copy_payload():
    if not PAYLOAD.exists():
        return []
    copied=[]
    for src in PAYLOAD.rglob('*'):
        if src.is_dir():
            continue
        rel=src.relative_to(PAYLOAD)
        dst=ROOT/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src,dst)
        copied.append(rel.as_posix())
    return copied

def update_metadata():
    v=load_json('xiaoyi_persona_visual/version.json')
    v['version']=VERSION
    v['personal_os_enterprise_version']=VERSION
    feats=v.setdefault('features',{})
    for k in ['enterprise_report_remaining_close','acceptance_regression_matrix_complete','observability_slo_ops_ready','rootless_deploy_smoke_ready','secret_workflow_guard_ready','data_retention_policy_ready','private_network_policy_ready','local_persona_image_fail_closed_domain']:
        feats[k]=True
    save_json('xiaoyi_persona_visual/version.json', v)
    rm=load_json('release_manifest.json')
    rm['version']=VERSION
    rm['personal_os_enterprise_version']=VERSION
    rm['report_remaining_close']=True
    rm['model_weights_included']=False
    rm.setdefault('acceptance',{})['verify_v111_52_13_report_remaining_close']='required'
    rm.setdefault('changes',[]).extend([
        'close remaining enterprise report items with acceptance/regression matrix files',
        'add observability SLO/metric catalog ops layer',
        'add rootless deployment smoke verification',
        'add secret workflow guard',
        'add data retention/artifact policy manager',
        'add private network policy and local persona image fail-closed domain',
    ])
    save_json('release_manifest.json', rm)
    oc=load_json('openclaw.json')
    oc['PERSONAL_OS_ENTERPRISE_VERSION']=VERSION
    oc['LOCAL_MODEL_STACK_BINDING']=True
    oc['ENTERPRISE_REPORT_REMAINING_CLOSE']=True
    oc['ACCEPTANCE_REGRESSION_MATRIX_COMPLETE']=True
    oc['OBSERVABILITY_SLO_OPS_READY']=True
    oc['ROOTLESS_DEPLOY_SMOKE_READY']=True
    oc['SECRET_WORKFLOW_GUARD_READY']=True
    oc['DATA_RETENTION_POLICY_READY']=True
    oc['PRIVATE_NETWORK_POLICY_READY']=True
    oc['ALLOW_NETWORK']=False; oc['NO_EXTERNAL_API']=True; oc['OFFLINE_MODE']=True; oc['ONLINE_MODE']=False; oc['NO_REAL_PAYMENT']=True; oc['NO_REAL_SEND']=True; oc['ZERO_EXTERNAL_MODE']=True
    runtime=oc.setdefault('runtime',{})
    runtime.update({'ALLOW_NETWORK':False,'NO_EXTERNAL_API':True,'OFFLINE_MODE':True,'ONLINE_MODE':False,'NO_REAL_PAYMENT':True,'NO_REAL_SEND':True,'ZERO_EXTERNAL_MODE':True,'profile':'strict_local_enterprise'})
    for key in ('personalOSEnterprise','personalOsEnterprise'):
        obj=oc.setdefault(key,{})
        obj['version']=VERSION
        obj['defaultProfile']='strict_local_enterprise'
        obj['defaultRuntimeProfile']='strict_local_enterprise'
    save_json('openclaw.json', oc)
    mh=load_json('profiles/model_hash_manifest.json')
    if mh:
        mh['version']=VERSION
        mh['report_remaining_close']=True
        save_json('profiles/model_hash_manifest.json', mh)

def clean_runtime():
    cleaner=ROOT/'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        import subprocess, sys, os
        env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTHONPATH']='.'
        subprocess.run([sys.executable,'-S',str(cleaner)],cwd=ROOT,env=env,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for pat in ['overlay_payload*','_overlay*','V111_52_11_1_manifest_model_hash_tighten_overlay']:
        for p in ROOT.glob(pat):
            if p.is_dir(): shutil.rmtree(p,ignore_errors=True)
            elif p.exists(): p.unlink(missing_ok=True)

def main():
    copied=copy_payload()
    update_metadata()
    clean_runtime()
    print(json.dumps({'overall':'applied','version':VERSION,'copied_count':len(copied)},ensure_ascii=False,indent=2))
if __name__=='__main__':
    main()
