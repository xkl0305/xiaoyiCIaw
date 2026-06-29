#!/usr/bin/env python3
"""
reflection_checker.py — 执行中反思检查器 v1.0

在 WorkflowOrchestrator 每步执行后调用，评估执行结果质量，
输出反思决策（PASS / WARN / REPLAN / ABORT），供编排器调整后续步骤。

用法：
  python3 scripts/reflection_checker.py evaluate --node-id "step_1" --result '{"status":"ok","data":{...}}'
  python3 scripts/reflection_checker.py --check-env

集成：
  from scripts.reflection_checker import ReflectionChecker
  checker = ReflectionChecker()
  decision = checker.evaluate(node_id, exec_result, context)
"""

import json, os, sys, math
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum

BEIJING_TZ = timezone(timedelta(hours=8))

# ================================================================
# 反思决策级别
# ================================================================

class ReflectionLevel(Enum):
    PASS = "pass"           # 执行正常，无需干预
    WARN = "warn"           # 质量偏低，标记后续节点
    REPLAN = "replan"       # 结果不可靠，需要调整/跳过后续节点
    ABORT = "abort"         # 严重失败，终止整个工作流


class ReflectionDecision:
    """单次反思的决策结果"""

    def __init__(self, level: ReflectionLevel, node_id: str,
                 confidence: float = 1.0,
                 reason: str = "",
                 affected_nodes: Optional[List[str]] = None,
                 suggested_action: str = ""):
        self.level = level
        self.node_id = node_id
        self.confidence = confidence
        self.reason = reason
        self.affected_nodes = affected_nodes or []
        self.suggested_action = suggested_action
        self.timestamp = datetime.now(BEIJING_TZ).isoformat()

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "node_id": self.node_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "affected_nodes": self.affected_nodes,
            "suggested_action": self.suggested_action,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"[{self.level.value.upper()}] {self.node_id} (conf={self.confidence:.2f}): {self.reason[:60]}"


# ================================================================
# 评分器
# ================================================================

def _score_confidence(result: Any) -> float:
    """对执行结果做置信度评分，返回 0.0 ~ 1.0

    评分依据（权重从高到低）：
      1. 显式错误 → 0.0
      2. 空结果（None/空列表/空dict/空字符串） → 0.1
      3. 异常码 → 0.2 ~ 0.5
      4. 结构化程度 → 0.5 ~ 0.8
      5. 内容质量 → 0.8 ~ 1.0
    """
    if result is None:
        return 0.0

    if isinstance(result, dict):
        # 显式错误
        if result.get("error"):
            return 0.0
        if result.get("status") in ("error", "failed"):
            return 0.1

        # 空结果
        if not result or len(result) == 0:
            return 0.1
        # 只有 status 没有实际数据
        if len(result) <= 2 and "status" in result:
            return 0.3

        # 有 content/result/data 字段
        if "content" in result and result["content"]:
            return _score_content_quality(result["content"])
        if "result" in result and result["result"]:
            return _score_content_quality(result["result"])
        if "data" in result and result["data"]:
            return _score_content_quality(result["data"])

        # 有 stdout
        if "stdout" in result and result["stdout"]:
            return min(0.7, _score_content_quality(result["stdout"]) + 0.2)

        return 0.5  # 有结构但数据不多

    if isinstance(result, list):
        if len(result) == 0:
            return 0.1
        return min(0.9, 0.5 + 0.05 * min(len(result), 8))

    if isinstance(result, str):
        if not result.strip():
            return 0.1
        return _score_content_quality(result)

    # 数值/布尔等基本类型
    if isinstance(result, bool):
        return 0.8 if result else 0.2
    if isinstance(result, (int, float)):
        return 0.7 if result != 0 else 0.3

    return 0.5  # 未知类型


