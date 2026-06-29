#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = 'V111.52.13.2_ACTIVE_METADATA_AND_CLEAN_BASE_FINAL'

def j(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def clean():
    cleaner = ROOT / 'scripts/clean_runtime_artifacts.py'
    if cleaner.exists():
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONPATH'] = '.'
        subprocess.run([sys.executable, '-S', str(cleaner)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def main():
    clean()
    oc = j('openclaw.json')
    rm = j('release_manifest.json')
    vj = j('xiaoyi_persona_visual/version.json')
    mhm = j('profiles/model_hash_manifest.json')
    hm = j('.openclaw/hooks/manifest.json')
    current = vj.get('version')
    checks = {
        'version_is_52_13_2': current == EXPECTED,
        'release_manifest_aligned': rm.get('version') == EXPECTED and rm.get('personal_os_enterprise_version') == EXPECTED,
        'model_hash_manifest_aligned': mhm.get('version') == EXPECTED,
        'openclaw_top_aligned': oc.get('PERSONAL_OS_ENTERPRISE_VERSION') == EXPECTED and oc.get('personalOSEnterpriseVersion') == EXPECTED,
        'openclaw_nested_aligned': all([
            (oc.get('personalOSEnterprise') or {}).get('version') == EXPECTED,
            (oc.get('personalOsEnterprise') or {}).get('version') == EXPECTED,
            (oc.get('localCapabilityRuntime') or {}).get('version') == EXPECTED,
            (oc.get('personaVisual') or {}).get('version') == EXPECTED,
        ]),
        'hooks_manifest_aligned': hm.get('version') == EXPECTED and hm.get('personal_os_enterprise_version') == EXPECTED,
        'strict_local_runtime': all([
            oc.get('ALLOW_NETWORK') is False,
            oc.get('NO_EXTERNAL_API') is True,
            oc.get('OFFLINE_MODE') is True,
            oc.get('ONLINE_MODE') is False,
            oc.get('NO_REAL_PAYMENT') is True,
            oc.get('NO_REAL_SEND') is True,
            (oc.get('runtime') or {}).get('ALLOW_NETWORK') is False,
            (oc.get('runtime') or {}).get('ONLINE_MODE') is False,
            (oc.get('runtime') or {}).get('profile') == 'strict_local_enterprise',
        ]),
    }
    base = subprocess.run([sys.executable, '-S', str(ROOT/'xiaoyi_persona_visual/diagnostics/verify_v111_52_13_report_remaining_close.py')],
                          cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'.'},
                          text=True, capture_output=True)
    try:
        base_payload = json.loads(base.stdout)
    except Exception:
        base_payload = {'overall':'failed','stdout':base.stdout,'stderr':base.stderr}
    checks['base_52_13_verify_passed'] = base.returncode == 0 and base_payload.get('overall') == 'passed'
    clean()
    out = {'overall': 'passed' if all(checks.values()) else 'failed',
           'version': current, 'checks': checks, 'base_verify': base_payload}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
