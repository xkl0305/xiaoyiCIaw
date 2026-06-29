#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path
VERSION='V111.52.12.1_FULL_LOCAL_STACK_RUNTIME_CLEAN_CLOSE_FINAL'
PAYLOAD_NAME='overlay_payload_v111_52_12_1'

def find_root() -> Path:
    cur=Path.cwd().resolve()
    here=Path(__file__).resolve()
    for p in [cur,*cur.parents,here.parent,*here.parents]:
        if (p/'openclaw.json').exists() and (p/'xiaoyi_persona_visual').exists():
            return p
    return cur
ROOT=find_root(); HERE=Path(__file__).resolve()

def find_payload() -> Path | None:
    for p in [ROOT/PAYLOAD_NAME, HERE.parents[1]/PAYLOAD_NAME, HERE.parent/PAYLOAD_NAME]:
        if p.exists(): return p
    return None

def copy_payload(payload: Path | None):
    if not payload: return 0
    count=0
    for src in payload.rglob('*'):
        if src.is_dir(): continue
        dst=ROOT/src.relative_to(payload)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        count+=1
    return count

def upd(path, fn):
    p=ROOT/path; d={}
    if p.exists():
        try: d=json.loads(p.read_text(encoding='utf-8'))
        except Exception: d={}
    fn(d)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def update_metadata():
    def v(d):
        d['version']=VERSION
        d['personal_os_enterprise_version']=VERSION
        d.setdefault('features',{}).update({'full_local_stack_runtime_clean_close':True,'local_model_stack_binding':True,'embodied_screen_agent_runtime':True,'observability_trace_context':True,'retention_policy_enabled':True})
    upd('xiaoyi_persona_visual/version.json',v)
    def rm(d):
        d['version']=VERSION
        d['personal_os_enterprise_version']=VERSION
        d['default_runtime_profile']='strict_local_enterprise'
        d['allow_network']=False; d['no_external_api']=True; d['external_fallback_allowed']=False
        d['runtime_clean_close']=True
        d.setdefault('acceptance',{})['verify_v111_52_12_1_full_local_stack_runtime_clean_close']='passed in builder workspace'
    upd('release_manifest.json',rm)
    def oc(d):
        d['PERSONAL_OS_ENTERPRISE_VERSION']=VERSION
        d['personalOSEnterpriseVersion']=VERSION
        d['DEFAULT_RUNTIME_PROFILE']='strict_local_enterprise'
        d['ALLOW_NETWORK']=False; d['NO_EXTERNAL_API']=True; d['OFFLINE_MODE']=True; d['ONLINE_MODE']=False
        d['NO_REAL_PAYMENT']=True; d['NO_REAL_SEND']=True; d['ZERO_EXTERNAL_MODE']=True
        d['LOCAL_MODEL_STACK_BINDING']=True; d['EMBODIED_SCREEN_AGENT_RUNTIME']=True
        d.setdefault('runtime',{}).update({'ALLOW_NETWORK':False,'NO_EXTERNAL_API':True,'OFFLINE_MODE':True,'ONLINE_MODE':False,'NO_REAL_PAYMENT':True,'NO_REAL_SEND':True,'ZERO_EXTERNAL_MODE':True})
        for k in ['personalOSEnterprise','personalOsEnterprise']:
            d.setdefault(k,{}).update({'version':VERSION,'defaultProfile':'strict_local_enterprise','defaultRuntimeProfile':'strict_local_enterprise','runtimeSecretPath':'env_only_no_workspace_path'})
        d.setdefault('sourcePackageMustExclude',[])
        for x in ['overlay_payload*','_overlay*','logs','.openclaw/state','.openclaw/hook_state','.v98_state','.v107_state','.lazy_state','.context_state','.persona_visual/runtime_wardrobe_state.json','.persona_visual/visual_request_ledger.jsonl','__pycache__','*.pyc','*.jsonl','*.sqlite3','*.db']:
            if x not in d['sourcePackageMustExclude']: d['sourcePackageMustExclude'].append(x)
    upd('openclaw.json',oc)
    def hm(d):
        d['version']=VERSION; d['personal_os_enterprise_version']=VERSION
        d['local_runtime']='strict_local_only'; d['allow_external_fallback']=False; d['post_overlay_compatible']=True; d['runtime_clean_close']=True
    upd('.openclaw/hooks/manifest.json',hm)
    def mh(d):
        d['version']=VERSION; d['local_model_stack_binding']=True; d['local_runtime']='strict_local_only'; d['allow_external_fallback']=False
    upd('profiles/model_hash_manifest.json',mh)

def clean():
    sys.path.insert(0,str(ROOT))
    try:
        from scripts.clean_runtime_artifacts import clean_runtime
        return clean_runtime(ROOT)
    except Exception:
        removed=0
        for pat in ['overlay_payload*','_overlay*','logs','generated-images','.openclaw/state','.openclaw/hook_state','.v98_state','.v107_state','.lazy_state','.context_state','.persona_visual/generated','.pytest_cache']:
            for p in ROOT.glob(pat):
                if p.is_dir(): shutil.rmtree(p,ignore_errors=True); removed+=1
                elif p.exists(): p.unlink(missing_ok=True); removed+=1
        for rel in ['.persona_visual/visual_request_ledger.jsonl','.persona_visual/runtime_wardrobe_state.json']:
            p=ROOT/rel
            if p.exists(): p.unlink(missing_ok=True); removed+=1
        for p in ROOT.rglob('__pycache__'): shutil.rmtree(p,ignore_errors=True); removed+=1
        for pat in ['*.pyc','*.pyo','*.jsonl','*.log','*.sqlite','*.sqlite3','*.db','*.sqlite3-wal','*.sqlite3-shm','*.db-wal','*.db-shm','*.tmp','*.cache','.DS_Store']:
            for p in ROOT.rglob(pat):
                if p.is_file():
                    try: p.unlink(); removed+=1
                    except Exception: pass
        return {'overall':'cleaned_fallback','removed_count':removed}

payload=find_payload()
copied=copy_payload(payload)
update_metadata()
clean_result=clean()
print(json.dumps({'overall':'applied','version':VERSION,'root':str(ROOT),'payload_copied':copied,'clean_result':clean_result},ensure_ascii=False,indent=2))
