from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path
from typing import Dict, Any, Optional
VERSION = 'V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'
def detect_rootless_runtime() -> Dict[str, Any]:
    candidates=[]
    for name in ['podman','docker']:
        exe=shutil.which(name)
        if not exe: continue
        try:
            proc=subprocess.run([exe,'info'],text=True,capture_output=True,timeout=10,check=False); txt=(proc.stdout+proc.stderr).lower(); rootless='rootless' in txt or os.geteuid()!=0
            candidates.append({'name':name,'path':exe,'available':proc.returncode==0,'rootless_likely':rootless})
        except Exception as e: candidates.append({'name':name,'path':exe,'available':False,'error':str(e)})
    return {'version':VERSION,'candidates':candidates,'recommended':candidates[0]['name'] if candidates else '', 'rootless_required':True}
def validate_rootless_layout(root: Optional[str | Path] = None) -> Dict[str, Any]:
    rootp=Path(root or '.').resolve(); checks={'compose_exists':(rootp/'deployment/rootless/compose.local.yaml').exists(),'systemd_service_exists':(rootp/'deployment/rootless/systemd-user/xiaoyi-local.service').exists(),'models_not_packaged':not (rootp/'models').exists(),'runtime_state_not_packaged':not (rootp/'.openclaw/state').exists()}
    return {'overall':'passed' if all(checks.values()) else 'failed','checks':checks,'version':VERSION}
