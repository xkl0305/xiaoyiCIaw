from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


class LocalProvider(Protocol):
    name: str
    capability: str
    def ready(self, ctx: Dict[str, Any]) -> bool: ...
    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]: ...


@dataclass
class LocalProviderResult:
    status: str
    capability: str
    provider: str
    output: Any = None
    blocked: bool = False
    blocked_reason: str = ''
    metadata: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'capability': self.capability,
            'provider': self.provider,
            'output': self.output,
            'blocked': self.blocked,
            'blocked_reason': self.blocked_reason,
            'metadata': self.metadata or {},
        }


class UnavailableLocalProvider:
    def __init__(self, name: str, capability: str):
        self.name = name
        self.capability = capability

    def ready(self, ctx: Dict[str, Any]) -> bool:
        return False

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return LocalProviderResult(
            status='blocked', capability=self.capability, provider=self.name,
            blocked=True, blocked_reason='local_capability_not_available',
            metadata={'allow_external_fallback': False}
        ).to_dict()
