"""
Crusheart Agent OS — WorkflowOrchestrator v4.1
工作流执行编排器：驱动 DAG 图从状态机维度完整执行

═══════════════════════════════════════════════
▸ 三层工作流架构（由下至上）：

  1. WorkflowEngine（workflow_engine.py）
     DAG 图构建 + TaskNode/DAGGraph 数据结构 + 节点状态管理
     → 职责："图怎么建，节点怎么管"

  2. WorkflowOrchestrator（本文件）
     工作流执行编排器：状态机驱动 + 生命周期管理 + step-by-step 调度
     + checkpoint/恢复 + 全局超时保护
     → 职责："这个工作流怎么跑完"
     → 调用：TaskExecutor 执行每个节点

  3. TaskExecutor（task_executor.py）
     单次任务执行引擎：解析→分解→路由→执行→验证→总结
     → 职责："单个节点具体怎么干"
     → 调用：底层工具/技能/引擎

═══════════════════════════════════════════════
▸ 全局编排 vs 工作流编排：

  - Orchestrator（engine_orchestrator.py）: Crusheart 全局引擎编排
    （17+ 引擎路由：hook_engine → dual_mode → goal_compiler → ... → finish）
    处理所有消息的预处理全链路。

  - WorkflowOrchestrator（本文件）: 单工作流粒度的执行编排
    由 GoalCompiler 编译出 DAGGraph 后，本编排器负责
    从 QUEUED 驱动到 COMPLETED。

═══════════════════════════════════════════════
▸ 完整调用链：

  用户输入 → Orchestrator.pre_process()
           → Orchestrator.compile_goal() → GoalCompiler.compile() → DAGGraph
           → WorkflowOrchestrator.run(graph, step_executor)
               ├─ 状态机循环
               ├─ 每步: ready_nodes() → TaskExecutor.execute(node)
               ├─ checkpoint 持久化
               └─ 全局超时保护
           → Orchestrator.post_process()
           → Orchestrator.finish_process()
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import json
import os

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# ── 引用 workflow_engine ──
from core.engines.workflow.workflow_engine import (
    DAGGraph, TaskNode,
    NodeStatus, GraphState, ActionKind, NodeLayer,
    WorkflowEngine,
)

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
CHECKPOINT_DIR = os.path.join(WORKSPACE, ".checkpoints")


# ═══════════════════════════════════════════
# 步骤执行器（用户可注入实际执行函数）
# ═══════════════════════════════════════════

class StepExecutor:
    """
    步骤执行器注册表
    
    调用方将 action_kind → 执行函数 注册进来，
    编排器在遇到特定类型的节点时调用对应函数执行。
    
    用法：
        executor = StepExecutor()
        executor.register("skill_call", my_skill_call_fn)
        executor.register("device_op", my_device_op_fn)
        result = await executor.execute(node)
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, action_kind: str, handler: Callable) -> None:
        """注册 action_kind 对应的执行函数"""
        self._handlers[action_kind] = handler
        logger.debug(f"[StepExecutor] 已注册 handler: {action_kind}")

    def unregister(self, action_kind: str) -> None:
        self._handlers.pop(action_kind, None)

    def get_handler(self, action_kind: str) -> Optional[Callable]:
        return self._handlers.get(action_kind)

    async def execute(self, node: TaskNode, context: dict) -> Any:
        """
        执行节点——根据 action_kind 派发到对应的 handler
        
        Args:
            node: 待执行的任务节点
            context: 工作流上下文
            
        Returns:
            执行结果
            
        Raises:
            ValueError: 未注册的 action_kind
        """
        handler = self._handlers.get(node.action_kind)
        if not handler:
            raise ValueError(
                f"[StepExecutor] 未注册的 action_kind: {node.action_kind} "
                f"(node={node.node_id})"
            )
        logger.info(
            f"[StepExecutor] 执行节点: {node.node_id} "
            f"kind={node.action_kind} name={node.name}"
        )
        return await handler(node, context)


# ═══════════════════════════════════════════
# Checkpoint 持久化
# ═══════════════════════════════════════════

