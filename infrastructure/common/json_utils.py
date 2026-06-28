from __future__ import annotations
import json
from pathlib import Path
def write_json(path,payload):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def read_json(path,default=None):
    p=Path(path)
    if not p.exists(): return default
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return default
