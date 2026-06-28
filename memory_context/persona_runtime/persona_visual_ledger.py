"""Persona visual ledger helpers."""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".visual_persona_state"
STATE.mkdir(parents=True, exist_ok=True)
LEDGER = STATE / "visual_generation_ledger.jsonl"
def append_visual_event(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(event); payload.setdefault("ts", time.time())
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload
def read_visual_events(limit: int = 50) -> List[Dict[str, Any]]:
    if not LEDGER.exists(): return []
    rows=[]
    for line in LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines():
        try: rows.append(json.loads(line))
        except Exception: pass
    return rows[-limit:]
def visual_status() -> Dict[str, Any]:
    rows=read_visual_events(200)
    return {"ledger": str(LEDGER), "events": len(rows), "last_event": rows[-1] if rows else None}