class CheckpointStore:
    """
    检查点持久化存储
    
    每个工作流图执行过程中的 checkpoint 序列化为 JSON 文件，
    存放在 .checkpoints/{graph_id}.json。
    
    支持：
    - save(): 保存 checkpoint
    - load(): 从 checkpoint 恢复
    - list(): 列出所有 checkpoint
    """

    @staticmethod
    def _ensure_dir():
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    @staticmethod
    def _graph_path(graph_id: str) -> str:
        return os.path.join(CHECKPOINT_DIR, f"{graph_id}.json")

    @staticmethod
    def save(graph: DAGGraph) -> str:
        """保存 DAG 图状态到 checkpoint 文件"""
        CheckpointStore._ensure_dir()
        path = CheckpointStore._graph_path(graph.graph_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"[CheckpointStore] 已保存 checkpoint: {path}")
        return path

    @staticmethod
    def load(graph_id: str) -> Optional[DAGGraph]:
        """从 checkpoint 文件恢复 DAG 图"""
        path = CheckpointStore._graph_path(graph_id)
        if not os.path.exists(path):
            logger.warning(f"[CheckpointStore] checkpoint 不存在: {path}")
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph = DAGGraph.from_dict(data)
        logger.info(f"[CheckpointStore] 已恢复 checkpoint: {graph_id}")
        return graph

    @staticmethod
    def remove(graph_id: str) -> bool:
        """删除 checkpoint"""
        path = CheckpointStore._graph_path(graph_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"[CheckpointStore] 已删除 checkpoint: {graph_id}")
            return True
        return False

    @staticmethod
    def list_all() -> List[str]:
        """列出所有 checkpoint 的 graph_id"""
        CheckpointStore._ensure_dir()
        ids = []
        for fname in os.listdir(CHECKPOINT_DIR):
            if fname.endswith(".json") and not fname.startswith("."):
                ids.append(fname[:-5])
        return ids


# ═══════════════════════════════════════════
# 工作流编排器（核心）
# ═══════════════════════════════════════════