def _score_content_quality(content: Any) -> float:
    """评估内容质量的置信度

    依据：
      - 内容长度（太短不靠谱）
      - 结构复杂度
      - 是否包含"错误""失败"等敏感词
    """
    if not content:
        return 0.1

    text = str(content)
    length = len(text)

    # 敏感词惩罚
    penalty_words = ["错误", "失败", "无法", "不存在", "未找到",
                     "error", "failed", "exception", "not found",
                     "timeout", "超时", "崩溃", "异常"]
    penalty = 0
    for word in penalty_words:
        if word in text.lower():
            penalty += 0.1

    # 长度评分
    if length < 10:
        length_score = 0.2
    elif length < 50:
        length_score = 0.4
    elif length < 200:
        length_score = 0.6
    elif length < 1000:
        length_score = 0.8
    else:
        length_score = 0.9

    score = length_score - penalty
    return max(0.0, min(1.0, score))


def _detect_anomalies(result: Any, context: dict = None) -> List[str]:
    """检测执行结果中的异常信号"""
    anomalies = []

    if result is None:
        anomalies.append("result_is_none")

    if isinstance(result, dict):
        if result.get("error"):
            anomalies.append(f"has_error: {str(result['error'])[:60]}")
        if result.get("status") in ("error", "failed", "timeout"):
            anomalies.append(f"status_{result['status']}")
        if result.get("code") and int(result.get("code", 0)) != 0:
            anomalies.append(f"exit_code_{result['code']}")
        # 空字典但存在
        if len(result) == 0:
            anomalies.append("empty_dict")
        # 只有 status 字段
        if len(result) <= 2 and "status" in result:
            anomalies.append("status_only")

    if isinstance(result, str) and not result.strip():
        anomalies.append("empty_string")

    if isinstance(result, list) and len(result) == 0:
        anomalies.append("empty_list")

    return anomalies


def _is_all_errors(result: Any) -> bool:
    """检查结果中是否全是错误信号（没有有效数据）"""
    if result is None:
        return True

    if isinstance(result, dict):
        if result.get("error"):
            return True
        if result.get("status") in ("error", "failed"):
            return True
        # 只有 error 相关字段，没有 content/data/result
        has_data = any(k in result for k in ("content", "data", "result", "stdout"))
        has_error = any(k in result for k in ("error", "errors"))
        return has_error and not has_data

    return False


# ================================================================
# 反思检查器
# ================================================================

