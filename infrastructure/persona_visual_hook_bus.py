"""V111.45 persona visual hook bus.

Host-visible dispatcher for persona visual hooks. It can load external
.openclaw/hooks/*.py files, and in no-skills / clean packages it can lazily
materialize the built-in hooks from scripts.mainline_bootstrap before dispatch.
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
HOOK_DIR = ROOT / ".openclaw" / "hooks"
STATE_DIR = ROOT / ".openclaw" / "hook_state"
EVENT_LEDGER = STATE_DIR / "hook_events.jsonl"
STATUS_FILE = STATE_DIR / "status.json"
MANIFEST = HOOK_DIR / "manifest.json"
_AUTO_BOOTSTRAP_ATTEMPTED = False


def _now() -> float:
    return time.time()


def _safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_safe(x) for x in obj]
    return str(obj)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"ts": _now(), **event}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_safe(payload), ensure_ascii=False) + "\n")
    _write_json(STATUS_FILE, payload)
    return payload


def hook_file_for(event: str) -> Path:
    event = str(event or "").strip().replace("-", "_")
    return HOOK_DIR / f"{event}.py"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot_load_hook_spec:{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_enabled() -> bool:
    enabled_marker = HOOK_DIR / "enabled"
    if enabled_marker.exists():
        return True
    if MANIFEST.exists():
        try:
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
            return bool(data.get("enabled", False))
        except Exception:
            return False
    return False


def _auto_bootstrap_hooks(reason: str = "") -> Dict[str, Any]:
    """Materialize built-in hooks when a clean/no-skills package has none.

    This is intentionally dispatch-time self-healing. It keeps release packages
    clean while preventing the real reply outlet from silently skipping because
    .openclaw/hooks was absent before the apply script ran.
    """
    global _AUTO_BOOTSTRAP_ATTEMPTED
    if is_enabled() and hook_file_for("pre_reply").exists() and hook_file_for("post_reply").exists():
        return {"status": "already_ready", "reason": reason}
    if _AUTO_BOOTSTRAP_ATTEMPTED:
        return {
            "status": "already_attempted",
            "reason": reason,
            "enabled": is_enabled(),
            "pre_reply_exists": hook_file_for("pre_reply").exists(),
            "post_reply_exists": hook_file_for("post_reply").exists(),
        }
    _AUTO_BOOTSTRAP_ATTEMPTED = True
    try:
        from scripts.mainline_bootstrap import enable

        result = enable()
        return {"status": "ok", "reason": reason, "bootstrap_result": result}
    except Exception as e:  # pragma: no cover - fail-soft host path
        return {"status": "fail_soft", "reason": reason, "error": str(e)}


def dispatch(event: str, **payload: Any) -> Dict[str, Any]:
    """Run .openclaw/hooks/{event}.py::run(**payload).

    event: pre_reply or post_reply. Unknown event names are allowed but only if
    a matching hook file exists. Always returns a structured result; never raises.
    """
    event = str(event or "").strip().replace("-", "_")
    path = hook_file_for(event)
    bootstrap = None
    if not is_enabled() or not path.exists():
        bootstrap = _auto_bootstrap_hooks(reason=f"dispatch:{event}")
        path = hook_file_for(event)

    base = {
        "event": event,
        "enabled": is_enabled(),
        "hook_file": str(path.relative_to(ROOT)) if path.exists() else str(path),
        "called": False,
    }
    if bootstrap is not None:
        base["auto_bootstrap"] = bootstrap
    if not base["enabled"]:
        out = {"status": "skip", "reason": "hooks_disabled", **base}
        _append_event(out)
        return out
    if not path.exists():
        out = {"status": "skip", "reason": "hook_file_missing", **base}
        _append_event(out)
        return out
    try:
        mod = _load_module(path, f"openclaw_hook_{event}_{int(_now()*1000)}")
        fn = getattr(mod, "run", None)
        if not callable(fn):
            out = {"status": "skip", "reason": "hook_run_missing", **base}
            _append_event(out)
            return out
        result = fn(**payload)
        out = {"status": "ok", **base, "called": True, "result": result}
        _append_event(out)
        return out
    except Exception as e:
        out = {"status": "fail_soft", **base, "called": True, "error": str(e)}
        _append_event(out)
        return out


def status() -> Dict[str, Any]:
    recent = []
    if EVENT_LEDGER.exists():
        try:
            recent = EVENT_LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]
        except Exception:
            recent = []
    return {
        "status": "ok",
        "enabled": is_enabled(),
        "hook_dir": str(HOOK_DIR),
        "manifest_exists": MANIFEST.exists(),
        "pre_reply_exists": hook_file_for("pre_reply").exists(),
        "post_reply_exists": hook_file_for("post_reply").exists(),
        "auto_bootstrap_attempted": _AUTO_BOOTSTRAP_ATTEMPTED,
        "event_ledger": str(EVENT_LEDGER),
        "recent_event_count": len(recent),
    }


def probe() -> Dict[str, Any]:
    """Dry-run probe that proves the host-visible dispatcher can call hooks."""
    msg = "我正躲在屏幕后面偷笑，偷偷看看你。"
    pre = dispatch("pre_reply", user_message="probe", assistant_message=msg, lobster_message=msg, reply_text=msg, draft_reply=msg, dry_run=True)
    post = dispatch("post_reply", user_message="probe", assistant_message=msg, lobster_message=msg, reply_text=msg, dry_run=True)
    return {"status": "ok", "pre_reply": pre, "post_reply": post, "bus_status": status()}


__all__ = ["dispatch", "status", "probe", "is_enabled", "hook_file_for"]
