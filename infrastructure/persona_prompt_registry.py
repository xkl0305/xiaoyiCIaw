from __future__ import annotations

from typing import Any, Callable, Dict

_PROMPT_BUILDERS: Dict[str, Callable[..., Any]] = {}
_METADATA: Dict[str, Dict[str, Any]] = {}


def register_prompt_builder(name: str, builder: Callable[..., Any], metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not name:
        raise ValueError('prompt builder name is required')
    if not callable(builder):
        raise TypeError('prompt builder must be callable')
    _PROMPT_BUILDERS[name] = builder
    _METADATA[name] = dict(metadata or {})
    return {'registered': True, 'name': name, 'total': len(_PROMPT_BUILDERS)}


def get_prompt_builder(name: str) -> Callable[..., Any] | None:
    return _PROMPT_BUILDERS.get(name)


def list_prompt_builders() -> Dict[str, Dict[str, Any]]:
    return {name: dict(_METADATA.get(name, {})) for name in _PROMPT_BUILDERS}


def clear_prompt_builders() -> None:
    _PROMPT_BUILDERS.clear()
    _METADATA.clear()