class ReflectionChecker:
    """执行中反思检查器

    评估单步执行结果，给出反思决策。
    支持从配置文件读取阈值，默认值适用于大部分场景。
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        # 阈值配置（可覆盖）
        self._pass_threshold = float(self.config.get("pass_threshold", 0.7))
        self._warn_threshold = float(self.config.get("warn_threshold", 0.3))
        self._abort_if_no_downstream = self.config.get("abort_if_no_downstream", False)
        self._enabled = self.config.get("enabled", True)

        # 统计信息
        self._stats = {
            "total_evaluations": 0,
            "pass": 0,
            "warn": 0,
            "replan": 0,
            "abort": 0,
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def evaluate(self, node_id: str, result: Any,
                 context: dict = None,
                 downstream_nodes: Optional[List[str]] = None) -> ReflectionDecision:
        """执行反思评估

        Args:
            node_id: 当前节点 ID
            result: 执行结果
            context: 执行上下文（可选）
            downstream_nodes: 依赖此节点的下游节点 ID 列表

        Returns:
            ReflectionDecision
        """
        if not self._enabled:
            return ReflectionDecision(
                ReflectionLevel.PASS, node_id, 1.0, "reflection disabled"
            )

        self._stats["total_evaluations"] += 1

        # 1. 异常检测
        anomalies = _detect_anomalies(result, context)

        # 2. 置信度评分
        confidence = _score_confidence(result)

        # 3. 是否全是错误
        all_errors = _is_all_errors(result)

        # 4. 决策
        affected = downstream_nodes or []

        # CRITICAL: 全部是错误且不可恢复
        if all_errors and confidence < 0.1:
            self._stats["abort"] += 1
            return ReflectionDecision(
                ReflectionLevel.ABORT, node_id,
                confidence=confidence,
                reason=f"严重失败: {'; '.join(anomalies[:3])}",
                affected_nodes=affected,
                suggested_action="terminate_workflow",
            )

        # REPLAN: 结果不可靠，需要调整后续节点
        if confidence < self._warn_threshold:
            self._stats["replan"] += 1
            action = "skip_or_reroute_downstream"
            if anomalies:
                action = f"reroute: {anomalies[0][:40]}"
            return ReflectionDecision(
                ReflectionLevel.REPLAN, node_id,
                confidence=confidence,
                reason=f"结果置信度过低 ({confidence:.2f}): {'; '.join(anomalies[:2])}",
                affected_nodes=affected,
                suggested_action=action,
            )

        # WARN: 质量偏低，标记后续节点
        if confidence < self._pass_threshold:
            self._stats["warn"] += 1
            return ReflectionDecision(
                ReflectionLevel.WARN, node_id,
                confidence=confidence,
                reason=f"质量偏低 (conf={confidence:.2f}): {'; '.join(anomalies[:1])}" if anomalies else f"质量偏低 (conf={confidence:.2f})",
                affected_nodes=affected,
                suggested_action="reduce_dependency_strictness",
            )

        # PASS
        self._stats["pass"] += 1
        return ReflectionDecision(
            ReflectionLevel.PASS, node_id,
            confidence=confidence,
            reason="OK",
            affected_nodes=affected,
        )

    def get_stats(self) -> dict:
        """获取统计信息"""
        return dict(self._stats)

    def reset_stats(self):
        """重置统计"""
        for k in self._stats:
            self._stats[k] = 0

    def to_config_dict(self) -> dict:
        """返回当前配置"""
        return {
            "enabled": self._enabled,
            "pass_threshold": self._pass_threshold,
            "warn_threshold": self._warn_threshold,
            "abort_if_no_downstream": self._abort_if_no_downstream,
        }


# ================================================================
# CLI 入口
# ================================================================

def cli_evaluate(args: List[str]) -> dict:
    """CLI 评估入口"""
    import argparse
    parser = argparse.ArgumentParser(description="反思检查器 CLI")
    parser.add_argument("action", choices=["evaluate", "check-env", "stats"])
    parser.add_argument("--node-id", help="节点 ID")
    parser.add_argument("--result", help="执行结果 JSON 字符串")
    parser.add_argument("--result-file", help="执行结果 JSON 文件路径")
    parser.add_argument("--downstream", nargs="*", default=[],
                        help="下游节点 ID 列表")
    parser.add_argument("--config", help="配置文件路径")

    if args[0:1] == ["evaluate"] and len(args) > 1:
        # 直接模式: evaluate --node-id xxx --result '{"...":...}'
        pass

    parsed = parser.parse_args(args)

    config = {}
    if parsed.config:
        with open(parsed.config, encoding="utf-8") as f:
            config = json.load(f)

    checker = ReflectionChecker(config)

    if parsed.action == "check-env":
        return {
            "status": "ok",
            "checker": "reflection_checker v1.0",
            "config": checker.to_config_dict(),
        }

    if parsed.action == "stats":
        return checker.get_stats()

    # evaluate
    if not parsed.node_id:
        return {"error": "需要 --node-id"}

    result = None
    if parsed.result:
        try:
            result = json.loads(parsed.result)
        except json.JSONDecodeError:
            result = parsed.result
    elif parsed.result_file:
        with open(parsed.result_file, encoding="utf-8") as f:
            result = json.load(f)
    else:
        return {"error": "需要 --result 或 --result-file"}

    decision = checker.evaluate(
        parsed.node_id, result,
        downstream_nodes=parsed.downstream or None,
    )
    return decision.to_dict()


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

    if len(sys.argv) < 2:
        print(json.dumps({"error": "需要 action (evaluate|check-env|stats)"},
                         ensure_ascii=False))
        sys.exit(1)

    result = cli_evaluate(sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False, indent=2))
