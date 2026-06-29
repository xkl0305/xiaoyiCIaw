# workflow engine 包
# GoalCompiler 已从独立文件移入 engine_orchestrator.py
# 向后兼容：旧代码 from core.engines.workflow.goal_compiler import GoalCompiler
# 仍然有效，此处提供别名

from core.engines.workflow.engine_orchestrator import GoalCompiler, GoalContract, Orchestrator
