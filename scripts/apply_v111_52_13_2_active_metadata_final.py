#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, os
from pathlib import Path

VERSION = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'

def find_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[1], Path.cwd()]
    for c in candidates:
        if (c / 'openclaw.json').exists():
            return c
    return here.parents[1]

ROOT = find_root()
PAYLOAD = ROOT / 'overlay_payload_v111_52_13_2'

def copy_payload():
    if PAYLOAD.exists():
        for src in PAYLOAD.rglob('*'):
            if src.is_dir():
                continue
            rel = src.relative_to(PAYLOAD)
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

def patch_json_files():
    # Defensive patch in case files were locally edited before applying.
    def load(p):
        fp = ROOT / p
        return json.loads(fp.read_text(encoding='utf-8')) if fp.exists() else {}
    def save(p, data):
        fp = ROOT / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    oc = load('openclaw.json')
    oc['PERSONAL_OS_ENTERPRISE_VERSION'] = VERSION
    oc['personalOSEnterpriseVersion'] = VERSION
    oc.setdefault('personalOSEnterprise', {})['version'] = VERSION
    oc.setdefault('personalOSEnterprise', {})['defaultProfile'] = 'strict_local_enterprise'
    oc.setdefault('personalOSEnterprise', {})['defaultRuntimeProfile'] = 'strict_local_enterprise'
    oc.setdefault('personalOsEnterprise', {})['version'] = VERSION
    oc.setdefault('personalOsEnterprise', {})['defaultProfile'] = 'strict_local_enterprise'
    oc.setdefault('personalOsEnterprise', {})['defaultRuntimeProfile'] = 'strict_local_enterprise'
    oc.setdefault('localCapabilityRuntime', {})['version'] = VERSION
    oc.setdefault('personaVisual', {})['version'] = VERSION
    for k,v in {'ALLOW_NETWORK':False,'NO_EXTERNAL_API':True,'OFFLINE_MODE':True,'ONLINE_MODE':False,
                'NO_REAL_PAYMENT':True,'NO_REAL_SEND':True,'ZERO_EXTERNAL_MODE':True,'ZERO_COST_MODE':True}.items():
        oc[k]=v
    rt=oc.setdefault('runtime',{})
    for k,v in {'ALLOW_NETWORK':False,'NO_EXTERNAL_API':True,'OFFLINE_MODE':True,'ONLINE_MODE':False,
                'NO_REAL_PAYMENT':True,'NO_REAL_SEND':True,'ZERO_EXTERNAL_MODE':True,'ZERO_COST_MODE':True}.items():
        rt[k]=v
    rt['profile']='strict_local_enterprise'
    save('openclaw.json', oc)
    for p in ['release_manifest.json','xiaoyi_persona_visual/version.json','profiles/model_hash_manifest.json','.openclaw/hooks/manifest.json']:
        data=load(p)
        data['version']=VERSION
        if p == 'release_manifest.json':
            data['personal_os_enterprise_version']=VERSION
            data['active_metadata_closed']=True
            data['active_metadata_close_version']=VERSION
        elif p == 'xiaoyi_persona_visual/version.json':
            data['personal_os_enterprise_version']=VERSION
        elif p == '.openclaw/hooks/manifest.json':
            data['personal_os_enterprise_version']=VERSION
            data['active_metadata_closed']=True
        save(p, data)

def clean_runtime():
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        os.system(f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S {cleaner} >/dev/null 2>&1")
    # remove overlay dirs after copy
    for pat in ['overlay_payload*','_overlay*','V111_52_13_1_enterprise_report_remaining_clean_gate_overlay*']:
        for p in ROOT.glob(pat):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink(missing_ok=True)

def main():
    copy_payload()
    patch_json_files()
    clean_runtime()
    print(json.dumps({'overall':'applied','version':VERSION}, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
