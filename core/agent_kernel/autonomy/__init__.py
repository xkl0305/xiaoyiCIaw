"""Canonical public exports for core.agent_kernel.autonomy.

V111.22:
- keep canonical package exports complete
- preserve compatibility aliases
- eliminate need to import from duplicated nested autonomy package
"""

from core.agent_kernel.autonomy.goal_strategy_kernel import GoalStrategyKernel
from core.agent_kernel.autonomy.autonomy_orchestrator import (
    AutonomyOrchestrator,
    run_autonomy_cycle,
    init_autonomy_system,
)
from core.agent_kernel.autonomy.memory_kernel import MemoryKernel
from core.agent_kernel.autonomy.world_interface import WorldInterface
from core.agent_kernel.autonomy.capability_gap import CapabilityGapAnalyzer
from core.agent_kernel.autonomy.extension_sandbox import ExtensionSandbox
from core.agent_kernel.autonomy.approval_interrupt import ApprovalInterruptManager
from core.agent_kernel.autonomy.trace_audit import TraceAudit
from core.agent_kernel.autonomy.quality_evaluator import QualityEvaluator
from core.agent_kernel.autonomy.strategy_evolver import StrategyEvolver
from core.agent_kernel.autonomy.continuous_task_runner import ContinuousTaskRunner
from core.agent_kernel.autonomy.task_graph_compiler import TaskGraphCompiler
from core.agent_kernel.autonomy.schemas import (
    RiskLevel,
    MemoryKind,
    ConnectorKind,
    CapabilityGapStatus,
    ExtensionStatus,
    ApprovalStatus,
    TaskRunStatus,
    MemoryRecord,
    ConnectorSpec,
    CapabilityGap,
    ExtensionProposal,
    ApprovalTicket,
    TraceEvent,
    QualityReport,
    StrategyRule,
    ContinuousTask,
    AutonomyCycleResult,
)


class GoalState:
    """Compatibility alias. Use GoalStrategyKernel or TaskRunStatus for state management."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalLifecycle:
    """Compatibility alias. Manages goal lifecycle stages."""
    INIT = "init"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    DONE = "done"


class AutonomyConfig:
    """Compatibility alias. Configuration container for autonomy system."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


AutonomyController = AutonomyOrchestrator


__all__ = [
    "GoalStrategyKernel",
    "AutonomyOrchestrator",
    "AutonomyController",
    "run_autonomy_cycle",
    "init_autonomy_system",
    "MemoryKernel",
    "WorldInterface",
    "CapabilityGapAnalyzer",
    "ExtensionSandbox",
    "ApprovalInterruptManager",
    "TraceAudit",
    "QualityEvaluator",
    "StrategyEvolver",
    "ContinuousTaskRunner",
    "TaskGraphCompiler",
    "GoalState",
    "GoalLifecycle",
    "AutonomyConfig",
    "RiskLevel", "MemoryKind", "ConnectorKind",
    "CapabilityGapStatus", "ExtensionStatus", "ApprovalStatus", "TaskRunStatus",
    "MemoryRecord", "ConnectorSpec", "CapabilityGap", "ExtensionProposal",
    "ApprovalTicket", "TraceEvent", "QualityReport", "StrategyRule",
    "ContinuousTask", "AutonomyCycleResult",
]
