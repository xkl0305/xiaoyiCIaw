from __future__ import annotations
"""No-skills compatibility import layer.

The V111 no-skills package deliberately does not ship a physical ``skills/``
directory.  Older integration tests and a few legacy imports still expect
``skills.*`` modules.  This shim provides an in-memory compatibility facade
without reintroducing a physical skills directory or making physical skills a
runtime requirement.
"""

from dataclasses import dataclass
from enum import Enum
import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
_INSTALLED = False


class SkillRegistry:
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or ROOT / "infrastructure" / "inventory" / "skill_registry.json"
        self._skills: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            skills = data.get("skills", {}) if isinstance(data, dict) else {}
            self._skills = skills if isinstance(skills, dict) else {}
        except Exception:
            self._skills = {}

    def list_skills(self) -> List[str]:
        return sorted(self._skills)

    def get(self, skill_id: str, default: Any = None) -> Any:
        return self._skills.get(skill_id, default)

    def register(self, skill_id: str, metadata: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        entry = {"skill_id": skill_id, **(metadata or {}), **kwargs}
        self._skills[skill_id] = entry
        return entry

    def discover(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._skills)

    def has_skill(self, skill_id: str) -> bool:
        return skill_id in self._skills


_GLOBAL_REGISTRY = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    return _GLOBAL_REGISTRY


@dataclass
class LoadResult:
    success: bool
    skill_id: str = ""
    version: str = ""
    package: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SkillPackageLoader:
    def load_from_path(self, path: Path | str) -> LoadResult:
        path = Path(path)
        package_path = path / "package.json"
        if not package_path.exists():
            return LoadResult(success=False, error="missing_package_json")
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return LoadResult(success=False, error=f"invalid_package_json:{exc}")
        skill_id = str(package.get("skill_id") or path.name)
        version = str(package.get("version") or "0.0.0")
        get_skill_registry().register(skill_id, package)
        return LoadResult(success=True, skill_id=skill_id, version=version, package=package)


class SkillDependencyResolver:
    def __init__(self):
        self._deps: Dict[str, set[str]] = {}

    def add_dependency(self, skill_id: str, dependency_id: str) -> None:
        self._deps.setdefault(skill_id, set()).add(dependency_id)

    def register_dependencies(self, skill_id: str, dependencies: Iterable[str]) -> None:
        self._deps[skill_id] = set(dependencies)

    def get_dependencies(self, skill_id: str) -> List[str]:
        return sorted(self._deps.get(skill_id, set()))

    def get_dependents(self, dependency_id: str) -> List[str]:
        return sorted(skill for skill, deps in self._deps.items() if dependency_id in deps)

    def can_remove(self, skill_id: str) -> bool:
        return not self.get_dependents(skill_id)


class VersionStrategy(str, Enum):
    LATEST = "latest"
    STABLE = "stable"
    PINNED = "pinned"


class SkillVersionSelector:
    def __init__(self):
        self._versions: Dict[str, List[Dict[str, Any]]] = {}

    def register_version(self, skill_id: str, version: str, stable: bool = False, **metadata: Any) -> None:
        self._versions.setdefault(skill_id, []).append({"version": version, "stable": stable, **metadata})

    @staticmethod
    def _version_key(version: str) -> tuple:
        parts: List[Any] = []
        for piece in str(version).replace("-", ".").split("."):
            parts.append(int(piece) if piece.isdigit() else piece)
        return tuple(parts)

    def get_latest(self, skill_id: str) -> Optional[str]:
        items = self._versions.get(skill_id, [])
        if not items:
            return None
        return max((str(i["version"]) for i in items), key=self._version_key)

    def get_stable(self, skill_id: str) -> Optional[str]:
        stable = [str(i["version"]) for i in self._versions.get(skill_id, []) if i.get("stable")]
        if not stable:
            return self.get_latest(skill_id)
        return max(stable, key=self._version_key)

    def select(self, skill_id: str, strategy: VersionStrategy | str = VersionStrategy.LATEST, pinned_version: Optional[str] = None) -> Optional[str]:
        strategy_value = strategy.value if isinstance(strategy, VersionStrategy) else str(strategy)
        if strategy_value == VersionStrategy.PINNED.value:
            return pinned_version
        if strategy_value == VersionStrategy.STABLE.value:
            return self.get_stable(skill_id)
        return self.get_latest(skill_id)


@dataclass
class CompatibilityResult:
    compatible: bool
    reason: str = "ok"


class CompatibilityManager:
    def __init__(self):
        self._compat: Dict[tuple[str, str], CompatibilityResult] = {}

    def register(self, skill_id: str, version: str, compatible: bool = True, reason: str = "ok") -> None:
        self._compat[(skill_id, version)] = CompatibilityResult(bool(compatible), reason)

    def check(self, skill_id: str, version: str) -> CompatibilityResult:
        return self._compat.get((skill_id, version), CompatibilityResult(True, "default_compatible"))

    def is_compatible(self, skill_id: str, version: str) -> bool:
        return bool(self.check(skill_id, version).compatible)


class LifecycleManager:
    def __init__(self):
        self._states: Dict[str, str] = {}

    def set_status(self, skill_id: str, status: str) -> None:
        self._states[skill_id] = status

    def get_status(self, skill_id: str) -> str:
        return self._states.get(skill_id, "active")


_GLOBAL_LIFECYCLE = LifecycleManager()


def get_lifecycle_manager() -> LifecycleManager:
    return _GLOBAL_LIFECYCLE


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class SkillHealth:
    skill_id: str
    status: HealthStatus
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0.0


class SkillHealthMonitor:
    def __init__(self):
        self._health: Dict[str, SkillHealth] = {}

    def record_execution(self, skill_id: str, success: bool, duration_ms: float = 0.0) -> None:
        current = self._health.get(skill_id, SkillHealth(skill_id, HealthStatus.UNKNOWN))
        total = current.success_count + current.failure_count
        current.avg_duration_ms = ((current.avg_duration_ms * total) + float(duration_ms)) / (total + 1)
        if success:
            current.success_count += 1
        else:
            current.failure_count += 1
        current.status = HealthStatus.HEALTHY if success else HealthStatus.DEGRADED
        self._health[skill_id] = current

    def get_health(self, skill_id: str) -> SkillHealth:
        return self._health.get(skill_id, SkillHealth(skill_id, HealthStatus.UNKNOWN))


class SkillRouter:
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or get_skill_registry()

    def select_skill(self, task: str, profile: str = "default") -> Optional[str]:
        skills = self.registry.list_skills()
        return skills[0] if skills else None


_GLOBAL_ROUTER = SkillRouter()


def get_skill_router() -> SkillRouter:
    return _GLOBAL_ROUTER


def _new_module(name: str, package: bool = False, attrs: Optional[Dict[str, Any]] = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    if package:
        mod.__path__ = []  # type: ignore[attr-defined]
    if attrs:
        for key, value in attrs.items():
            setattr(mod, key, value)
    return mod


def _provider_module() -> types.ModuleType:
    provider = importlib.import_module("memory_context.persona_runtime.providers.seedream_provider")
    return _new_module(
        "skills.seedream_image_gen.scripts.generate_seedream",
        attrs={
            "generate_image": getattr(provider, "generate_image"),
            "provider_ready": getattr(provider, "provider_ready", lambda: False),
            "provider_env": getattr(provider, "provider_env", lambda *args, **kwargs: {}),
        },
    )


def install() -> Dict[str, Any]:
    global _INSTALLED
    if _INSTALLED:
        return {"status": "already_installed", "physical_skills_dir_present": (ROOT / "skills").exists()}

    modules: Dict[str, types.ModuleType] = {
        "skills": _new_module("skills", package=True, attrs={"__no_physical_skills__": True}),
        "skills.registry": _new_module("skills.registry", attrs={"SkillRegistry": SkillRegistry, "get_skill_registry": get_skill_registry}),
        "skills.runtime": _new_module("skills.runtime", package=True, attrs={
            "SkillRouter": SkillRouter,
            "get_skill_router": get_skill_router,
            "SkillHealthMonitor": SkillHealthMonitor,
            "HealthStatus": HealthStatus,
            "SkillPackageLoader": SkillPackageLoader,
            "LoadResult": LoadResult,
            "SkillDependencyResolver": SkillDependencyResolver,
            "SkillVersionSelector": SkillVersionSelector,
            "VersionStrategy": VersionStrategy,
        }),
        "skills.runtime.skill_router": _new_module("skills.runtime.skill_router", attrs={"SkillRouter": SkillRouter, "get_skill_router": get_skill_router}),
        "skills.runtime.skill_package_loader": _new_module("skills.runtime.skill_package_loader", attrs={"SkillPackageLoader": SkillPackageLoader, "LoadResult": LoadResult}),
        "skills.runtime.skill_dependency_resolver": _new_module("skills.runtime.skill_dependency_resolver", attrs={"SkillDependencyResolver": SkillDependencyResolver}),
        "skills.runtime.skill_version_selector": _new_module("skills.runtime.skill_version_selector", attrs={"SkillVersionSelector": SkillVersionSelector, "VersionStrategy": VersionStrategy}),
        "skills.runtime.skill_health_monitor": _new_module("skills.runtime.skill_health_monitor", attrs={"SkillHealthMonitor": SkillHealthMonitor, "HealthStatus": HealthStatus, "SkillHealth": SkillHealth}),
        "skills.lifecycle": _new_module("skills.lifecycle", package=True, attrs={"LifecycleManager": LifecycleManager, "get_lifecycle_manager": get_lifecycle_manager, "CompatibilityManager": CompatibilityManager}),
        "skills.lifecycle.compatibility_manager": _new_module("skills.lifecycle.compatibility_manager", attrs={"CompatibilityManager": CompatibilityManager, "CompatibilityResult": CompatibilityResult}),
        "skills.seedream_image_gen": _new_module("skills.seedream_image_gen", package=True),
        "skills.seedream_image_gen.scripts": _new_module("skills.seedream_image_gen.scripts", package=True),
        "skills.seedream_image_gen.scripts.generate_seedream": _provider_module(),
    }
    for name, module in modules.items():
        sys.modules.setdefault(name, module)

    # Expose child modules as attributes on their parents.  This is required
    # when the top-level `skills` package is provided by skills.py rather than
    # by an on-disk package directory.
    for name in sorted(modules, key=lambda x: x.count('.')):
        if '.' not in name:
            continue
        parent_name, child_name = name.rsplit('.', 1)
        parent = sys.modules.get(parent_name)
        child = sys.modules.get(name)
        if parent is not None and child is not None and not hasattr(parent, child_name):
            setattr(parent, child_name, child)

    top = sys.modules.get('skills')
    if top is not None:
        setattr(top, '__path__', getattr(top, '__path__', []))
        setattr(top, '__no_physical_skills__', True)

    _INSTALLED = True
    return {"status": "installed", "physical_skills_dir_present": (ROOT / "skills").exists(), "modules": sorted(modules)}


__all__ = [
    "install",
    "SkillRegistry",
    "get_skill_registry",
    "SkillRouter",
    "get_skill_router",
    "SkillPackageLoader",
    "LoadResult",
    "SkillDependencyResolver",
    "SkillVersionSelector",
    "VersionStrategy",
    "CompatibilityManager",
    "CompatibilityResult",
    "LifecycleManager",
    "get_lifecycle_manager",
    "SkillHealthMonitor",
    "HealthStatus",
    "SkillHealth",
]
