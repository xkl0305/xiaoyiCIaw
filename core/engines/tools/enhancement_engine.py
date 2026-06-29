"""
Crusheart 增强引擎 — 事件触发 + 告警分级 + 闭环验证

注入来源：
  - alert_manager.py     → AlertEngine (告警分级 + incident 全生命周期)
  - notification_manager → NotificationRouter (多渠道路由 + 去重冷却)
  - event_trigger.py     → EventEngine (事件驱动触发)
  - smart_scheduler.py   → SmartScheduler (依赖调度 + 优先级队列)

架构层级：L4 Infrastructure
依赖：无外部框架，纯 Python 标准库
集成方式：init_engines.py 统一加载，.engine_state.json 注册
"""

import os
import re
import json
import time
import heapq
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import logging

# =============================================================================
# 1. AlertEngine — 告警分级 + Incident 全生命周期
# =============================================================================

class AlertSeverity(str, Enum):
    """告警严重级别"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class IncidentStatus(str, Enum):
    """Incident 状态"""
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """统一告警对象"""
    alert_type: str           # 告警类型: engine_failure / tool_timeout / memory_corrupt / ...
    severity: AlertSeverity   # 严重级别
    message: str              # 描述
    source: str               # 来源模块
    details: dict             # 详情数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AlertEngine:
    """告警引擎 — 分级告警 + Incident 自动管理"""

    def __init__(self, state_dir: str = ""):
        self.state_dir = state_dir or self._default_state_dir()
        self._ensure_dir()

    def _default_state_dir(self) -> str:
        """默认状态目录"""
        base = os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
        return os.path.join(base, ".alerts")

    def _ensure_dir(self):
        os.makedirs(self.state_dir, exist_ok=True)

    # ---- 告警生成 ----

    def create_alert(self, alert_type: str, severity: AlertSeverity,
                     message: str, source: str = "",
                     details: Optional[dict] = None) -> Alert:
        """创建告警"""
        return Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            source=source,
            details=details or {}
        )

    def save_alerts(self, alerts: List[Alert]) -> dict:
        """保存告警到 latest + history"""
        now = datetime.now()
        report = {
            "generated_at": now.isoformat(),
            "total": len(alerts),
            "critical_count": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
            "warning_count": sum(1 for a in alerts if a.severity == AlertSeverity.WARNING),
            "info_count": sum(1 for a in alerts if a.severity == AlertSeverity.INFO),
            "alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity.value,
                    "message": a.message,
                    "source": a.source,
                    "details": a.details,
                    "timestamp": a.timestamp
                }
                for a in alerts
            ]
        }

        # latest
        with open(os.path.join(self.state_dir, "latest_alerts.json"), "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # history
        history_dir = os.path.join(self.state_dir, "history")
        os.makedirs(history_dir, exist_ok=True)
        history_path = os.path.join(history_dir, f"{now.strftime('%Y%m%d_%H%M%S')}_alerts.json")
        with open(history_path, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    # ---- Incident 管理 ----

    def _incidents_path(self) -> str:
        return os.path.join(self.state_dir, "incidents.json")

    def _load_incidents(self) -> List[dict]:
        path = self._incidents_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_incidents(self, incidents: List[dict]):
        with open(self._incidents_path(), "w") as f:
            json.dump(incidents, f, ensure_ascii=False, indent=2)

    def manage_incidents(self, alerts: List[Alert]) -> dict:
        """
        Incident 闭环管理：
        - 有 critical 告警 → 创建新 incident（相同类型去重）
        - 无 critical 告警 → 自动关闭 open incidents
        """
        incidents = self._load_incidents()
        now = datetime.now()
        created = False
        resolved = False

        has_critical = any(a.severity == AlertSeverity.CRITICAL for a in alerts)

        if has_critical:
            open_types = {inc.get("type") for inc in incidents if inc.get("status") == IncidentStatus.OPEN.value}
            for alert in alerts:
                if alert.severity == AlertSeverity.CRITICAL and alert.alert_type not in open_types:
                    incidents.append({
                        "id": f"INC-{now.strftime('%Y%m%d%H%M%S')}-{len(incidents)}",
                        "type": alert.alert_type,
                        "severity": alert.severity.value,
                        "message": alert.message,
                        "status": IncidentStatus.OPEN.value,
                        "opened_at": now.isoformat(),
                        "resolved_at": None,
                        "resolution_note": None
                    })
                    created = True
                    open_types.add(alert.alert_type)
        else:
            for inc in incidents:
                if inc.get("status") == IncidentStatus.OPEN.value:
                    inc["status"] = IncidentStatus.RESOLVED.value
                    inc["resolved_at"] = now.isoformat()
                    inc["resolution_note"] = "告警已自动恢复"
                    resolved = True

        self._save_incidents(incidents)

        open_count = sum(1 for i in incidents if i.get("status") == IncidentStatus.OPEN.value)

        return {
            "total_incidents": len(incidents),
            "open_incidents": open_count,
            "resolved_incidents": len(incidents) - open_count,
            "created": created,
            "resolved": resolved
        }

    def get_status(self) -> dict:
        """获取告警引擎状态"""
        latest_path = os.path.join(self.state_dir, "latest_alerts.json")
        latest = {}
        if os.path.exists(latest_path):
            try:
                with open(latest_path) as f:
                    latest = json.load(f)
            except Exception:
                logging.exception("[enhancement_engine.py] suppressed")
                pass

        incidents = self._load_incidents()
        return {
            "latest_alerts": latest.get("total", 0),
            "critical": latest.get("critical_count", 0),
            "warning": latest.get("warning_count", 0),
            "open_incidents": sum(1 for i in incidents if i.get("status") == "open"),
            "total_incidents": len(incidents)
        }


# =============================================================================
# 2. NotificationRouter — 多渠道路由 + 去重冷却
# =============================================================================

class NotificationRouter:
    """通知路由 — 支持多渠道 + 去重冷却"""

    DEFAULT_CHANNELS = ["console"]

    def __init__(self, state_dir: str = ""):
        self.state_dir = state_dir or (
            os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
            + "/.notifications"
        )
        self._ensure_dir()
        self.history = self._load_history()

    def _ensure_dir(self):
        os.makedirs(self.state_dir, exist_ok=True)

    def _history_path(self) -> str:
        return os.path.join(self.state_dir, "notification_history.json")

    def _load_history(self) -> List[dict]:
        path = self._history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            logging.exception("[enhancement_engine.py] suppressed")
            return []

    def _save_history(self):
        # 保留最近 200 条
        self.history = self.history[-200:]
        with open(self._history_path(), "w") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def is_in_cooldown(self, alert_type: str, window_minutes: int = 30) -> bool:
        """检查指定告警类型是否在冷却期内"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=window_minutes)

        for entry in reversed(self.history):
            if entry.get("type") != alert_type:
                continue
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts > cutoff:
                    return True
            except Exception:
                logging.exception("[enhancement_engine.py] suppressed")
                continue
        return False

    def get_channels_for(self, alert_type: str,
                         routing_config: Optional[dict] = None) -> List[str]:
        """根据告警类型获取目标渠道"""
        if not routing_config:
            return self.DEFAULT_CHANNELS
        return routing_config.get(alert_type, {}).get("channels", self.DEFAULT_CHANNELS)

    def route(self, alert_type: str, severity: str, message: str,
              channels: Optional[List[str]] = None,
              skip_cooldown: bool = False) -> dict:
        """
        路由通知到指定渠道

        Args:
            alert_type: 告警类型
            severity: 严重级别
            message: 消息内容
            channels: 目标渠道列表
            skip_cooldown: 是否跳过冷却检查

        Returns:
            {sent: int, failed: int, cooldown_skipped: bool, channels: [...]}
        """
        result = {
            "sent": 0,
            "failed": 0,
            "cooldown_skipped": False,
            "channels": []
        }

        # 冷却检查
        if not skip_cooldown and self.is_in_cooldown(alert_type):
            result["cooldown_skipped"] = True
            return result

        channels = channels or self.DEFAULT_CHANNELS
        for ch in channels:
            ok = self._do_send(ch, severity, message)
            if ok:
                result["sent"] += 1
            else:
                result["failed"] += 1
            result["channels"].append({"channel": ch, "sent": ok})

        # 记录历史
        self.history.append({
            "type": alert_type,
            "severity": severity,
            "channels": channels,
            "timestamp": datetime.now().isoformat()
        })
        self._save_history()

        return result

    def _do_send(self, channel: str, severity: str, message: str) -> bool:
        """
        实际发送到渠道。
        扩展点：后续可接入 feishu、webhook 等真实发送。
        """
        if channel == "console":
            icon = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(severity, "📢")
            print(f"{icon} [{channel}] {severity.upper()}: {message}")
            return True
        elif channel == "log":
            # 写入系统日志
            log_path = os.path.join(self.state_dir, "notification_log.txt")
            with open(log_path, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {severity.upper()}: {message}\n")
            return True

        # 未实现的渠道
        return False

    def get_history(self, limit: int = 20) -> List[dict]:
        """获取通知历史"""
        return self.history[-limit:]


# =============================================================================
# 3. EventEngine — 事件驱动触发器
# =============================================================================

class EventType(str, Enum):
    """事件类型"""
    FILE_CHANGE = "file_change"
    SCHEDULE = "schedule"
    THRESHOLD = "threshold"
    ERROR = "error"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class Event:
    """事件"""
    id: str
    type: EventType
    source: str
    data: dict
    timestamp: float = field(default_factory=time.time)


@dataclass
class Trigger:
    """触发器"""
    id: str
    name: str
    event_type: EventType
    condition_fn: Callable  # fn(event) -> bool
    action_fn: Callable     # fn(event) -> Any
    priority: int = 0
    cooldown_seconds: float = 0
    last_triggered: float = 0
    trigger_count: int = 0


class EventEngine:
    """事件引擎 — 事件驱动的触发器系统"""

    def __init__(self):
        self.triggers: Dict[str, Trigger] = {}
        self.events: List[Event] = []
        self._counter = 0
        self._lock = threading.Lock()

    def register(self, name: str, event_type: EventType,
                 condition_fn: Callable, action_fn: Callable,
                 priority: int = 0, cooldown_seconds: float = 0) -> str:
        """注册触发器"""
        with self._lock:
            tid = f"trg_{self._counter}"
            self._counter += 1

        self.triggers[tid] = Trigger(
            id=tid, name=name, event_type=event_type,
            condition_fn=condition_fn, action_fn=action_fn,
            priority=priority, cooldown_seconds=cooldown_seconds
        )
        return tid

    def unregister(self, trigger_id: str) -> bool:
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            return True
        return False

    def emit(self, event_type: EventType, source: str, data: dict) -> str:
        """发射事件并触发匹配的触发器"""
        with self._lock:
            eid = f"evt_{self._counter}"
            self._counter += 1

        event = Event(id=eid, type=event_type, source=source, data=data)
        self.events.append(event)

        # 匹配并执行触发器
        matched = []
        for trigger in self.triggers.values():
            if trigger.event_type != event_type:
                continue

            # 冷却检查
            if trigger.cooldown_seconds > 0:
                elapsed = time.time() - trigger.last_triggered
                if elapsed < trigger.cooldown_seconds:
                    continue

            # 条件检查
            try:
                if trigger.condition_fn(event):
                    matched.append(trigger)
            except Exception:
                continue

        # 按优先级执行
        matched.sort(key=lambda t: -t.priority)
        for trigger in matched:
            try:
                trigger.action_fn(event)
                trigger.last_triggered = time.time()
                trigger.trigger_count += 1
            except Exception:
                continue

        return eid

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            "total_triggers": len(self.triggers),
            "total_events": len(self.events),
            "top_triggers": sorted(
                [{"name": t.name, "count": t.trigger_count}
                 for t in self.triggers.values()],
                key=lambda x: -x["count"]
            )[:5]
        }


