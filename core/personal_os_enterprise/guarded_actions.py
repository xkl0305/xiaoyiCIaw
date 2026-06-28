from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .side_effect_gateway import prepare_side_effect, execute_side_effect


def guarded_file_write(path: str | Path, content: str, *, proof: Optional[Dict[str, Any]] = None, root=None) -> Dict[str, Any]:
    target = Path(path)
    payload = {"path": str(target), "content_sha_hint": len(content or "")}
    def _write(_: Any) -> Dict[str, Any]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content or "", encoding="utf-8")
        return {"written": True, "path": str(target)}
    return execute_side_effect(action_type="file_write", payload=payload, proof=proof, executor=_write, root=root)


def prepare_file_write(path: str | Path, content: str, *, root=None) -> Dict[str, Any]:
    payload = {"path": str(Path(path)), "content_sha_hint": len(content or "")}
    return prepare_side_effect(action_type="file_write", payload=payload, risk_level="medium", entrypoint="guarded_file_write", root=root)


def guarded_memory_write(key: str, value: Any, *, proof: Optional[Dict[str, Any]] = None, writer=None, root=None) -> Dict[str, Any]:
    payload = {"key": key, "value_type": type(value).__name__}
    def _write(_: Any) -> Any:
        if writer is None:
            return {"memory_write": "noop", "key": key}
        return writer(key, value)
    return execute_side_effect(action_type="memory_write", payload=payload, proof=proof, executor=_write, root=root)


def prepare_memory_write(key: str, value: Any, *, root=None) -> Dict[str, Any]:
    payload = {"key": key, "value_type": type(value).__name__}
    return prepare_side_effect(action_type="memory_write", payload=payload, risk_level="medium", entrypoint="guarded_memory_write", root=root)
