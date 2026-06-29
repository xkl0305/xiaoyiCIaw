#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path

VERSION='V111.52.13.1_ENTERPRISE_REPORT_REMAINING_CLEAN_GATE_FINAL'
SCRIPT=Path(__file__).resolve()

def find_root() -> Path:
    for p in [SCRIPT.parent, *SCRIPT.parents, Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (p/'openclaw.json').exists() and (p/'xiaoyi_persona_visual').exists():
            return p
    return SCRIPT.parents[1]

ROOT=find_root()
PAYLOAD=ROOT/'overlay_payload_v111_52_13_1'

def load_json(path):
    p=ROOT/path
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {}

def save_json(path, obj):
    p=ROOT/path
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def copy_payload():
    copied=[]
    if PAYLOAD.exists():
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
    feats['enterprise_report_remaining_clean_gate_final']=True
    feats['direct_verify_self_clean_gate']=True
    save_json('xiaoyi_persona_visual/version.json', v)
    rm=load_json('release_manifest.json')
    rm['version']=VERSION
    rm['personal_os_enterprise_version']=VERSION
    rm['enterprise_report_remaining_clean_gate_final']=True
    rm.setdefault('acceptance',{})['verify_v111_52_13_1_clean_gate']='required'
    rm.setdefault('changes',[]).append('make V111.52.13 verification self-clean before package_clean gate')
    save_json('release_manifest.json', rm)
    oc=load_json('openclaw.json')
    oc['PERSONAL_OS_ENTERPRISE_VERSION']=VERSION
    oc['ENTERPRISE_REPORT_REMAINING_CLEAN_GATE_FINAL']=True
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
        mh['enterprise_report_remaining_clean_gate_final']=True
        save_json('profiles/model_hash_manifest.json', mh)

def clean_runtime():
    cleaner=ROOT/'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
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
    print(json.dumps({'overall':'applied','version':VERSION,'root':str(ROOT),'copied_count':len(copied)},ensure_ascii=False,indent=2))
if __name__=='__main__':
    main()