# =============================================================================
# 4. SmartScheduler — 依赖调度 + 优先级队列
# =============================================================================

class TaskStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    id: str
    name: str
    fn: Callable
    next_run: float          # unix timestamp
    interval: float = 0      # 重复间隔（秒），0=一次性
    priority: int = 0        # 越高越优先
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.SCHEDULED
    run_count: int = 0
    max_errors: int = 3
    error_count: int = 0


class SmartScheduler:
    """智能调度器 — 优先级队列 + 依赖解析 + 自动重试"""

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.queue: List[tuple] = []  # (next_run, -priority, task_id)
        self._counter = 0
        self._lock = threading.Lock()
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def schedule(self, name: str, fn: Callable,
                 delay_seconds: float = 0,
                 interval: float = 0,
                 priority: int = 0,
                 dependencies: Optional[List[str]] = None) -> str:
        """调度一个任务"""
        with self._lock:
            tid = f"task_{self._counter}"
            self._counter += 1

        next_run = time.time() + delay_seconds
        task = ScheduledTask(
            id=tid, name=name, fn=fn,
            next_run=next_run, interval=interval,
            priority=priority, dependencies=dependencies or []
        )
        self.tasks[tid] = task
        heapq.heappush(self.queue, (next_run, -priority, tid))
        return tid

    def cancel(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.SCHEDULED:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def start(self):
        """启动调度器后台线程"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                self._tick()
                time.sleep(0.5)
            except Exception:
                time.sleep(1)

    def _tick(self):
        now = time.time()
        tasks_to_run = []

        with self._lock:
            while self.queue and self.queue[0][0] <= now:
                _, _, tid = heapq.heappop(self.queue)
                task = self.tasks.get(tid)
                if task and task.status == TaskStatus.SCHEDULED:
                    tasks_to_run.append(task)

        for task in tasks_to_run:
            # 检查依赖
            if not self._deps_met(task):
                task.next_run = now + 5
                heapq.heappush(self.queue, (task.next_run, -task.priority, task.id))
                continue

            # 执行
            task.status = TaskStatus.RUNNING
            try:
                result = task.fn()
                task.status = TaskStatus.COMPLETED
                task.run_count += 1

                # 周期性任务重新调度
                if task.interval > 0:
                    task.status = TaskStatus.SCHEDULED
                    task.next_run = now + task.interval
                    heapq.heappush(self.queue, (task.next_run, -task.priority, task.id))
            except Exception:
                task.error_count += 1
                if task.error_count >= task.max_errors:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.SCHEDULED
                    task.next_run = now + 10
                    heapq.heappush(self.queue, (task.next_run, -task.priority, task.id))

    def _deps_met(self, task: ScheduledTask) -> bool:
        for dep_id in task.dependencies:
            dep = self.tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_upcoming(self, limit: int = 10) -> List[dict]:
        """获取即将执行的任务"""
        now = time.time()
        upcoming = [
            {"id": t.id, "name": t.name, "next_run": t.next_run,
             "in_seconds": max(0, int(t.next_run - now)),
             "priority": t.priority}
            for t in self.tasks.values()
            if t.status == TaskStatus.SCHEDULED and t.next_run >= now
        ]
        upcoming.sort(key=lambda x: x["next_run"])
        return upcoming[:limit]

    def get_statistics(self) -> dict:
        status_counts = {}
        for t in self.tasks.values():
            status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1
        return {
            "total": len(self.tasks),
            **status_counts,
            "total_runs": sum(t.run_count for t in self.tasks.values())
        }


# =============================================================================
# 5. EnhancementEngine — 统一入口
# =============================================================================

class EnhancementEngine:
    """
    Crusheart 增强引擎 — 统一入口

    整合了告警管理、通知路由、事件触发、智能调度四个子系统。
    """

    def __init__(self, state_dir: str = ""):
        self.state_dir = state_dir
        self.alert = AlertEngine(state_dir)
        self.notifier = NotificationRouter(state_dir)
        self.events = EventEngine()
        self.scheduler = SmartScheduler()
        self._initialized = datetime.now().isoformat()

    def init_default_triggers(self):
        """注册默认触发器"""
        # 引擎失败告警触发器
        self.events.register(
            name="engine_failure_alerter",
            event_type=EventType.ERROR,
            condition_fn=lambda e: True,
            action_fn=lambda e: self.alert.save_alerts([
                self.alert.create_alert(
                    alert_type="engine_failure",
                    severity=AlertSeverity.CRITICAL,
                    message=str(e.data.get("error", "Unknown engine error")),
                    source=e.source,
                    details=e.data
                )
            ]),
            priority=100
        )

    def get_status(self) -> dict:
        """获取增强引擎整体状态"""
        return {
            "engine": "EnhancementEngine",
            "initialized": self._initialized,
            "alert": self.alert.get_status(),
            "event_engine": self.events.get_statistics(),
            "scheduler": self.scheduler.get_statistics(),
            "notification_history": len(self.notifier.history)
        }


# =============================================================================
# 全局实例工厂
# =============================================================================

_enhancement_engine: Optional[EnhancementEngine] = None


def init() -> EnhancementEngine:
    return get_enhancement_engine()


def get_enhancement_engine() -> EnhancementEngine:
    """获取增强引擎全局实例"""
    global _enhancement_engine
    if _enhancement_engine is None:
        _enhancement_engine = EnhancementEngine()
        _enhancement_engine.init_default_triggers()
    return _enhancement_engine
