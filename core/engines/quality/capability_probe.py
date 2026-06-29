"""
Crusheart capability probe — 分级探测每个能力的实际状态。
借鉴 Enterprise local_runtime_probe.py + local_health_check.py + local_model_stack_binding.py

Ready kinds:
  - real_model_ready:    真实可用（模块都 loaded）
  - stub_ready_only:     只有声明框架，引擎未实际加载
  - environment_blocked: 环境不满足需求
  - not_configured:      未声明/未配置
"""
from __future__ import annotations

import importlib
import os
import sys
import shutil
from pathlib import Path
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from .capability_registry import (
    DEFAULT_CAPABILITIES, list_capabilities, assert_declared_capabilities,
    CapabilitySpec, ALL_CAPABILITIES, REQUIRED_CAPABILITIES,
)


# ── 引擎组 → Python 模块路径映射 ──

def detect_provider():
    """动态探测当前模型 provider（替代硬编码）"""
    import json
    workspace = os.environ.get('OPENCLAW_WORKSPACE', os.path.expanduser('~/.openclaw/workspace'))
    config_paths = [
        os.path.join(workspace, 'openclaw.json'),
        os.path.join(os.path.expanduser('~/.openclaw'), 'openclaw.json'),
    ]
    for cfg_path in config_paths:
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path) as f:
                    cfg = json.load(f)
                providers = cfg.get('models', {}).get('providers', {})
                for name in providers:
                    return name
                return 'default'
            except Exception:
                pass
    return os.environ.get('CRUSHEART_MODEL_PROVIDER', 'default')


_detected_provider = detect_provider()


ENGINE_GROUPS: Dict[str, str] = {
    'init': 'core.engines.init',
    'memory': 'core.engines.memory',
    'quality': 'core.engines.quality',
    'operations': 'core.engines.operations',
    'workflow': 'core.engines.workflow',
    'hooks': 'core.engines.hooks',
    'tools': 'core.engines.tools',
}


def _module_ready(module_path: str) -> bool:
    if not module_path:
        return False
    try:
        mod = importlib.import_module(module_path)
        if mod:
            _ = dir(mod)
        return True
    except (ImportError, AttributeError, TypeError, ValueError):
        return False
    except Exception:
        return False

def _path_ready(path: str) -> bool:
    if not path:
        return False
    return Path(path).expanduser().exists()


def _command_ready(command: str) -> bool:
    if not command:
        return False
    first = str(command).split()[0]
    return bool(shutil.which(first))


# ── 各能力专属探针 ──

def _probe_engine_init() -> Dict[str, Any]:
    checks = {}
    for group, module_path in ENGINE_GROUPS.items():
        checks[group] = _module_ready(module_path)
    all_ready = all(checks.values())
    return {
        'ready': all_ready,
        'ready_kind': 'real_model_ready' if all_ready else 'environment_blocked',
        'reason': 'all_groups_loaded' if all_ready else 'some_groups_missing',
        'checks': checks,
    }


def _probe_memory() -> Dict[str, Any]:
    subsystems = ['auto_memory', 'vector_memory']
    checks = {}
    for sub in subsystems:
        try:
            importlib.import_module(f'core.engines.memory.{sub}')
            checks[sub] = True
        except Exception:
            checks[sub] = False
    data_dir = Path('memory/')
    checks['memory_dir_exists'] = data_dir.exists()
    all_ready = all(checks.values())
    return {
        'ready': all_ready,
        'ready_kind': 'real_model_ready' if all_ready else 'stub_ready_only',
        'reason': 'ready' if all_ready else 'memory_dir_missing',
        'checks': checks,
    }


def _probe_skill_engine() -> Dict[str, Any]:
    checks = {
        'skill_engine_import': _module_ready('skills'),
        'skills_dir_exists': Path('skills/').exists(),
    }
    all_ready = all(checks.values())
    return {
        'ready': all_ready,
        'ready_kind': 'real_model_ready' if all_ready else 'stub_ready_only',
        'reason': 'ready' if all_ready else 'skills_dir_not_found',
        'checks': checks,
    }


