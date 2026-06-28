"""V85 LLM model decision engine.

Public entry points:
- init_model_system()
- auto_route()/route_message()
- LLMGateway.call() or core.llm.call()
- registry / register_model_external()
"""

from __future__ import annotations

import typing

from core.llm.schemas import (
    Complexity,
    CostPreference,
    LatencyPreference,
    ModelInfo,
    ModelType,
    PrivacyLevel,
    Provider,
    RouteDecision,
    TaskCategory,
    TaskProfile,
)
from core.llm.model_registry import registry, Cost, Latency
from core.llm.model_discovery import discover_and_register, register_model_external, update_availability
__all__ = [
    "registry",
    "ModelInfo",
    "ModelType",
    "Provider",
    "TaskProfile",
    "TaskCategory",
    "Complexity",
    "CostPreference",
    "LatencyPreference",
    "PrivacyLevel",
    "RouteDecision",
    "discover_and_register",
    "register_model_external",
    "update_availability",
    "auto_route",
    "route_message",
    "init_model_system",
    "get_switch_history",
    "LLMGateway",
    "GatewayResult",
    "call",
    "Cost",
    "Latency",
]

_LazyModule = typing.Any


def __getattr__(name: str) -> _LazyModule:
    """Deferred import to break circular import between core.llm and core.llm_gateway."""
    if name in ("auto_route", "route_message", "init_model_system", "get_switch_history"):
        import core.llm_gateway.model_router as _mr
        return getattr(_mr, name)
    if name in ("LLMGateway", "GatewayResult", "call"):
        import core.llm_gateway.llm_gateway as _gw
        return getattr(_gw, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
