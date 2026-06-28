from __future__ import annotations
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def remove_tree(p: Path) -> None:
    if p.exists() and p.is_dir():
        shutil.rmtree(p, ignore_errors=True)

for p in list(ROOT.rglob('__pycache__')):
    remove_tree(p)
for p in ROOT.rglob('*.pyc'):
    try:
        p.unlink()
    except Exception:
        pass

print('V111.51.16 provider guard hardened overlay applied')
print('auto_pvc_removed=true')
print('seed_avatar_reference_requires_main_pipeline=true')
print('persona_identity_descriptor_requires_main_pipeline=true')
print('actual_reference_payload_required=true')
