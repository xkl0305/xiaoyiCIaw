"""
Crusheart capability registry — 声明系统有哪些核心能力。
借鉴 Enterprise capability_types.py + local_capability_registry.py + local_model_registry.py
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

# ── 能力类型常量 ──
CAP_ENGINE_INIT = 'engine_init'
CAP_MEMORY = 'memory_system'
CAP_SKILL_ENGINE = 'skill_engine'
CAP_TASK_SCHEDULER = 'task_scheduler'
CAP_PLANNER = 'planner'
CAP_WORKFLOW = 'workflow_orchestrator'
CAP_LOCAL_LLM = 'local_llm'

REQUIRED_CAPABILITIES = {CAP_ENGINE_INIT, CAP_MEMORY, CAP_SKILL_ENGINE, CAP_PLANNER}
OPTIONAL_CAPABILITIES = {CAP_TASK_SCHEDULER, CAP_WORKFLOW, CAP_LOCAL_LLM}
ALL_CAPABILITIES = REQUIRED_CAPABILITIES | OPTIONAL_CAPABILITIES


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    kind: str
    status: str = 'declared'          # declared | active | degraded | disabled
    required: bool = True
    description: str = ''
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name, 'kind': self.kind, 'status': self.status,
            'required': self.required, 'description': self.description,
            'tags': list(self.tags),
        }


# ── 默认能力注册表 ──
DEFAULT_CAPABILITIES: Dict[str, CapabilitySpec] = {
    CAP_ENGINE_INIT: CapabilitySpec(
        name=CAP_ENGINE_INIT, kind='engine_group', status='declared', required=True,
        description='7 组引擎初始化（init/memory/quality/operations/workflow/hooks/tools）',
        tags=['bootstrap', 'core'],
    ),
    CAP_MEMORY: CapabilitySpec(
        name=CAP_MEMORY, kind='memory', status='declared', required=True,
        description='五层记忆体系（L0-L5）：倒排索引 + 向量检索 + 场景分组 + 梦境固化',
        tags=['memory', 'persistence'],
    ),
    CAP_SKILL_ENGINE: CapabilitySpec(
        name=CAP_SKILL_ENGINE, kind='execution', status='declared', required=True,
        description='技能加载与执行引擎',
        tags=['skill', 'execution'],
    ),
    CAP_PLANNER: CapabilitySpec(
        name=CAP_PLANNER, kind='planner', status='declared', required=True,
        description='planner 管线（goal_parser → task_decomposer → route_selector → plan_to_graph）',
        tags=['planner', 'orchestration'],
    ),
    CAP_TASK_SCHEDULER: CapabilitySpec(
        name=CAP_TASK_SCHEDULER, kind='scheduler', status='declared', required=False,
        description='定时任务调度器（cron）',
        tags=['scheduler', 'automation'],
    ),
    CAP_WORKFLOW: CapabilitySpec(
        name=CAP_WORKFLOW, kind='workflow', status='declared', required=False,
        description='WorkflowOrchestrator 工作流编排',
        tags=['workflow', 'orchestration'],
    ),
    CAP_LOCAL_LLM: CapabilitySpec(
        name=CAP_LOCAL_LLM, kind='inference', status='declared', required=False,
        description='本地推理模型（可选，当前使用 cloud provider）',
        tags=['inference', 'local_model'],
    ),
}


def list_capabilities(include_optional: bool = True) -> Dict[str, Dict[str, Any]]:
    result = {}
    for name, spec in DEFAULT_CAPABILITIES.items():
        if include_optional or spec.required:
            result[name] = spec.to_dict()
    return result


def get_capability(name: str) -> Optional[Dict[str, Any]]:
    spec = DEFAULT_CAPABILITIES.get(name)
    return spec.to_dict() if spec else None


def assert_declared_capabilities() -> Dict[str, Any]:
    missing = [c for c in REQUIRED_CAPABILITIES if c not in DEFAULT_CAPABILITIES]
    missing_status = [c for c, s in DEFAULT_CAPABILITIES.items() if s.status not in {'declared', 'active'}]
    return {
        'ok': not missing and not missing_status,
        'count': len(DEFAULT_CAPABILITIES),
        'required': sorted(REQUIRED_CAPABILITIES),
        'optional': sorted(OPTIONAL_CAPABILITIES),
        'missing': missing,
        'status_issues': missing_status,
    }
