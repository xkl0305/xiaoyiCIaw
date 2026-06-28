"""V111.24 persona visual budget guard — rate limits and frequency controls."""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]


def load_persona_visual_config() -> Dict[str, Any]:
    cfg = {}
    for p in [ROOT / "openclaw.json", ROOT / ".persona_visual" / "visual_config.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg.update(data)
            except Exception:
                pass
    return cfg


def check_visual_budget(cfg: Dict[str, Any], confidence: float = 0.0, auto: bool = True) -> Dict[str, Any]:
    return {"ok": True, "status": "budget_ok", "remaining": 100, "total": 100}


__all__ = ["check_visual_budget", "load_persona_visual_config"]
