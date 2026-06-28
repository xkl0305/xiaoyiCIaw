from __future__ import annotations
import json, time, importlib.util, traceback
from pathlib import Path
from typing import Any, Dict
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".openclaw" / "hook_state"
HOOKS = ROOT / ".openclaw" / "hooks"
def _log(event: str, payload: Dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "event": event, **payload}
    with (STATE / "hook_events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
def is_enabled() -> bool:
    return (HOOKS / "enabled").exists() or (HOOKS / "manifest.json").exists()
def _load(path: Path):
    spec = importlib.util.spec_from_file_location("openclaw_hook_" + path.stem, path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def dispatch(event: str, **kwargs: Any) -> Dict[str, Any]:
    if not is_enabled():
        _log(event, {"status": "disabled"})
        return {"status": "disabled", "event": event}
    path = HOOKS / f"{event}.py"
    if not path.exists():
        _log(event, {"status": "missing", "path": str(path)})
        return {"status": "missing", "event": event, "path": str(path)}
    try:
        mod = _load(path)
        fn = getattr(mod, "run", None)
        if not callable(fn):
            raise RuntimeError(f"hook {event} has no run()")
        res = fn(**kwargs)
        if not isinstance(res, dict):
            res = {"result": res}
        out = {"status": res.get("status", "ok"), "event": event, **res}
        _log(event, out)
        return out
    except Exception as e:
        out = {
            "status": "fail_soft",
            "event": event,
            "error": str(e),
            "traceback": traceback.format_exc()[-2000:],
        }
        _log(event, out)
        return out
def status() -> Dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "hooks_dir": str(HOOKS),
        "manifest": (HOOKS / "manifest.json").exists(),
        "pre_reply": (HOOKS / "pre_reply.py").exists(),
        "post_reply": (HOOKS / "post_reply.py").exists(),
    }
