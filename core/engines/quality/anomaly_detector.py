"""
Crusheart Agent OS — AnomalyDetector v1.0
异常模式检测器：实时监控系统运行指标，主动推送告警

设计定位：
- 与 JudgeEngine（judge_engine.py）配合：读取回答评分记录
- 与 RuleEngine（workflow/rule_engine.py）配合：检测结果作为事件触发规则
- 与 QualityScoreDashboard（quality_dashboard.py）配合：读取引擎质量评分
- 与 auto_memory（memory/auto_memory.py）配合：监控记忆检索指标
- 纯 self-contained，依赖可注入

检测维度（6个内置检测器）：
  Q1. 回答质量持续低分     → consecutive_low_score_detector
  Q2. 记忆检索失败率升高   → memory_retrieval_failure_detector
  Q3. 引擎响应时间变慢     → response_time_slowdown_detector
  Q4. 规则命中率异常       → rule_trigger_anomaly_detector
  Q5. 设备操作失败率升高   → device_op_failure_detector
  Q6. 引擎评分骤降         → quality_score_plunge_detector

告警等级：
  info      → 通知但不需关注
  warning   → 建议关注
  critical  → 需立即处理

使用方式：
  detector = AnomalyDetector()
  detector.register_detector("my_detector", my_fn)
  alerts = detector.run_all(context)
  # 或
  alerts = detector.run_single("memory_retrieval_failure", context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ANOMALY_PATH = os.path.join(WORKSPACE, ".anomaly_history.jsonl")
ALERT_PATH = os.path.join(WORKSPACE, ".alerts.jsonl")


# ═══════════════════════════════════════════
# 枚举 & 数据结构
# ═══════════════════════════════════════════

class AlertLevel(str, Enum):
    """告警等级"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """
    告警数据结构

    用于内部记录 + 规则引擎事件 + 用户推送
    """
    alert_id: str
    detector: str                    # 检测器名称
    level: str                       # AlertLevel 值
    title: str                       # 简洁标题
    message: str                     # 详细描述
    metric_name: str                 # 指标名称（如 "avg_score"）
    metric_value: float              # 当前指标值
    threshold: float                 # 阈值
    details: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(BEIJING_TZ).isoformat()

    def is_actionable(self) -> bool:
        return self.level in (AlertLevel.WARNING, AlertLevel.CRITICAL)

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "detector": self.detector,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "details": self.details,
            "generated_at": self.generated_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
        }

    def to_event(self) -> Dict:
        """转为规则引擎事件格式"""
        return {
            "type": f"anomaly.{self.level.value}",
            "source": "anomaly_detector",
            "metadata": {
                "alert_id": self.alert_id,
                "detector": self.detector,
                "level": self.level,
                "title": self.title,
                "message": self.message,
                "metric_name": self.metric_name,
                "metric_value": self.metric_value,
                "threshold": self.threshold,
            },
        }


@dataclass
class DetectorConfig:
    """
    检测器配置

    enabled: 是否启用
    window_size: 滑动窗口大小（样本数）
    threshold: 触发阈值
    min_samples: 最少样本数（低于则不检测）
    cooldown_s: 同指标冷却时间（秒）
    """
    enabled: bool = True
    window_size: int = 10
    threshold: float = 0.5
    min_samples: int = 3
    cooldown_s: int = 600
    extra: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════
# 异常检测器
# ═══════════════════════════════════════════

class AnomalyDetector:
    """
    异常模式检测器

    提供 6 个内置检测器，支持注册自定义检测器。
    每个检测器接收 context（历史数据、当前指标），返回 Alert 列表。

    使用方式：
        detector = AnomalyDetector()
        detector.load_history()
        alerts = detector.run_all(context)
        # 自动写入告警历史记录
    """

    def __init__(self):
        self._detectors: Dict[str, Callable] = {}
        self._configs: Dict[str, DetectorConfig] = {}
        self._last_alert_time: Dict[str, float] = {}  # detector → last_ts
        self._alert_cooldown: Dict[str, float] = {}  # dedup_key → timestamp
        self._emit_count: int = 0  # 当前窗口内 WARNING 发出数
        self._last_emit_reset: float = 0.0
        self._register_builtins()

    # ── 检测器注册 ──

    def register_detector(self, name: str, fn: Callable,
                          config: Optional[DetectorConfig] = None):
        """注册检测器"""
        self._detectors[name] = fn
        self._configs[name] = config or DetectorConfig()
        logger.info(f"[AnomalyDetector] 注册检测器: {name}")

    def get_detector_names(self) -> List[str]:
        return list(self._detectors.keys())

    def get_config(self, name: str) -> Optional[DetectorConfig]:
        return self._configs.get(name)

    def update_config(self, name: str, **kwargs) -> bool:
        """更新检测器配置"""
        cfg = self._configs.get(name)
        if not cfg:
            return False
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return True

    # ── 运行检测器 ──

    def run_all(self, context: Dict[str, Any]) -> List[Alert]:
        """
        运行所有启用的检测器

        Args:
            context: 全局上下文
                {
                    "judge_scores": [...],          # 最近 N 次 JudgeEngine 评分
                    "memory_stats": {...},           # 记忆检索统计
                    "response_times": [...],         # 响应时间样本（ms）
                    "quality_overview": {...},       # QualityScoreDashboard 概览
                    "device_op_history": [...],      # 设备操作记录
                    "rule_stats": {...},             # 规则引擎统计
                    "timestamp": "...",              # 当前时间 ISO
                }

        Returns:
            所有告警列表
        """
        all_alerts: List[Alert] = []
        now = time.time()

        for name, fn in self._detectors.items():
            cfg = self._configs.get(name)
            if not cfg or not cfg.enabled:
                continue

            # 冷却检查
            last_ts = self._last_alert_time.get(name, 0)
            if now - last_ts < cfg.cooldown_s:
                continue

            alerts = []
            try:
                alerts = fn(context, cfg)
                for alert in alerts:
                    if self._should_emit(alert):
                        all_alerts.append(alert)
                        self._record_alert(alert)
            except Exception as e:
                logger.warning(f"[AnomalyDetector] 检测器异常 {name}: {e}")

            # 如果产生了告警，更新冷却时间
            if any(a.is_actionable() for a in alerts):
                self._last_alert_time[name] = now

        return all_alerts

    def run_single(self, name: str, context: Dict[str, Any]) -> List[Alert]:
        """运行单个检测器"""
        fn = self._detectors.get(name)
        cfg = self._configs.get(name)
        if not fn or not cfg:
            return []
        try:
            return fn(context, cfg)
        except Exception as e:
            logger.warning(f"[AnomalyDetector] 单次检测异常 {name}: {e}")
            return []

    def _should_emit(self, alert: Alert) -> bool:
        """是否应该发出告警（防重复 + 速率限制）"""
        if alert.level == AlertLevel.CRITICAL:
            return True

        now = time.time()
        # 每小时重置 emit_count
        if now - self._last_emit_reset > 3600:
            self._emit_count = 0
            self._last_emit_reset = now

        # 去重：同检测器+同内容 hash，1 小时内不重复
        dedup_key = f"{alert.detector}:{hash(alert.message)}"
        last_emit = self._alert_cooldown.get(dedup_key, 0.0)
        if now - last_emit < 3600:
            return False

        # WARNING 每小时不超过 10 条
        if alert.level == AlertLevel.WARNING and self._emit_count >= 10:
            return False

        self._alert_cooldown[dedup_key] = now
        self._emit_count += 1
        return True

    # ── 告警持久化 ──

    def _record_alert(self, alert: Alert):
        """记录告警到文件（dirty counter + tmp+rename 原子写入 + 防截断）"""
        os.makedirs(os.path.dirname(ALERT_PATH) or ".", exist_ok=True)
        tmp_path = ALERT_PATH + ".tmp"
        with open(tmp_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp_path, ALERT_PATH)

        self._trim_file(ALERT_PATH, 500)

    @staticmethod
    def _trim_file(path: str, max_lines: int = 500):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            tmp_path = path + ".trim"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.writelines(lines[-max_lines:])
            os.replace(tmp_path, path)

    def get_recent_alerts(self, limit: int = 20,
                          min_level: str = "info") -> List[Dict]:
        """获取最近告警"""
        if not os.path.exists(ALERT_PATH):
            return []
        levels = {"info": 0, "warning": 1, "critical": 2}
        min_score = levels.get(min_level, 0)

        alerts = []
        with open(ALERT_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    alert = json.loads(line)
                    if levels.get(alert.get("level", "info"), 0) >= min_score:
                        alerts.append(alert)
                except json.JSONDecodeError:
                    continue
        return alerts[-limit:]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        if not os.path.exists(ALERT_PATH):
            return False

        lines = []
        found = False
        with open(ALERT_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    alert = json.loads(line)
                    if alert.get("alert_id") == alert_id:
                        alert["acknowledged"] = True
                        alert["acknowledged_at"] = datetime.now(BEIJING_TZ).isoformat()
                        found = True
                    lines.append(json.dumps(alert, ensure_ascii=False))
                except json.JSONDecodeError:
                    lines.append(line)

        if found:
            with open(ALERT_PATH, "w") as f:
                f.write("\n".join(lines) + "\n")
        return found

    def get_detector_stats(self) -> Dict[str, Any]:
        """获取检测器统计"""
        total = len(self._detectors)
        enabled = sum(1 for c in self._configs.values() if c.enabled)

        # 从告警文件统计
        alert_counts = {}
        if os.path.exists(ALERT_PATH):
            with open(ALERT_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        alert = json.loads(line)
                        detector = alert.get("detector", "unknown")
                        level = alert.get("level", "info")
                        if detector not in alert_counts:
                            alert_counts[detector] = {"info": 0, "warning": 0, "critical": 0}
                        if level in alert_counts[detector]:
                            alert_counts[detector][level] += 1
                    except json.JSONDecodeError:
                        continue

        return {
            "total_detectors": total,
            "enabled_detectors": enabled,
            "disabled_detectors": total - enabled,
            "alert_counts_by_detector": alert_counts,
        }

    # ── 内置检测器 ──

    def _register_builtins(self):
        """注册 6 个内置检测器"""
        self.register_detector(
            "consecutive_low_score",
            self._detect_consecutive_low_score,
            DetectorConfig(
                window_size=10,
                threshold=5.0,       # 评分阈值（/10）
                min_samples=5,
                cooldown_s=1800,
            ),
        )
        self.register_detector(
            "memory_retrieval_failure",
            self._detect_memory_retrieval_failure,
            DetectorConfig(
                window_size=10,
                threshold=0.4,       # 失败率阈值
                min_samples=5,
                cooldown_s=1800,
            ),
        )
        self.register_detector(
            "response_time_slowdown",
            self._detect_response_time_slowdown,
            DetectorConfig(
                window_size=10,
                threshold=2.0,       # 倍数阈值（> 历史均值×2）
                min_samples=5,
                cooldown_s=1800,
            ),
        )
        self.register_detector(
            "rule_trigger_anomaly",
            self._detect_rule_trigger_anomaly,
            DetectorConfig(
                window_size=60,      # 60 分钟窗口
                threshold=20,        # 1 小时触发次数阈值
                min_samples=1,
                cooldown_s=3600,
            ),
        )
        self.register_detector(
            "device_op_failure",
            self._detect_device_op_failure,
            DetectorConfig(
                window_size=10,
                threshold=3,         # 连续失败次数阈值
                min_samples=3,
                cooldown_s=1800,
            ),
        )
        self.register_detector(
            "quality_score_plunge",
            self._detect_quality_score_plunge,
            DetectorConfig(
                window_size=5,
                threshold=0.2,       # 单次降幅阈值（0.2 = 20%）
                min_samples=3,
                cooldown_s=3600,
            ),
        )

    # ── 检测器 Q1: 回答质量持续低分 ──

    @staticmethod
    def _detect_consecutive_low_score(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测回答质量持续低分

        从 context.judge_scores 读取最近 N 次评分，
        如果均值低于阈值则告警。

        context.judge_scores 格式：
        [
            {"faithfulness": 8, "relevance": 9, "completeness": 7, "ts": "..."},
            ...
        ]
        """
        scores = context.get("judge_scores", [])
        if len(scores) < cfg.min_samples:
            return []

        # 取窗口内样本
        window = scores[-cfg.window_size:]

        # 计算最近 window 次的平均总分
        avg_totals = []
        for s in window:
            total = (
                s.get("faithfulness", 0)
                + s.get("relevance", 0)
                + s.get("completeness", 0)
            ) / 3.0
            avg_totals.append(total)

        current_avg = sum(avg_totals) / len(avg_totals)

        if current_avg < cfg.threshold:
            alert = Alert(
                alert_id=f"low_score_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                detector="consecutive_low_score",
                level=AlertLevel.WARNING if current_avg > cfg.threshold * 0.6 else AlertLevel.CRITICAL,
                title="回答质量持续偏低",
                message=f"最近 {len(window)} 次回答平均评分为 {current_avg:.1f}/10，低于阈值 {cfg.threshold}",
                metric_name="avg_score",
                metric_value=current_avg,
                threshold=cfg.threshold,
                details={
                    "window_size": len(window),
                    "min_score": min(avg_totals),
                    "max_score": max(avg_totals),
                },
            )
            return [alert]

        return []

    # ── 检测器 Q2: 记忆检索失败率升高 ──

    @staticmethod
    def _detect_memory_retrieval_failure(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测记忆检索失败率

        从 context.memory_stats 读取检索统计：
            {
                "recent_retrievals": [
                    {"total": 10, "failed": 2, "ts": "..."},
                    ...
                ]
            }
        """
        recent = context.get("memory_stats", {}).get("recent_retrievals", [])
        if len(recent) < cfg.min_samples:
            return []

        window = recent[-cfg.window_size:]
        total_attempts = sum(r.get("total", 0) for r in window)
        total_failed = sum(r.get("failed", 0) for r in window)

        if total_attempts == 0:
            return []

        failure_rate = total_failed / total_attempts

        if failure_rate > cfg.threshold:
            level = (
                AlertLevel.CRITICAL if failure_rate > cfg.threshold * 1.5
                else AlertLevel.WARNING
            )
            alert = Alert(
                alert_id=f"mem_fail_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                detector="memory_retrieval_failure",
                level=level,
                title="记忆检索失败率升高",
                message=f"最近 {len(window)} 批检索失败率为 {failure_rate:.0%}，超过阈值 {cfg.threshold:.0%}",
                metric_name="failure_rate",
                metric_value=failure_rate,
                threshold=cfg.threshold,
                details={
                    "total_attempts": total_attempts,
                    "total_failed": total_failed,
                    "window_size": len(window),
                },
            )
            return [alert]

        return []

    # ── 检测器 Q3: 引擎响应时间变慢 ──

    @staticmethod
    def _detect_response_time_slowdown(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测引擎响应时间变慢

        从 context.response_times 读取：
            [1200, 1500, 3000, ...]  # ms
        如果窗口内均值 > 历史均值 × threshold 则告警。
        """
        times = context.get("response_times", [])
        if len(times) < cfg.min_samples * 2:
            return []

        # 确保窗口不超样本数
        effective_window = min(cfg.window_size, len(times) // 2)
        window = times[-effective_window:]
        history = times[:-effective_window]

        if not window or not history:
            return []

        window_avg = sum(window) / len(window)
        history_avg = sum(history) / len(history)

        if history_avg <= 0:
            return []

        slowdown_ratio = window_avg / history_avg

        if slowdown_ratio > cfg.threshold:
            level = (
                AlertLevel.CRITICAL if slowdown_ratio > cfg.threshold * 1.5
                else AlertLevel.WARNING
            )
            alert = Alert(
                alert_id=f"slowdown_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                detector="response_time_slowdown",
                level=level,
                title="引擎响应时间变慢",
                message=f"最近 {len(window)} 次响应均值 {window_avg:.0f}ms，"
                        f"是历史均值 {history_avg:.0f}ms 的 {slowdown_ratio:.1f} 倍",
                metric_name="response_time_ratio",
                metric_value=slowdown_ratio,
                threshold=cfg.threshold,
                details={
                    "window_avg_ms": window_avg,
                    "history_avg_ms": history_avg,
                    "window_size": len(window),
                    "history_size": len(history),
                },
            )
            return [alert]

        return []

    # ── 检测器 Q4: 规则命中率异常 ──

    @staticmethod
    def _detect_rule_trigger_anomaly(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测规则命中率异常

        从 context.rule_stats 读取最近 1 小时触发次数。
        """
        stats = context.get("rule_stats", {})
        triggers_last_hour = stats.get("triggers_last_hour", 0)
        total_rules = stats.get("total_rules", 0)

        if total_rules == 0:
            return []

        avg_per_rule = triggers_last_hour / total_rules if total_rules > 0 else 0

        if avg_per_rule > cfg.threshold:
            alert = Alert(
                alert_id=f"rule_burst_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                detector="rule_trigger_anomaly",
                level=AlertLevel.WARNING,
                title="规则触发频率异常",
                message=f"最近 1 小时规则触发 {triggers_last_hour} 次，"
                        f"平均每规则 {avg_per_rule:.1f} 次，超过阈值 {cfg.threshold}",
                metric_name="triggers_per_rule_per_hour",
                metric_value=avg_per_rule,
                threshold=cfg.threshold,
                details={
                    "triggers_last_hour": triggers_last_hour,
                    "total_rules": total_rules,
                },
            )
            return [alert]

        return []

    # ── 检测器 Q5: 设备操作失败率升高 ──

    @staticmethod
    def _detect_device_op_failure(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测设备操作失败率

        从 context.device_op_history 读取：
            [{"success": True}, {"success": False}, ...]
        """
        history = context.get("device_op_history", [])
        if len(history) < cfg.min_samples:
            return []

        window = history[-cfg.window_size:]
        consecutive_failures = 0
        for op in reversed(window):
            if not op.get("success", True):
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= cfg.threshold:
            level = (
                AlertLevel.CRITICAL if consecutive_failures >= cfg.threshold * 2
                else AlertLevel.WARNING
            )
            alert = Alert(
                alert_id=f"device_fail_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                detector="device_op_failure",
                level=level,
                title="设备操作连续失败",
                message=f"最近连续 {consecutive_failures} 次设备操作失败，超过阈值 {cfg.threshold}",
                metric_name="consecutive_failures",
                metric_value=consecutive_failures,
                threshold=cfg.threshold,
                details={
                    "window_size": len(window),
                    "total_in_window": len(window),
                },
            )
            return [alert]

        return []

    # ── 检测器 Q6: 引擎评分骤降 ──

    @staticmethod
    def _detect_quality_score_plunge(
        context: Dict, cfg: DetectorConfig
    ) -> List[Alert]:
        """
        检测引擎评分骤降

        从 context.quality_overview 读取引擎评分历史，检测单次降幅。
        """
        overview = context.get("quality_overview", {})
        overall = overview.get("overall_score", 1.0)

        # 读取历史评分记录
        history_path = os.path.join(WORKSPACE, ".quality_scores.json")
        if not os.path.exists(history_path):
            return []

        try:
            with open(history_path) as f:
                quality_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        history = quality_data.get("history", [])
        if len(history) < cfg.min_samples:
            return []

        window = history[-cfg.window_size:]
        recent_scores = [h.get("score", 0) for h in window]

        # 检测骤降：当前分 vs 窗口起点
        if len(recent_scores) >= 2:
            start = recent_scores[0]
            end = recent_scores[-1]
            if start > 0:
                drop_ratio = (start - end) / start
                if drop_ratio > cfg.threshold:
                    level = (
                        AlertLevel.CRITICAL if drop_ratio > cfg.threshold * 1.5
                        else AlertLevel.WARNING
                    )
                    alert = Alert(
                        alert_id=f"plunge_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                        detector="quality_score_plunge",
                        level=level,
                        title="引擎评分骤降",
                        message=f"最近 {len(window)} 次评分从 {start:.2f} 降至 {end:.2f}，降幅 {drop_ratio:.0%}",
                        metric_name="score_drop_ratio",
                        metric_value=drop_ratio,
                        threshold=cfg.threshold,
                        details={
                            "score_start": start,
                            "score_end": end,
                            "window_size": len(window),
                        },
                    )
                    return [alert]

        # 检测连续下降趋势
        if len(recent_scores) >= 4:
            # 简单线性趋势检测：最近 4 次是否持续下降
            if all(recent_scores[i] >= recent_scores[i + 1] for i in range(len(recent_scores) - 1)):
                total_drop = (recent_scores[0] - recent_scores[-1]) / recent_scores[0] if recent_scores[0] > 0 else 0
                if total_drop > cfg.threshold * 0.8:
                    alert = Alert(
                        alert_id=f"downtrend_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                        detector="quality_score_plunge",
                        level=AlertLevel.WARNING,
                        title="引擎评分持续下降",
                        message=f"最近 {len(recent_scores)} 次评分连续下降，"
                                f"从 {recent_scores[0]:.2f} 到 {recent_scores[-1]:.2f}",
                        metric_name="score_drop_ratio",
                        metric_value=total_drop,
                        threshold=cfg.threshold,
                        details={
                            "score_sequence": recent_scores,
                            "window_size": len(window),
                        },
                    )
                    return [alert]

        return []

    # ── 集成: 检测结果推送规则引擎 ──

    def alerts_to_events(self, alerts: List[Alert]) -> List[Dict]:
        """将告警转为规则引擎事件列表"""
        return [a.to_event() for a in alerts if a.is_actionable()]

    def alerts_to_messages(self, alerts: List[Alert]) -> List[Dict]:
        """将告警转为推送消息列表（供 message() 使用）"""
        messages = []
        for a in alerts:
            if not a.is_actionable():
                continue
            level_icon = {"warning": "⚠️", "critical": "🚨"}.get(a.level, "ℹ️")
            messages.append({
                "channel": "last",
                "message": f"{level_icon} {a.title}\n{a.message}",
            })
        return messages


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
    import uuid

    print("=" * 60)
    print("AnomalyDetector v1.0 — 快速验证")
    print("=" * 60)

    detector = AnomalyDetector()

    # 测试1: 所有检测器已注册
    names = detector.get_detector_names()
    print(f"\n[测试1] 检测器: {len(names)} 个 → {names}")

    # 测试2: 回答质量持续低分
    context = {
        "judge_scores": [
            {"faithfulness": s, "relevance": s, "completeness": s, "ts": "..."}
            for s in [3, 2, 4, 3, 2, 3, 4, 2, 3, 2]
        ],
    }
    alerts = detector.run_single("consecutive_low_score", context)
    print(f"\n[测试2] 回答质量持续低分: {len(alerts)} 条告警")
    for a in alerts:
        print(f"  [{a.level}] {a.title}: {a.message[:60]}...")

    # 测试3: 记忆检索失败
    context2 = {
        "memory_stats": {
            "recent_retrievals": [
                {"total": 10, "failed": 5, "ts": "..."},
                {"total": 8, "failed": 4, "ts": "..."},
                {"total": 12, "failed": 5, "ts": "..."},
                {"total": 10, "failed": 6, "ts": "..."},
            ]
        },
    }
    alerts2 = detector.run_single("memory_retrieval_failure", context2)
    print(f"\n[测试3] 记忆检索失败率: {len(alerts2)} 条告警")
    for a in alerts2:
        print(f"  [{a.level}] {a.title}: {a.message[:60]}...")

    # 测试4: 响应时间变慢
    context3 = {
        "response_times": [1200, 1100, 1300, 1250, 1500, 3000, 3500, 4000, 3800, 4200],
    }
    alerts3 = detector.run_single("response_time_slowdown", context3)
    print(f"\n[测试4] 响应时间变慢: {len(alerts3)} 条告警")
    for a in alerts3:
        print(f"  [{a.level}] {a.title}: {a.message[:60]}...")

    # 测试5: 引擎评分骤降
    # 先写入一些历史评分
    import os
    os.makedirs(os.path.dirname(ANOMALY_PATH) or ".", exist_ok=True)
    with open(WORKSPACE + "/.quality_scores.json", "w") as f:
        json.dump({
            "history": [
                {"timestamp": f"2026-05-18T{10+i:02d}:00:00", "score": max(0.1, 0.9 - i * 0.15), "engine": "test"}
                for i in range(6)  # 0.9 → 0.75 → 0.6 → 0.45 → 0.3 → 0.15
            ],
            "overall_score": 0.15,
        }, f, ensure_ascii=False, indent=2)

    context5 = {"quality_overview": {"overall_score": 0.15}}
    alerts5 = detector.run_single("quality_score_plunge", context5)
    print(f"\n[测试5] 引擎评分骤降: {len(alerts5)} 条告警")
    for a in alerts5:
        print(f"  [{a.level}] {a.title}: {a.message[:60]}...")

    # 测试6: 设备操作失败
    context6 = {
        "device_op_history": [
            {"success": True},
            {"success": True},
            {"success": False},
            {"success": False},
            {"success": False},
            {"success": False},
        ],
    }
    alerts6 = detector.run_single("device_op_failure", context6)
    print(f"\n[测试6] 设备操作失败: {len(alerts6)} 条告警")
    for a in alerts6:
        print(f"  [{a.level}] {a.title}: {a.message[:60]}...")

    # 测试7: 转为推送消息
    actionable = [a for a in (alerts + alerts2 + alerts3 + alerts5 + alerts6) if a.is_actionable()]
    events = detector.alerts_to_events(actionable)
    msgs = detector.alerts_to_messages(actionable)
    print(f"\n[测试7] 事件转换: {len(events)} 个 | 推送消息: {len(msgs)} 条")
    for m in msgs[:2]:
        print(f"  {m['message'][:60]}...")

    # 清理
    import os
    for f in [ANOMALY_PATH, ALERT_PATH]:
        if os.path.exists(f):
            os.remove(f)

    print(f"\n{'=' * 60}")
    print("✅ 异常检测器验证完成")
