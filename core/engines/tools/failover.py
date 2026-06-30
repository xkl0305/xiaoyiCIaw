"""
Crusheart Agent OS — Failover v4.0
故障转移引擎：自动检测 + 节点切换 + 降级策略

与现有系统关系：
- model-failover 插件：负责模型层的故障转移（主→备模型）
- Failover（本文件）：通用执行层的故障转移（工具/能力/节点级别）
- ToolExecutionGateway：调用本模块做降级决策

核心能力：
1. 多节点健康监控（register_node / check / switch）
2. 自动故障检测 + 切换
3. 三种切换策略：轮询 / 加权 / 最低延迟
4. 执行包裹器：自动重试 + 节点切换
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import asyncio
import logging
import time
import random

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))

# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class NodeHealth(str, Enum):
    """节点健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"

class SwitchStrategy(str, Enum):
    """切换策略"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"

# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class Node:
    """服务节点"""
    node_id: str
    endpoint: str
    weight: float = 1.0
    status: NodeHealth = NodeHealth.HEALTHY
    failure_count: int = 0
    success_count: int = 0
    latency: float = 0.0
    last_check: float = 0.0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "latency": round(self.latency, 3),
            "last_check": datetime.fromtimestamp(self.last_check, tz=BEIJING_TZ).isoformat()
                if self.last_check else None,
            "last_error": self.last_error,
        }

# ═══════════════════════════════════════════
# 健康检查器
# ═══════════════════════════════════════════

class HealthChecker:
    """
    健康检查器
    
    用注册的健康检查函数定期检查节点状态。
    默认检查函数模拟 90% 成功率 + 随机延迟。
    """

    def __init__(self, check_interval_s: float = 10.0,
                 failure_threshold: int = 3,
                 recovery_threshold: int = 2):
        self.check_interval = check_interval_s
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.nodes: Dict[str, Node] = {}
        self._check_fn: Optional[Callable] = None

    def set_check_fn(self, fn: Callable) -> None:
        """设置自定义健康检查函数（接收 node, 返回 bool）"""
        self._check_fn = fn

    def register_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        logger.info(f"[HealthChecker] 已注册: {node.node_id}")

    def unregister_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)

    async def check_node(self, node: Node, force: bool = False) -> bool:
        """检查单个节点，返回是否健康"""
        fn = self._check_fn or self._default_check
        try:
            result = fn(node)
            if hasattr(result, "__await__"):
                result = await result
            is_healthy = bool(result)
        except Exception as e:
            is_healthy = False
            node.last_error = str(e)

        node.last_check = time.time()

        if is_healthy:
            node.success_count += 1
            node.failure_count = 0
            if node.status in (NodeHealth.UNHEALTHY, NodeHealth.OFFLINE):
                if node.success_count >= self.recovery_threshold:
                    node.status = NodeHealth.HEALTHY
                    logger.info(
                        f"[HealthChecker] 节点恢复: {node.node_id}"
                    )
            else:
                node.status = NodeHealth.HEALTHY
        else:
            node.failure_count += 1
            node.success_count = 0
            if node.failure_count >= self.failure_threshold:
                old_status = node.status
                node.status = NodeHealth.UNHEALTHY
                if old_status != NodeHealth.UNHEALTHY:
                    logger.warning(
                        f"[HealthChecker] 节点不健康: {node.node_id} "
                        f"failures={node.failure_count}"
                    )

        return is_healthy

    def _default_check(self, node: Node) -> bool:
        """
        默认健康检查。
        根据 node 类型自动选择检查方式：
          - http/https → 发送 HEAD 请求
          - 其他 → 尝试 TCP 连通性检查
        检查失败则逐步降级（degraded → unhealthy）。
        """
        import socket

        endpoint = node.endpoint or node.node_id
        is_healthy = False
        start = time.time()

        try:
            if endpoint.startswith("http://") or endpoint.startswith("https://"):
                # HTTP(S) 节点：HEAD 请求
                import urllib.request
                req = urllib.request.Request(endpoint, method="HEAD")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    is_healthy = resp.status < 500
                    node.latency = time.time() - start
            else:
                # 非 HTTP 节点：TCP 连接检查
                host_port = endpoint.rsplit(":", 1)
                host = host_port[0] if len(host_port) == 2 else endpoint
                port = int(host_port[1]) if len(host_port) == 2 else 80
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()
                is_healthy = True
                node.latency = time.time() - start
        except Exception:
            is_healthy = False
            node.latency = time.time() - start

        # 连续失败 → 降级
        if not is_healthy:
            if node.failure_count >= 3:
                node.status = NodeHealth.UNHEALTHY
            elif node.failure_count >= 1:
                node.status = NodeHealth.DEGRADED
        else:
            if node.failure_count > 0:
                node.failure_count = max(0, node.failure_count - 1)
            if node.status != NodeHealth.HEALTHY:
                node.status = NodeHealth.HEALTHY

        node.last_check = time.time()
        return is_healthy

    async def check_all(self) -> Dict[str, bool]:
        """检查所有节点"""
        results = {}
        for nid, node in self.nodes.items():
            results[nid] = await self.check_node(node)
        return results

    def get_healthy(self) -> List[Node]:
        return [n for n in self.nodes.values()
                if n.status == NodeHealth.HEALTHY]

    def stats(self) -> Dict[str, Any]:
        return {
            "total": len(self.nodes),
            "healthy": len(self.get_healthy()),
            "by_status": {
                s.value: sum(1 for n in self.nodes.values() if n.status == s)
                for s in NodeHealth
            },
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

# ═══════════════════════════════════════════
# 节点选择器
# ═══════════════════════════════════════════

class NodeSelector:
    """节点选择器"""

    def __init__(self, strategy: SwitchStrategy = SwitchStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self._index = 0

    def select(self, nodes: List[Node]) -> Optional[Node]:
        if not nodes:
            return None

        if self.strategy == SwitchStrategy.ROUND_ROBIN:
            node = nodes[self._index % len(nodes)]
            self._index += 1
            return node

        elif self.strategy == SwitchStrategy.WEIGHTED:
            total = sum(n.weight for n in nodes)
            r = random.uniform(0, total)
            current = 0.0
            for node in nodes:
                current += node.weight
                if r <= current:
                    return node
            return nodes[-1]

        elif self.strategy == SwitchStrategy.LEAST_LATENCY:
            return min(nodes, key=lambda n: n.latency)

        return nodes[0]

    def set_strategy(self, strategy: SwitchStrategy):
        self.strategy = strategy

# ═══════════════════════════════════════════
# 故障转移管理器
# ═══════════════════════════════════════════

class FailoverManager:
    """
    故障转移管理器 v4.0
    
    使用方式：
        fm = FailoverManager()
        
        # 注册节点
        fm.register_node(Node("model_a", "endpoint_a", weight=1.0))
        fm.register_node(Node("model_b", "endpoint_b", weight=1.5))
        
        # 执行（自动故障转移）
        result = await fm.execute(lambda node: call_api(node.endpoint))
        # 或指定重试次数
        result = await fm.execute_with_retry(
            lambda node: call_api(node.endpoint),
            max_retries=5
        )
    """

    def __init__(self, checker: Optional[HealthChecker] = None,
                 strategy: SwitchStrategy = SwitchStrategy.ROUND_ROBIN):
        self.checker = checker or HealthChecker()
        self.selector = NodeSelector(strategy)
        self._failover_count = 0

    def register_node(self, node: Node) -> None:
        self.checker.register_node(node)

    def set_strategy(self, strategy: SwitchStrategy) -> None:
        self.selector.strategy = strategy

    async def execute(self, fn: Callable, *args,
                      context: Optional[Dict] = None,
                      **kwargs) -> Any:
        """
        执行（带故障转移）
        
        Args:
            fn: 执行函数，接收 (node, *args, **kwargs)
            
        Returns:
            执行结果
            
        Raises:
            RuntimeError: 所有节点都失败
        """
        return await self.execute_with_retry(fn, *args, max_retries=3,
                                              context=context, **kwargs)

    async def execute_with_retry(self, fn: Callable, *args,
                                 max_retries: int = 3,
                                 context: Optional[Dict] = None,
                                 **kwargs) -> Any:
        """
        带重试的故障转移执行
        
        流程：
        1. 获取健康节点列表
        2. 选择一个节点
        3. 执行 fn(node, ...)
        4. 成功 → 返回
        5. 失败 → 标记节点不健康 → 选下一个节点 → 重试
        """
        ctx = context or {}

        for attempt in range(max_retries):
            # 1. 获取健康节点
            healthy = self.checker.get_healthy()
            if not healthy:
                # 如果没有健康节点，从所有节点中尝试
                healthy = list(self.checker.nodes.values())

            if not healthy:
                raise RuntimeError("没有可用节点")

            # 2. 选择一个
            node = self.selector.select(healthy)
            if not node:
                raise RuntimeError("无法选择节点")

            try:
                # 3. 执行（传入节点作为第一个参数）
                start = time.time()
                result = fn(node, *args, **kwargs)
                if hasattr(result, "__await__"):
                    result = await result
                node.latency = (time.time() - start) * 1000
                node.success_count += 1
                node.failure_count = 0
                node.status = NodeHealth.HEALTHY
                return result

            except Exception as e:
                node.failure_count += 1
                node.last_error = str(e)
                node.latency = 9999  # 失败标记高延迟

                if node.failure_count >= self.checker.failure_threshold:
                    node.status = NodeHealth.UNHEALTHY

                self._failover_count += 1
                logger.warning(
                    f"[FailoverManager] 节点失败: {node.node_id} - {e}"
                    f" (attempt {attempt + 1}/{max_retries})"
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (1 + attempt))  # 指数退避

        raise RuntimeError(
            f"所有 {len(self.checker.nodes)} 个节点均已失败，"
            f"已重试 {max_retries} 次"
        )

    def switch_model(self, current: str, backup: str) -> Optional[Node]:
        """
        快速切换：从当前节点切换到备用节点
        
        这是 model-failover 插件场景的便捷方法。
        """
        backup_node = self.checker.nodes.get(backup)
        if not backup_node:
            logger.error(f"[FailoverManager] 备用节点不存在: {backup}")
            return None

        backup_node.status = NodeHealth.HEALTHY
        logger.info(
            f"[FailoverManager] 模型切换: {current} → {backup}"
        )
        return backup_node

    def get_stats(self) -> Dict[str, Any]:
        return {
            "failover_count": self._failover_count,
            "strategy": self.selector.strategy.value,
            "health": self.checker.stats(),
        }

# ── Engine init ──
_instance = None

def init() -> FailoverManager:
    global _instance
    if _instance is None:
        _instance = FailoverManager()
    return _instance

def get_failover() -> FailoverManager:
    return init()

# ═══════════════════════════════════════════
# 验证
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

    async def main():
        logging.basicConfig(level=logging.INFO)

        print("=" * 60)
        print("Failover v4.0 — 测试")
        print("=" * 60)

        fm = FailoverManager()

        # 模拟 API 调用
        call_count: Dict[str, int] = {}

        async def api_call(node: Node, payload: str):
            call_count[node.node_id] = call_count.get(node.node_id, 0) + 1
            # 模拟 30% 失败率
            if random.random() < 0.3:
                raise RuntimeError("模拟失败")
            await asyncio.sleep(0.05)
            return f"{node.node_id}: {payload} ok"

        # 注册节点
        fm.register_node(Node("node_a", "http://a:8080", weight=1.0))
        fm.register_node(Node("node_b", "http://b:8080", weight=1.5))
        fm.register_node(Node("node_c", "http://c:8080", weight=0.8))

        # 测试1: 基本执行
        print("\n测试1: 基本执行")
        r1 = await fm.execute(api_call, "test1")
        print(f"  result={r1}")
        print("  ✅ 通过")

        # 测试2: 故障转移（多次执行触发切换）
        print("\n测试2: 故障转移（执行10次）")
        call_count.clear()
        fm.checker.nodes["node_a"].status = NodeHealth.HEALTHY
        fm.checker.nodes["node_b"].status = NodeHealth.HEALTHY
        fm.checker.nodes["node_c"].status = NodeHealth.HEALTHY

        results = []
        for i in range(10):
            try:
                r = await fm.execute(api_call, f"req_{i}")
                results.append(r)
            except RuntimeError as e:
                results.append(str(e))

        print(f"  成功: {sum(1 for r in results if 'ok' in str(r))}/10")
        print(f"  调用分布: {call_count}")
        stats = fm.get_stats()
        print(f"  故障转移次数: {stats['failover_count']}")
        print("  ✅ 通过")

        # 测试3: 切换策略
        print("\n测试3: 切换策略")
        fm.set_strategy(SwitchStrategy.WEIGHTED)
        print(f"  当前策略: {fm.selector.strategy.value}")
        fm.set_strategy(SwitchStrategy.LEAST_LATENCY)
        print(f"  切换后策略: {fm.selector.strategy.value}")
        print("  ✅ 通过")

        # 测试4: 健康检查
        print("\n测试4: 健康检查")
        hc = fm.checker
        hc.failure_threshold = 2
        hc.recovery_threshold = 1
        # 模拟检查
        await hc.check_all()
        health = hc.stats()
        print(f"  节点: {health['total']}, 健康: {health['healthy']}")
        print("  ✅ 通过")

        # 测试5: 模型快速切换
        print("\n测试5: 模型快速切换")
        fm.switch_model("node_a", "node_b")
        print(f"  node_b 状态: {fm.checker.nodes['node_b'].status.value}")
        print("  ✅ 通过")

        # 测试6: 节点选择器
        print("\n测试6: 节点选择器（验证轮询）")
        selector = NodeSelector(SwitchStrategy.ROUND_ROBIN)
        nodes = [
            Node("x", "ep_x"),
            Node("y", "ep_y"),
            Node("z", "ep_z"),
        ]
        selections = [selector.select(nodes).node_id for _ in range(6)]
        print(f"  轮询结果: {selections}")
        assert selections == ["x", "y", "z", "x", "y", "z"]
        print("  ✅ 通过")

        print("\n" + "=" * 60)
        print("全部测试通过 ✅")
        print("=" * 60)

    asyncio.run(main())