class WorkflowOrchestrator:
    """
    工作流编排器 v4.0
    
    一个工作流的完整生命周期：
        PENDING → RUNNING → (循环: 取就绪节点 → 执行 → 更新状态)
                        ↕          ↕
                      PAUSED     FAILED/CANCELLED
                        ↕
                     COMPLETED
    
    核心流程：
    1. start(graph)        → 启动工作流，标记 RUNNING
    2. step()              → 推进一步：取 ready_nodes() 并执行
    3. run_all()           → 自动执行到 COMPLETED 或失败
    4. pause/resume/cancel → 生命周期控制
    5. get_status()        → 进度报告
    """

    def __init__(self, step_executor: Optional[StepExecutor] = None,
                 auto_checkpoint: bool = True,
                 reflection_checker: Optional[Any] = None):
        self.engine = WorkflowEngine()
        self.executor = step_executor or StepExecutor()
        self.auto_checkpoint = auto_checkpoint
        self._reflection_checker = reflection_checker
        self._context: Dict[str, Any] = {}

    def set_context(self, context: dict) -> None:
        """设置/更新工作流上下文"""
        self._context.update(context)

    def get_context(self) -> dict:
        return dict(self._context)

    # ── 构建相关 ──

    def build(self, raw_goal: str,
              contract_id: Optional[str] = None) -> DAGGraph:
        """从用户意图构建 DAG 图"""
        return self.engine.build_from_goal(raw_goal, contract_id)

    def build_custom(self, nodes: List[TaskNode],
                     contract_id: Optional[str] = None) -> DAGGraph:
        """用自定义节点构建 DAG 图"""
        return self.engine.build_custom(nodes, contract_id)

    # ── 生命周期管理 ──

    def start(self, graph: DAGGraph) -> DAGGraph:
        """
        启动工作流
        
        状态变更：PENDING → RUNNING
        自动触发 checkpoint
        """
        if graph.state != GraphState.PENDING:
            raise ValueError(
                f"工作流状态必须为 PENDING（当前: {graph.state.value}）"
            )
        graph.state = GraphState.RUNNING
        graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
        self._checkpoint(graph)
        logger.info(
            f"[WorkflowOrchestrator] 工作流已启动: "
            f"graph={graph.graph_id} nodes={len(graph.nodes)}"
        )
        return graph

    async def step(self, graph: DAGGraph) -> Dict[str, Any]:
        """
        推进一步——执行所有当前 ready 的节点
        
        返回执行结果摘要：
        {
            "executed": [node_id, ...],
            "failed": [node_id, ...],
            "skipped": [node_id, ...],
            "state": "running|completed|failed|paused",
            "progress": { "completed": N, "total": N, "percentage": N }
        }
        """
        if graph.state not in (GraphState.RUNNING, GraphState.PAUSED):
            raise ValueError(
                f"工作流未在运行（当前: {graph.state.value}）"
            )

        if graph.state == GraphState.PAUSED:
            graph.state = GraphState.RUNNING

        result = {
            "executed": [],
            "failed": [],
            "skipped": [],
            "state": GraphState.RUNNING.value,
        }

        # 取 ready 节点
        ready = graph.ready_nodes()
        if not ready:
            # 没有就绪节点 → 检查是否全部完成
            all_terminal = all(
                n.status in (
                    NodeStatus.COMPLETED, NodeStatus.FAILED,
                    NodeStatus.SKIPPED, NodeStatus.CANCELLED
                )
                for n in graph.nodes
            )
            if all_terminal:
                graph.state = GraphState.COMPLETED
                graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
                self._checkpoint(graph)
                result["state"] = GraphState.COMPLETED.value
                logger.info(
                    f"[WorkflowOrchestrator] 工作流已完成: {graph.graph_id}"
                )
            return result

        # 执行 ready 节点
        for node in ready:
            try:
                # RUNNING
                graph.update_node_status(node.node_id, NodeStatus.RUNNING)
                self._checkpoint(graph)

                # 实际执行
                exec_result = await self.executor.execute(node, self._context)

                # COMPLETED
                graph.update_node_status(
                    node.node_id, NodeStatus.COMPLETED, exec_result
                )
                result["executed"].append(node.node_id)

                logger.info(
                    f"[WorkflowOrchestrator] 节点完成: {node.node_id} "
                    f"({node.name})"
                )

                # 🆕 反思环节：评估执行结果，调整后续步骤
                if self._reflection_checker is not None and self._reflection_checker.get("enabled", True):
                    try:
                        _reflection_checker = None
                        # 优先从引擎包内导入
                        try:
                            from .reflection_checker import ReflectionChecker
                            _reflection_checker = ReflectionChecker(self._reflection_checker)
                        except ImportError:
                            # 降级：从插件脚本目录加载
                            _checker_path = os.path.join(
                                os.environ.get("OPENCLAW_WORKSPACE", ""),
                                "extensions", "crusheart-autobrain-turbo",
                                "bundle", "scripts", "reflection_checker.py"
                            )
                            if os.path.exists(_checker_path):
                                import importlib.util as _iu
                                _spec = _iu.spec_from_file_location("reflection_checker", _checker_path)
                                if _spec and _spec.loader:
                                    _mod = _iu.module_from_spec(_spec)
                                    _spec.loader.exec_module(_mod)
                                    _reflection_checker = _mod.ReflectionChecker(self._reflection_checker)

                        if _reflection_checker:
                            # 找出依赖此节点的下游节点
                            _downstream = [
                                n.node_id for n in graph.nodes
                                if node.node_id in n.depends_on
                            ]
                            _decision = _reflection_checker.evaluate(
                                node.node_id, exec_result,
                                downstream_nodes=_downstream
                            )
                            _d = _decision.to_dict()
                            node.metadata["reflection"] = _d

                            if _d["level"] == "replan" and _downstream:
                                # 标记下游节点降低依赖严格度
                                for _dep_id in _downstream:
                                    _dep_node = graph.get_node(_dep_id)
                                    if _dep_node:
                                        _dep_node.metadata["reflection_warn"] = True
                                        _dep_node.metadata["reflection_reason"] = _d["reason"]
                                        logger.info(
                                            f"[Reflection] {_dep_id}: 标记为低质量依赖 "
                                            f"(来源: {node.node_id})"
                                        )

                            elif _d["level"] == "abort":
                                logger.warning(
                                    f"[Reflection] 反思终止: {node.node_id} - {_d['reason']}"
                                )
                                graph.state = GraphState.FAILED
                                result["reflection_abort"] = _d["reason"]
                                break

                            elif _d["level"] == "warn" and _downstream:
                                for _dep_id in _downstream:
                                    _dep_node = graph.get_node(_dep_id)
                                    if _dep_node:
                                        _dep_node.metadata["reflection_warn"] = True
                                        _dep_node.metadata["reflection_reason"] = _d["reason"]

                    except Exception as _re:
                        logger.debug(f"[Reflection] 反思环节异常: {_re}")

            except Exception as e:
                logger.error(
                    f"[WorkflowOrchestrator] 节点执行失败: {node.node_id} - {e}"
                )
                graph.update_node_status(
                    node.node_id, NodeStatus.FAILED, error=str(e)
                )
                result["failed"].append(node.node_id)

                # 判断是否需要终止整个工作流（不可重试的失败）
                if not node.reversible:
                    logger.warning(f"[WorkflowOrchestrator] 不可逆节点 {node.node_id} 失败，终止工作流")
                    graph.state = GraphState.FAILED
                    break

            finally:
                # 每一步都保存 checkpoint
                self._checkpoint(graph)

        # 更新进度
        completed = sum(
            1 for n in graph.nodes
            if n.status in (
                NodeStatus.COMPLETED, NodeStatus.SKIPPED
            )
        )
        failed = sum(
            1 for n in graph.nodes
            if n.status == NodeStatus.FAILED
        )
        total = len(graph.nodes)
        result["progress"] = {
            "completed": completed,
            "failed": failed,
            "total": total,
            "percentage": round(completed / total * 100, 1) if total > 0 else 0,
        }

        # 检查是否全部终结状态
        all_done = all(
            n.status in (
                NodeStatus.COMPLETED, NodeStatus.FAILED,
                NodeStatus.SKIPPED, NodeStatus.CANCELLED
            )
            for n in graph.nodes
        )
        if all_done:
            graph.state = GraphState.COMPLETED
            graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
            self._checkpoint(graph)
            result["state"] = GraphState.COMPLETED.value
            logger.info(
                f"[WorkflowOrchestrator] 工作流执行完毕: {graph.graph_id}"
            )

        return result

    async def run_all(self, graph: DAGGraph,
                      global_timeout_s: Optional[int] = None) -> Dict[str, Any]:
        """
        全自动执行——从 start 到 COMPLETED/FAILED

        内置全局超时保护：默认 max_execution = max(120, len(nodes) * 30)s
        
        Args:
            graph: 要执行的 DAGGraph
            global_timeout_s: 全局执行超时秒数（覆盖默认值）

        Returns:
            {
                "graph_id": str,
                "state": "completed|failed|cancelled",
                "progress": {...},
                "context": dict,
                "summary": [节点执行结果摘要]
            }
        """
        graph = self.start(graph)

        max_loops = len(graph.nodes) * 3  # 安全上限
        loop_count = 0

        # ── 全局超时保护 ──
        import time as _time_module
        if global_timeout_s is not None:
            deadline = _time_module.monotonic() + global_timeout_s
        else:
            deadline = _time_module.monotonic() + max(120, len(graph.nodes) * 30)

        while graph.state == GraphState.RUNNING and loop_count < max_loops:
            # 超时检测
            if _time_module.monotonic() > deadline:
                logger.warning(
                    f"[WorkflowOrchestrator] 全局执行超时，终止工作流: "
                    f"{graph.graph_id} (>{deadline - _time_module.monotonic() + deadline}s)"
                )
                graph.state = GraphState.CANCELLED
                graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
                self._checkpoint(graph)
                break

            step_result = await self.step(graph)
            loop_count += 1

            if step_result["failed"]:
                logger.warning(
                    f"[WorkflowOrchestrator] 执行中有节点失败: "
                    f"{step_result['failed']}"
                )
                # 继续尝试执行其他节点，不中断整个流程

        summary = []
        for node in graph.nodes:
            summary.append({
                "node_id": node.node_id,
                "name": node.name,
                "status": node.status.value,
                "error": node.error,
            })

        return {
            "graph_id": graph.graph_id,
            "state": graph.state.value,
            "progress": step_result.get("progress", {}),
            "context": self.get_context(),
            "summary": summary,
        }

    # ── 同步执行包装（供 CLI/hook 同步调用） ──

    async def run_sync(self, graph: DAGGraph,
                       timeout_s: int = 600) -> dict:
        """
        同步执行整个工作流（async run_all 的同步包装）

        与 run_all 相同语义，用于 bundle/scripts/workflow_engine.py
        等同步调用方。

        Args:
            graph: DAGGraph 工作流图
            timeout_s: 全局超时秒数

        Returns:
            {"graph_id": ..., "state": ..., "progress": ..., "summary": [...]}
        """
        return await self.run_all(graph, timeout_s=timeout_s)

    # ── 生命周期控制 ──

    def pause(self, graph: DAGGraph) -> bool:
        """暂停工作流"""
        if graph.state != GraphState.RUNNING:
            return False
        graph.state = GraphState.PAUSED
        graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
        self._checkpoint(graph)
        logger.info(
            f"[WorkflowOrchestrator] 工作流已暂停: {graph.graph_id}"
        )
        return True

    def resume(self, graph: DAGGraph) -> bool:
        """恢复已暂停的工作流"""
        if graph.state != GraphState.PAUSED:
            return False
        graph.state = GraphState.RUNNING
        graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
        self._checkpoint(graph)
        logger.info(
            f"[WorkflowOrchestrator] 工作流已恢复: {graph.graph_id}"
        )
        return True

    def cancel(self, graph: DAGGraph) -> bool:
        """取消工作流"""
        if graph.state in (
            GraphState.COMPLETED, GraphState.FAILED, GraphState.CANCELLED
        ):
            return False
        graph.state = GraphState.CANCELLED
        graph.updated_at = datetime.now(BEIJING_TZ).isoformat()
        for node in graph.nodes:
            if node.status == NodeStatus.QUEUED:
                node.status = NodeStatus.CANCELLED
        self._checkpoint(graph)
        logger.info(
            f"[WorkflowOrchestrator] 工作流已取消: {graph.graph_id}"
        )
        return True

    # ── 状态 / 进度 ──

    def get_status(self, graph: DAGGraph) -> Dict[str, Any]:
        """获取工作流进度报告"""
        completed = sum(
            1 for n in graph.nodes
            if n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
        )
        failed = sum(1 for n in graph.nodes if n.status == NodeStatus.FAILED)
        total = len(graph.nodes)

        return {
            "graph_id": graph.graph_id,
            "state": graph.state.value,
            "contract_id": graph.contract_id,
            "progress": {
                "completed": completed,
                "failed": failed,
                "total": total,
                "percentage": round(completed / total * 100, 1) if total > 0 else 0,
            },
            "nodes": [
                {
                    "node_id": n.node_id,
                    "name": n.name,
                    "status": n.status.value,
                    "action_kind": n.action_kind,
                    "device_op": n.device_side_effect,
                    "error": n.error,
                }
                for n in graph.nodes
            ],
            "updated_at": graph.updated_at,
        }

    # ── Checkpoint ──

    def _checkpoint(self, graph: DAGGraph):
        """保存 checkpoint（如果启用）"""
        if self.auto_checkpoint:
            CheckpointStore.save(graph)

    def save_checkpoint(self, graph: DAGGraph) -> str:
        """显式保存 checkpoint"""
        return CheckpointStore.save(graph)

    @staticmethod
    def load_checkpoint(graph_id: str) -> Optional[DAGGraph]:
        """从 checkpoint 恢复"""
        return CheckpointStore.load(graph_id)
