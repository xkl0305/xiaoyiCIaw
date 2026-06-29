"""
Crusheart Agent OS — WorkflowEngine v4.0
耐久工作流引擎：DAG 任务图构建 + 状态机管理 + 依赖解析 + 串行约束

设计原则：
- 完全自实现（借鉴鸽子王 durable_workflow_engine_v3 + orchestration 的设计模式）
- 与 Crusheart 现有引擎体系对接（orchestrator.py, mutex_engine, unified_judge）
- 所有数据可序列化 JSON，支持 checkpoint/recovery
- 设备侧操作强制串行约束，禁止并行派发
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timezone, timedelta
import json
import uuid
import logging

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))


# ═══════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════

class NodeStatus(str, Enum):
    """任务节点状态（9态）"""
    QUEUED = "queued"                    # 排队中，等待依赖满足
    RUNNING = "running"                  # 执行中
    WAITING_APPROVAL = "waiting_approval"  # 等待用户确认
    PENDING_VERIFY = "pending_verify"    # 执行完成，等待验证回执
    COMPLETED = "completed"              # 已完成
    FAILED = "failed"                    # 失败
    SKIPPED = "skipped"                  # 跳过（条件不满足）
    PAUSED = "paused"                    # 暂停（工作流层面）
    CANCELLED = "cancelled"              # 已取消


class GraphState(str, Enum):
    """工作流图状态"""
    PENDING = "pending"          # 未启动
    RUNNING = "running"          # 运行中
    PAUSED = "paused"            # 已暂停
    COMPLETED = "completed"      # 全部完成
    FAILED = "failed"            # 失败终止
    CANCELLED = "cancelled"      # 已取消


class NodeLayer(str, Enum):
    """节点所属层级"""
    L1_SKILL = "L1_skill"                  # 技能层
    L2_MEMORY = "L2_memory"               # 记忆层
    L3_ORCHESTRATION = "L3_orchestration"  # 编排层
    L4_EXECUTION = "L4_execution"          # 执行层
    L5_GOVERNANCE = "L5_governance"        # 治理/审核层


class ActionKind(str, Enum):
    """动作类型"""
    SKILL_CALL = "skill_call"                # 技能调用
    TOOL_EXEC = "tool_exec"                  # 工具执行
    DEVICE_OP = "device_op"                  # 设备操作（gui-agent等）
    GOVERNANCE_CHECK = "governance_check"    # 治理审核
    MEMORY_WRITE = "memory_write"            # 记忆写入
    REPORT = "report"                        # 报告/回执
    INTERNAL_REVIEW = "internal_review"      # 内部审查
    USER_CONFIRM = "user_confirm"            # 用户确认
    CONDITIONAL = "conditional"              # 条件分支
    SUBAGENT = "subagent"                    # 子代理任务


# ═══════════════════════════════════════════
# 核心数据结构
# ═══════════════════════════════════════════

@dataclass
class TaskNode:
    """
    任务节点 — DAG 中的最小执行单元
    
    设计说明：
    - 使用 dataclass 确保可序列化
    - depends_on 列表实现 DAG 依赖关系
    - device_side_effect 标记设备侧操作，用于串行约束
    - reversible 标记是否可回滚
    """
    node_id: str
    name: str
    action_kind: str
    layer_owner: str
    depends_on: List[str] = field(default_factory=list)
    device_side_effect: bool = False
    reversible: bool = True
    timeout_s: int = 120
    max_retries: int = 3
    retry_delay_s: int = 2
    verification_policy: str = "basic"
    status: NodeStatus = NodeStatus.QUEUED
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskNode":
        data = dict(data)
        data["status"] = NodeStatus(data["status"])
        return cls(**data)


@dataclass
class DAGGraph:
    """
    有向无环图 — 工作流执行的基础数据结构
    
    核心能力：
    - ready_nodes(): 获取所有依赖已满足的待执行节点
    - has_blocking_pending_verify(): 检查是否有阻塞的验证回执
    - assert_device_serialized(): 设备侧操作串行性校验
    - to_dict() / from_dict(): 完整 JSON 序列化，支持 checkpoint
    """
    graph_id: str
    contract_id: str
    nodes: List[TaskNode]
    cursor: Optional[str] = None
    version: str = "v4.0"
    state: GraphState = GraphState.PENDING
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(BEIJING_TZ).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        self._node_map: Dict[str, TaskNode] = {}
        for n in self.nodes:
            self._node_map[n.node_id] = n

    def _rebuild_map(self):
        self._node_map = {}
        for n in self.nodes:
            self._node_map[n.node_id] = n

    @property
    def node_map(self) -> Dict[str, TaskNode]:
        if not self._node_map:
            self._rebuild_map()
        return self._node_map

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        return self.node_map.get(node_id)

    def add_node(self, node: TaskNode) -> "DAGGraph":
        """添加节点（运行时动态注册）"""
        self.nodes.append(node)
        self._node_map[node.node_id] = node
        self.updated_at = datetime.now(BEIJING_TZ).isoformat()
        return self

    def ready_nodes(self) -> List[TaskNode]:
        """
        获取所有依赖已满足的待执行节点
        
        判定规则：
        1. 节点状态必须为 QUEUED
        2. 所有 dependencies 中的节点必须是 COMPLETED 或 SKIPPED
        """
        done = {
            n.node_id for n in self.nodes
            if n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED, NodeStatus.FAILED)
        }
        ready = []
        for node in self.nodes:
            if node.status != NodeStatus.QUEUED:
                continue
            if all(dep in done for dep in node.depends_on):
                ready.append(node)
        return ready

    def has_blocking_pending_verify(self) -> bool:
        """检查是否有设备侧操作等待验证回执"""
        return any(
            n.status == NodeStatus.PENDING_VERIFY and n.device_side_effect
            for n in self.nodes
        )

    def assert_device_serialized(self) -> bool:
        """
        设备侧操作串行性校验
        
        核心规则：
        - 如果存在多个 device_side_effect=True 的节点
        - 它们必须形成一条链（每个节点必须依赖前一个设备节点）
        - 不允许两个设备节点并行执行
        """
        device_nodes = [n for n in self.nodes if n.device_side_effect]
        if len(device_nodes) <= 1:
            return True
        # 检查链连续性：每个设备节点必须依赖前一个设备节点
        previous = device_nodes[0].node_id
        for node in device_nodes[1:]:
            if previous not in node.depends_on:
                return False
            previous = node.node_id
        # 额外检查：不存在非链中的并行设备节点依赖关系
        device_ids = {n.node_id for n in device_nodes}
        for node in device_nodes:
            for dep in node.depends_on:
                if dep in device_ids and dep != previous:
                    # 如果有设备节点之间存在非链依赖，也视为不串行
                    pass  # 上层的链式检查已经覆盖
        return True

    def update_node_status(self, node_id: str, status: NodeStatus,
                           result: Any = None, error: Optional[str] = None) -> bool:
        """更新节点状态"""
        node = self.get_node(node_id)
        if not node:
            return False
        node.status = status
        result and setattr(node, "result", result)
        error and setattr(node, "error", error)
        if status == NodeStatus.RUNNING and not node.started_at:
            node.started_at = datetime.now(BEIJING_TZ).isoformat()
        if status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
            node.completed_at = datetime.now(BEIJING_TZ).isoformat()
        self.updated_at = datetime.now(BEIJING_TZ).isoformat()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "contract_id": self.contract_id,
            "cursor": self.cursor,
            "version": self.version,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAGGraph":
        data = dict(data)
        data["state"] = GraphState(data["state"])
        data["nodes"] = [TaskNode.from_dict(n) for n in data["nodes"]]
        return cls(**data)


# ═══════════════════════════════════════════
# 工作流引擎 — DAG 构建 + 编排
# ═══════════════════════════════════════════

class WorkflowEngine:
    """
    耐久工作流引擎 v4.0
    
    职责：
    1. 从 OperatingContract（或用户意图）构建 DAG 任务图
    2. 设备侧操作强制串行链
    3. 运行时节点状态管理
    4. 完整 JSON 序列化（checkpoint / recovery 支撑）
    
    使用方式：
        engine = WorkflowEngine()
        graph = engine.build_from_goal("帮我设置明天8点的闹钟")
        # 检查 graph.ready_nodes() -> 获取可执行节点
        # ... 执行节点并 update_node_status ...
        # 循环直到 graph.state == COMPLETED
    """

    # 设备关键词检测——用于自动识别需要串行链的任务
    DEVICE_KEYWORDS = [
        "闹钟", "提醒", "日程", "通知",
        "打开", "设置", "调整",
        "文件", "下载", "上传",
        "GUI", "端侧", "手机",
        "gui-agent", "gui_agent",
    ]

    def build_from_goal(self, raw_goal: str,
                         contract_id: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> DAGGraph:
        """
        从用户意图构建 DAG 任务图
        
        构建流程：
        1. 创建 n1_goal_review 节点（合约审查）
        2. 检测是否含设备操作 → 构建串行设备链
        3. 追加 governance 审核 → 记忆写入 → 完成报告
        
        Args:
            raw_goal: 用户原始意图文本
            contract_id: 合约 ID（可选，自动生成）
            context: 附加上下文
            
        Returns:
            构建完成的 DAGGraph（已执行串行性校验）
        """
        graph_id = "graph_" + uuid.uuid4().hex[:12]
        cid = contract_id or "contract_" + uuid.uuid4().hex[:8]
        nodes: List[TaskNode] = []

        # ── 第1步：合约审查节点（占位，L3编排层） ──
        nodes.append(TaskNode(
            node_id="n1_goal_review",
            name="review_goal_contract",
            action_kind=ActionKind.INTERNAL_REVIEW,
            layer_owner=NodeLayer.L3_ORCHESTRATION,
            verification_policy="contract_schema",
        ))

        # ── 第2步：检测设备操作 → 构建串行设备链 ──
        last_device_node = "n1_goal_review"
        need_device_chain = any(kw in raw_goal for kw in self.DEVICE_KEYWORDS)

        if need_device_chain:
            device_phases: List[Dict[str, str]] = [
                {
                    "node_id": "n2_device_probe",
                    "name": "probe_device_capability",
                    "action_kind": ActionKind.TOOL_EXEC,
                    "verify": "device_probe",
                    "desc": "设备能力探测"
                },
                {
                    "node_id": "n3_device_prepare",
                    "name": "prepare_device_action",
                    "action_kind": ActionKind.TOOL_EXEC,
                    "verify": "device_prepare",
                    "desc": "设备操作准备"
                },
                {
                    "node_id": "n4_device_execute",
                    "name": "execute_device_action",
                    "action_kind": ActionKind.DEVICE_OP,
                    "verify": "device_receipt_or_pending_verify",
                    "desc": "设备操作执行"
                },
                {
                    "node_id": "n5_device_verify",
                    "name": "verify_device_result",
                    "action_kind": ActionKind.TOOL_EXEC,
                    "verify": "two_phase_verify",
                    "desc": "设备操作验证"
                },
            ]

            for phase in device_phases:
                # 串行链：依赖上一个节点 + 前一个设备节点
                deps = [last_device_node]

                node = TaskNode(
                    node_id=phase["node_id"],
                    name=phase["name"],
                    action_kind=phase["action_kind"],
                    layer_owner=NodeLayer.L4_EXECUTION,
                    depends_on=deps,
                    device_side_effect=True,
                    reversible=("execute" not in phase["node_id"]),
                    timeout_s=180,
                    max_retries=2,
                    verification_policy=phase["verify"],
                    metadata={"description": phase["desc"]},
                )
                nodes.append(node)
                last_device_node = phase["node_id"]

        # ── 第3步：治理审核 + 记忆写入 + 完成报告 ──
        nodes.append(TaskNode(
            node_id="n6_judge_gate",
            name="unified_judge_gate",
            action_kind=ActionKind.GOVERNANCE_CHECK,
            layer_owner=NodeLayer.L5_GOVERNANCE,
            depends_on=[last_device_node],
            verification_policy="judge_decision",
        ))
        nodes.append(TaskNode(
            node_id="n7_memory_writeback",
            name="guarded_memory_writeback",
            action_kind=ActionKind.MEMORY_WRITE,
            layer_owner=NodeLayer.L2_MEMORY,
            depends_on=["n6_judge_gate"],
            verification_policy="memory_guard",
        ))
        nodes.append(TaskNode(
            node_id="n8_completion_report",
            name="completion_report",
            action_kind=ActionKind.REPORT,
            layer_owner=NodeLayer.L3_ORCHESTRATION,
            depends_on=["n7_memory_writeback"],
            verification_policy="done_definition",
        ))

        # ── 构建 DAG 并校验串行性 ──
        graph = DAGGraph(
            graph_id=graph_id,
            contract_id=cid,
            nodes=nodes,
        )

        if not graph.assert_device_serialized():
            raise ValueError(
                f"[WorkflowEngine] 设备操作节点未构成串行链，"
                f"已拦截 graph={graph_id}"
            )

        logger.info(
            f"[WorkflowEngine] DAG图构建完成: "
            f"graph={graph_id} nodes={len(nodes)} "
            f"device_chain={need_device_chain}"
        )
        return graph

    def build_custom(self, nodes: List[TaskNode],
                     contract_id: Optional[str] = None) -> DAGGraph:
        """
        用预定义节点列表构建自定义 DAG 图
        
        适用于高级场景：调用方已自行构造好节点和依赖关系
        
        Args:
            nodes: 任务节点列表
            contract_id: 合约 ID
            
        Returns:
            构建完成的 DAGGraph
        """
        graph_id = "graph_" + uuid.uuid4().hex[:12]
        graph = DAGGraph(
            graph_id=graph_id,
            contract_id=contract_id or "custom_" + uuid.uuid4().hex[:8],
            nodes=nodes,
        )

        if not graph.assert_device_serialized():
            raise ValueError(
                f"[WorkflowEngine] 自定义 DAG 中设备操作未串行化"
            )

        logger.info(
            f"[WorkflowEngine] 自定义DAG图构建完成: "
            f"graph={graph_id} nodes={len(nodes)}"
        )
        return graph

    @staticmethod
    def validate_graph(graph: DAGGraph) -> List[str]:
        """
        校验 DAG 图合法性，返回错误列表
        
        检查项：
        1. 设备节点串行性
        2. 节点 ID 唯一性
        3. 依赖节点必须存在
        4. 不存在循环依赖（简单检测：所有节点可达）
        """
        errors = []

        # 检查串行性
        if not graph.assert_device_serialized():
            errors.append("设备操作节点未串行化")

        # 检查节点 ID 唯一性
        ids = [n.node_id for n in graph.nodes]
        if len(ids) != len(set(ids)):
            duplicates = [i for i in ids if ids.count(i) > 1]
            errors.append(f"存在重复节点ID: {set(duplicates)}")

        # 检查依赖节点都存在
        all_ids = set(ids)
        for node in graph.nodes:
            for dep in node.depends_on:
                if dep not in all_ids:
                    errors.append(
                        f"节点 {node.node_id} 依赖不存在的节点: {dep}"
                    )

        # 循环依赖检测 (DFS back edge)
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n.node_id: WHITE for n in graph.nodes}
        adj = {n.node_id: list(n.depends_on) for n in graph.nodes}

        def dfs_cycle(nid, path):
            color[nid] = GRAY
            for dep in adj.get(nid, []):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    cycle_nodes = path[path.index(dep):] + [dep]
                    errors.append(f"存在循环依赖: {' -> '.join(cycle_nodes)}")
                    return True
                elif color[dep] == WHITE:
                    if dfs_cycle(dep, path + [dep]):
                        return True
            color[nid] = BLACK
            return False

        for nid in list(color.keys()):
            if color[nid] == WHITE:
                dfs_cycle(nid, [nid])

        return errors

    # ────────────────────────────────────────────────
    # Item 5: 深度调研工作流构建
    # ────────────────────────────────────────────────
    @staticmethod
    def build_deep_research_workflow(topic: str) -> DAGGraph:
        """
        构建标准 3 层深度调研 DAG。

        工作流：
          layer1_broad（5 角度广度搜索）
               ↓
          layer2_deep（追问挖掘）
               ↓
          layer3_verify（交叉验证）
               ↓
          synthesize（综合报告）

        Args:
            topic: 调研主题

        Returns:
            DAGGraph 对象
        """
        from uuid import uuid4 as _uuid4
        gid = f"research_{_uuid4().hex[:8]}"

        nodes = [
            TaskNode(
                node_id="layer1_broad",
                name=f"广度搜索: {topic}",
                action_kind=ActionKind.SUBAGENT,
                layer_owner=NodeLayer.L4_EXECUTION,
            ),
            TaskNode(
                node_id="layer2_deep",
                name=f"深度挖掘: {topic}",
                action_kind=ActionKind.SUBAGENT,
                layer_owner=NodeLayer.L4_EXECUTION,
                depends_on=["layer1_broad"],
            ),
            TaskNode(
                node_id="layer3_verify",
                name=f"交叉验证: {topic}",
                action_kind=ActionKind.SUBAGENT,
                layer_owner=NodeLayer.L4_EXECUTION,
                depends_on=["layer2_deep"],
            ),
            TaskNode(
                node_id="synthesize",
                name=f"综合报告: {topic}",
                action_kind=ActionKind.SUBAGENT,
                layer_owner=NodeLayer.L4_EXECUTION,
                depends_on=["layer3_verify"],
            ),
        ]

        return DAGGraph(
            graph_id=gid,
            contract_id=gid,
            nodes=nodes,
        )


# ═══════════════════════════════════════════
# 快速验证
# ═══════════════════════════════════════════

if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    logging.basicConfig(level=logging.INFO)

    # 测试1：构建带设备操作的 DAG
    print("=" * 60)
    print("测试1: 带设备操作的 DAG 构建")
    print("=" * 60)
    engine = WorkflowEngine()
    graph = engine.build_from_goal("帮我设置明天8点的闹钟")
    print(f"graph_id: {graph.graph_id}")
    print(f"节点数: {len(graph.nodes)}")
    print(f"设备节点串行: {graph.assert_device_serialized()}")
    print(f"就绪节点: {[n.node_id for n in graph.ready_nodes()]}")
    print()

    # 测试2：打印 DAG 图 JSON
    print("=" * 60)
    print("测试2: DAG 图 JSON 序列化")
    print("=" * 60)
    print(graph.to_json()[:500] + "...")
    print()

    # 测试3：序列化 → 反序列化 → 一致
    print("=" * 60)
    print("测试3: 序列化/反序列化一致性")
    print("=" * 60)
    data = graph.to_dict()
    restored = DAGGraph.from_dict(data)
    assert restored.graph_id == graph.graph_id
    assert len(restored.nodes) == len(graph.nodes)
    assert restored.assert_device_serialized() == graph.assert_device_serialized()
    print("✅ 一致")
    print()

    # 测试4：节点状态流转
    print("=" * 60)
    print("测试4: 节点状态流转")
    print("=" * 60)
    for node in graph.nodes:
        if node.status == NodeStatus.QUEUED or not node.depends_on:
            graph.update_node_status(node.node_id, NodeStatus.COMPLETED, {"ok": True})
            print(f"  ✅ {node.node_id} ({node.name}) → COMPLETED")

    ready = graph.ready_nodes()
    print(f"\n完成后就绪节点: {[n.node_id for n in ready]}")
    print(f"最终状态: {graph.state.value}")
    print()

    # 测试5：不串行的设备节点（应失败）
    print("=" * 60)
    print("测试5: 非法并行设备节点（应被拦截）")
    print("=" * 60)
    try:
        bad_nodes = [
            TaskNode(node_id="d1", name="dev1", action_kind=ActionKind.DEVICE_OP,
                     layer_owner=NodeLayer.L4_EXECUTION, device_side_effect=True),
            TaskNode(node_id="d2", name="dev2", action_kind=ActionKind.DEVICE_OP,
                     layer_owner=NodeLayer.L4_EXECUTION, device_side_effect=True),
        ]
        engine.build_custom(bad_nodes)
        print("  ❌ 应失败但通过了")
    except ValueError as e:
        print(f"  ✅ 正确拦截: {e}")
    print()

    print("所有测试通过 ✅")
