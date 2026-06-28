"""Canonical public exports for core.agent_kernel.personal_agent.

V111.22:
- keep canonical package exports complete
- preserve compatibility aliases
- eliminate need to import from duplicated nested personal_agent package
"""

from core.agent_kernel.personal_agent.goal_compiler import GoalCompiler
from core.agent_kernel.personal_agent.personal_execution_agent import (
    PersonalExecutionAgent,
    build_task_graph,
    compile_goal,
    run_personal_execution,
)
from core.agent_kernel.personal_agent.execution_planner import ExecutionPlanner
from core.agent_kernel.personal_agent.durable_task_state import DurableTaskState
from core.agent_kernel.personal_agent.experience_writer import ExperienceWriter
from core.agent_kernel.personal_agent.policy_judge import PolicyJudge
from core.agent_kernel.personal_agent.result_verifier import ResultVerifier
from core.agent_kernel.personal_agent.task_graph import TaskGraphBuilder, TaskGraphExecutor
from core.agent_kernel.personal_agent.schemas import (
    GoalSpec, PolicyDecision, TaskNode, TaskGraph, ExecutionPlan,
    VerificationResult, ExperienceRecord,
    RiskLevel, Decision, NodeStatus, NodeType,
)


class PersonalAgentConfig:
    """Compatibility alias for old API consumers."""
    def __init__(self, **kwargs):
        self.default_goal_compiler = GoalCompiler
        self.default_executor = PersonalExecutionAgent
        for k, v in kwargs.items():
            setattr(self, k, v)


class PersonalAgentRuntime:
    """Compatibility alias for old API consumers."""
    def __init__(self, config: 'PersonalAgentConfig | None' = None, **kwargs):
        self.config = config or PersonalAgentConfig()
        self.task_graph_builder = TaskGraphBuilder
        self.executor = PersonalExecutionAgent
        for k, v in kwargs.items():
            setattr(self, k, v)


__all__ = [
    "GoalCompiler",
    "PersonalExecutionAgent",
    "ExecutionPlanner",
    "DurableTaskState",
    "ExperienceWriter",
    "PolicyJudge",
    "ResultVerifier",
    "TaskGraphBuilder",
    "TaskGraphExecutor",
    "PersonalAgentConfig",
    "PersonalAgentRuntime",
    "compile_goal",
    "build_task_graph",
    "run_personal_execution",
    "GoalSpec", "PolicyDecision", "TaskNode", "TaskGraph", "ExecutionPlan",
    "VerificationResult", "ExperienceRecord",
    "RiskLevel", "Decision", "NodeStatus", "NodeType",
]