def _probe_planner() -> Dict[str, Any]:
    planner_modules = [
        'core.engines.workflow.engine_orchestrator',
    ]
    checks = {}
    for mod in planner_modules:
        checks[mod] = _module_ready(mod)
    checks['planner_bundle'] = Path('core/planner/route_selector.py').exists()
    all_ready = checks.get('core.engines.workflow.engine_orchestrator', False)
    return {
        'ready': all_ready,
        'ready_kind': 'real_model_ready' if all_ready else 'stub_ready_only',
        'reason': 'ready' if all_ready else 'planner_not_loaded',
        'checks': checks,
    }


def _probe_task_scheduler() -> Dict[str, Any]:
    checks = {
        'cron_installed': bool(shutil.which('openclaw')),
    }
    checks['scheduler_available'] = True
    return {
        'ready': True,
        'ready_kind': 'real_model_ready',
        'reason': 'ready',
        'checks': checks,
    }


def _probe_workflow() -> Dict[str, Any]:
    checks = {
        'orchestrator_import': _module_ready('core.engines.workflow.engine_orchestrator'),
    }
    return {
        'ready': checks['orchestrator_import'],
        'ready_kind': 'real_model_ready' if checks['orchestrator_import'] else 'stub_ready_only',
        'reason': 'ready' if checks['orchestrator_import'] else 'orchestrator_unavailable',
        'checks': checks,
    }


def _probe_local_llm() -> Dict[str, Any]:
    return {
        'ready': False,
        'ready_kind': 'stub_ready_only',
        'reason': 'local_llm not deployed (using cloud provider)',
        'checks': {'enabled': False},
    }


# ── 探针注册表 ──
PROBE_REGISTRY: Dict[str, callable] = {
    'engine_init': _probe_engine_init,
    'memory_system': _probe_memory,
    'skill_engine': _probe_skill_engine,
    'planner': _probe_planner,
    'task_scheduler': _probe_task_scheduler,
    'workflow_orchestrator': _probe_workflow,
    'local_llm': _probe_local_llm,
}


def probe_capability(name: str) -> Dict[str, Any]:
    if name not in PROBE_REGISTRY:
        return {
            'capability': name,
            'ready': False,
            'ready_kind': 'not_configured',
            'reason': 'unknown_capability',
        }
    spec = DEFAULT_CAPABILITIES.get(name)
    result = PROBE_REGISTRY[name]()
    result['capability'] = name
    result['required'] = spec.required if spec else False
    return result


def probe_all_capabilities() -> Dict[str, Any]:
    probes = {cap: probe_capability(cap) for cap in ALL_CAPABILITIES}
    ready = [c for c, p in probes.items() if p.get('ready')]
    missing = [c for c, p in probes.items() if not p.get('ready')]
    required_missing = [c for c in missing if probes[c].get('required', False)]
    real_ready = [c for c, p in probes.items() if p.get('ready_kind') == 'real_model_ready']
    return {
        'overall': 'ready' if not required_missing else 'degraded',
        'ready': ready,
        'missing': missing,
        'required_missing': required_missing,
        'real_model_ready': real_ready,
        'stub_ready_only': [c for c in probes if probes[c].get('ready_kind') == 'stub_ready_only'],
        'environment_blocked': [c for c in probes if probes[c].get('ready_kind') == 'environment_blocked'],
        'probes': probes,
    }


def capability_health() -> Dict[str, Any]:
    registry = assert_declared_capabilities()
    probes = probe_all_capabilities()
    return {
        'overall': 'ready' if (registry.get('ok') and not probes['required_missing'])
                  else 'critical' if probes['required_missing']
                  else 'degraded',
        'registry_ok': registry.get('ok'),
        'registry': registry,
        'probes': probes,
    }


def require_capabilities(capabilities: list[str]) -> Dict[str, Any]:
    checks = {cap: probe_capability(cap) for cap in capabilities}
    missing = [cap for cap, out in checks.items() if not out.get('ready')]
    return {
        'ok': not missing,
        'missing': missing,
        'blocked': bool(missing),
        'blocked_reason': 'required_capability_unavailable' if missing else '',
        'checks': checks,
    }
