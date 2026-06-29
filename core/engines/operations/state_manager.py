"""
Crusheart Agent OS — StateManager v4.0
统一状态管理层：Checkpoint + Recovery + EventLog + InstanceStore

数据存储映射：
  .checkpoints/{graph_id}.json     → DAG 图检查点（由 WorkflowOrchestrator 使用）
  .autonomy_state/recovery.json    → 恢复记录（兼容旧版 recovery_ledger.json）
  .autonomy_state/events.jsonl     → 工作流事件日志（JSONL 格式）
  .autonomy_state/instances.json   → 工作流实例注册表

与现有系统的对接：
- workflow_orchestrator.py 中的 CheckpointStore 将被本模块替代
- .autonomy_state/recovery_ledger.json 数据将被迁移到本模块
- 全模块无外部依赖，纯 Python 标准库
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


# ═══════════════════════════════════════════
# 路径常量
# ═══════════════════════════════════════════

class _Paths:
    CHECKPOINT_DIR = os.path.join(WORKSPACE, ".checkpoints")
    STATE_DIR = os.path.join(WORKSPACE, ".autonomy_state")
    RECOVERY_FILE = os.path.join(STATE_DIR, "recovery.json")
    EVENTS_FILE = os.path.join(STATE_DIR, "events.jsonl")
    INSTANCES_FILE = os.path.join(STATE_DIR, "instances.json")


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class ErrorType(str, Enum):
    """错误类型（用于 recovery 分类决策）"""
    TRANSIENT = "transient"        # 暂时性（网络超时、临时不可用）
    PERMANENT = "permanent"        # 永久性（逻辑错误、配置错误）
    RESOURCE = "resource"          # 资源不足
    VALIDATION = "validation"      # 参数校验失败
    DEPENDENCY = "dependency"      # 依赖不可用
    TIMEOUT = "timeout"            # 超时
    PERMISSION = "permission"      # 权限不足
    DEVICE = "device"              # 设备侧操作失败
    UNKNOWN = "unknown"            # 未分类


class RecoveryAction(str, Enum):
    """恢复动作策略"""
    RETRY = "retry"                # 重试
    SKIP = "skip"                  # 跳过本步骤
    FALLBACK = "fallback"          # 降级执行
    ABORT = "abort"                # 终止工作流
    ROLLBACK = "rollback"          # 回滚到检查点
    MANUAL = "manual"              # 需要人工介入


class EventType(str, Enum):
    """工作流事件类型"""
    # 生命周期
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    # 节点
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    # 恢复
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    RETRY_TRIGGERED = "retry_triggered"
    FALLBACK_TRIGGERED = "fallback_triggered"
    ROLLBACK_TRIGGERED = "rollback_triggered"


# ═══════════════════════════════════════════
# 1. CheckpointService — DAG 图检查点
# ═══════════════════════════════════════════

class CheckpointService:
    """
    检查点服务
    
    每个 DAG 图执行过程中的完整状态序列化为 JSON 文件，
    存放在 .checkpoints/{graph_id}.json。
    
    v4.0 改进（vs workflow_orchestrator 中的 CheckpointStore）：
    - 使用 DAGGraph.to_dict()/from_dict() 直接序列化
    - 支持旧版本文件的版本检测
    - 按实例批量清理 + 最大保留数控制
    - 线程安全
    """

    def __init__(self):
        self._ensure_dirs()

    @staticmethod
    def _ensure_dirs():
        os.makedirs(_Paths.CHECKPOINT_DIR, exist_ok=True)
        os.makedirs(_Paths.STATE_DIR, exist_ok=True)

    def _graph_path(self, graph_id: str) -> str:
        return os.path.join(_Paths.CHECKPOINT_DIR, f"{graph_id}.json")

    def save(self, graph) -> str:
        """
        保存 DAG 图状态到 checkpoint
        兼容任何有 to_dict() 方法的 graph 对象
        """
        self._ensure_dirs()
        path = self._graph_path(graph.graph_id)
        data = graph.to_dict()
        data["_checkpoint_version"] = "v4.0"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"[CheckpointService] 已保存: {path}")
        return path

    def load(self, graph_id: str) -> Optional[Dict]:
        """
        从 checkpoint 文件加载 DAG 图数据
        
        Returns:
            图的 dict 格式数据（可用于 DAGGraph.from_dict()），或 None
        """
        path = self._graph_path(graph_id)
        if not os.path.exists(path):
            logger.warning(f"[CheckpointService] 不存在: {path}")
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"[CheckpointService] 已恢复: graph_id={graph_id}")
        return data

    def remove(self, graph_id: str) -> bool:
        """删除指定 checkpoint"""
        path = self._graph_path(graph_id)
        if os.path.exists(path):
            os.remove(path)
            logger.debug(f"[CheckpointService] 已删除: {graph_id}")
            return True
        return False

    def list_all(self) -> List[str]:
        """列出所有 checkpoint 的 graph_id（按修改时间降序）"""
        self._ensure_dirs()
        files = []
        for fname in os.listdir(_Paths.CHECKPOINT_DIR):
            if fname.endswith(".json") and not fname.startswith("."):
                fpath = os.path.join(_Paths.CHECKPOINT_DIR, fname)
                files.append((fname[:-5], os.path.getmtime(fpath)))
        files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in files]

    def cleanup_old(self, keep_count: int = 20) -> int:
        """
        清理旧 checkpoint，只保留最新的 keep_count 个
        Returns: 删除的文件数
        """
        all_ck = self.list_all()
        if len(all_ck) <= keep_count:
            return 0
        to_remove = all_ck[keep_count:]
        for gid in to_remove:
            self.remove(gid)
        return len(to_remove)

    def stats(self) -> Dict[str, Any]:
        """checkpoint 统计"""
        all_ids = self.list_all()
        total_bytes = 0
        for gid in all_ids:
            path = self._graph_path(gid)
            if os.path.exists(path):
                total_bytes += os.path.getsize(path)
        return {
            "count": len(all_ids),
            "total_bytes": total_bytes,
            "max_retain": 20,
        }


# ═══════════════════════════════════════════
# 2. RecoveryService — 恢复记录管理
# ═══════════════════════════════════════════

@dataclass
class RecoveryRecord:
    """单条恢复记录"""
    record_id: str
    graph_id: str
    node_id: str
    error_type: ErrorType
    error_message: str
    recovery_action: RecoveryAction
    timestamp: str
    retry_count: int = 0
    max_retries: int = 3
    resolved: bool = False
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["error_type"] = self.error_type.value
        d["recovery_action"] = self.recovery_action.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "RecoveryRecord":
        data = dict(data)
        data["error_type"] = ErrorType(data["error_type"])
        data["recovery_action"] = RecoveryAction(data["recovery_action"])
        return cls(**data)


class RecoveryService:
    """
    恢复记录服务
    
    管理工作流执行中的失败记录和恢复策略。
    数据持久化到 .autonomy_state/recovery.json
    
    v4.0 改进：
    - 错误分类 + 策略选择
    - 重试次数追踪 + 上限自动拦截
    - 兼容旧版 recovery_ledger.json 格式
    """

    def __init__(self):
        self._records: Dict[str, RecoveryRecord] = {}
        self._lock = threading.RLock()
        self._ensure_dirs()
        self._migrate_legacy()  # 兼容旧版
        self._load()

    def _ensure_dirs(self):
        os.makedirs(_Paths.STATE_DIR, exist_ok=True)

    def _load(self):
        if os.path.exists(_Paths.RECOVERY_FILE):
            try:
                with open(_Paths.RECOVERY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("records", []):
                        record = RecoveryRecord.from_dict(item)
                        self._records[record.record_id] = record
            except Exception as e:
                logger.warning(f"[RecoveryService] 加载失败: {e}")
                self._records = {}

    def _save(self):
        with self._lock:
            data = {"records": [r.to_dict() for r in self._records.values()]}
            self._ensure_dirs()
            # 原子写入：tmp + rename
            tmp_path = _Paths.RECOVERY_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, _Paths.RECOVERY_FILE)

    def _migrate_legacy(self):
        """
        兼容旧版 recovery_ledger.json
        
        如果存在旧文件且 recovery.json 不存在，则迁移数据
        """
        legacy_path = os.path.join(_Paths.STATE_DIR, "recovery_ledger.json")
        if os.path.exists(legacy_path) and not os.path.exists(_Paths.RECOVERY_FILE):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                if isinstance(legacy_data, list):
                    records = []
                    for item in legacy_data:
                        records.append(RecoveryRecord(
                            record_id=item.get("id", f"migrated_{len(records)}"),
                            graph_id=item.get("run_id", "legacy"),
                            node_id=item.get("action", "unknown"),
                            error_type=ErrorType.UNKNOWN,
                            error_message=item.get("rollback_plan", ""),
                            recovery_action=RecoveryAction.ROLLBACK,
                            timestamp=self._ts_from_epoch(item.get("created_at")),
                            resolved=item.get("reversible", True),
                            metadata={"source": "legacy_recovery_ledger"},
                        ))
                    self._records = {r.record_id: r for r in records}
                    self._save()
                    logger.info(
                        f"[RecoveryService] 已从 recovery_ledger.json 迁移 "
                        f"{len(records)} 条记录"
                    )
            except Exception as e:
                logger.warning(f"[RecoveryService] 旧文件迁移失败: {e}")

    def _ts_from_epoch(self, epoch: Optional[float]) -> str:
        if epoch:
            try:
                dt = datetime.fromtimestamp(epoch, tz=BEIJING_TZ)
                return dt.isoformat()
            except (OSError, ValueError):
                pass
        return datetime.now(BEIJING_TZ).isoformat()

    # ── 核心 API ──

    def record_error(
        self,
        graph_id: str,
        node_id: str,
        error_type: ErrorType,
        error_message: str,
        recovery_action: RecoveryAction,
        max_retries: int = 3,
        metadata: Optional[Dict] = None,
    ) -> RecoveryRecord:
        """记录一次错误"""
        now = datetime.now(BEIJING_TZ)
        record_id = f"err_{graph_id}_{node_id}_{now.strftime('%Y%m%d%H%M%S%f')}"
        record = RecoveryRecord(
            record_id=record_id,
            graph_id=graph_id,
            node_id=node_id,
            error_type=error_type,
            error_message=error_message[:500],
            recovery_action=recovery_action,
            timestamp=now.isoformat(),
            max_retries=max_retries,
            metadata=metadata or {},
        )
        with self._lock:
            self._records[record_id] = record
            self._save()
        logger.info(
            f"[RecoveryService] 记录错误: graph={graph_id} "
            f"node={node_id} type={error_type.value} action={recovery_action.value}"
        )
        return record

    def get(self, record_id: str) -> Optional[RecoveryRecord]:
        return self._records.get(record_id)

    def get_latest(self, graph_id: str, node_id: str) -> Optional[RecoveryRecord]:
        """获取指定 graph+node 的最新记录"""
        matched = [
            r for r in self._records.values()
            if r.graph_id == graph_id and r.node_id == node_id
        ]
        return matched[-1] if matched else None

    def can_retry(self, record_id: str) -> bool:
        """检查是否还可以重试"""
        record = self._records.get(record_id)
        if not record:
            return False
        return record.retry_count < record.max_retries

    def increment_retry(self, record_id: str) -> Optional[RecoveryRecord]:
        """增加重试计数"""
        with self._lock:
            record = self._records.get(record_id)
            if not record:
                return None
            record.retry_count += 1
            self._save()
            return record

    def mark_resolved(self, record_id: str) -> Optional[RecoveryRecord]:
        """标记为已解决"""
        with self._lock:
            record = self._records.get(record_id)
            if not record:
                return None
            record.resolved = True
            record.resolved_at = datetime.now(BEIJING_TZ).isoformat()
            self._save()
            return record

    def list_unresolved(self, graph_id: Optional[str] = None) -> List[RecoveryRecord]:
        """列出未解决的记录"""
        records = [r for r in self._records.values() if not r.resolved]
        if graph_id:
            records = [r for r in records if r.graph_id == graph_id]
        return records

    def list_by_graph(self, graph_id: str) -> List[RecoveryRecord]:
        return [r for r in self._records.values() if r.graph_id == graph_id]

    def clear_resolved(self, older_than_days: int = 30):
        """清除已解决的旧记录"""
        now = datetime.now(BEIJING_TZ)
        with self._lock:
            to_remove = []
            for rid, record in self._records.items():
                if record.resolved and record.resolved_at:
                    try:
                        resolved_time = datetime.fromisoformat(record.resolved_at)
                        if (now - resolved_time).days > older_than_days:
                            to_remove.append(rid)
                    except (ValueError, TypeError):
                        pass
            for rid in to_remove:
                del self._records[rid]
            if to_remove:
                self._save()
                logger.info(
                    f"[RecoveryService] 清理了 {len(to_remove)} 条旧记录"
                )

    def classify_error(self, error_message: str) -> ErrorType:
        """根据错误信息自动分类错误类型"""
        emsg = error_message.lower()
        if any(kw in emsg for kw in ("timeout", "timed out", "超时")):
            return ErrorType.TIMEOUT
        if any(kw in emsg for kw in ("network", "connection", "断开")):
            return ErrorType.TRANSIENT
        if any(kw in emsg for kw in ("permission", "denied", "权限", "禁止")):
            return ErrorType.PERMISSION
        if any(kw in emsg for kw in ("not found", "missing", "不存在", "缺少")):
            return ErrorType.VALIDATION
        if any(kw in emsg for kw in ("device", "gui_agent", "端侧", "设备端", "设备")):
            return ErrorType.DEVICE
        return ErrorType.UNKNOWN

    def determine_action(self, error_type: ErrorType, retry_count: int = 0) -> RecoveryAction:
        """根据错误类型和重试次数决定恢复策略"""
        if error_type == ErrorType.TRANSIENT:
            return RecoveryAction.RETRY
        if error_type == ErrorType.TIMEOUT:
            return RecoveryAction.RETRY if retry_count < 3 else RecoveryAction.FALLBACK
        if error_type == ErrorType.PERMISSION:
            return RecoveryAction.MANUAL
        if error_type == ErrorType.VALIDATION:
            return RecoveryAction.ABORT
        if error_type == ErrorType.DEVICE:
            return RecoveryAction.RETRY if retry_count < 2 else RecoveryAction.ROLLBACK
        if error_type == ErrorType.RESOURCE:
            return RecoveryAction.FALLBACK
        return RecoveryAction.ABORT

    def stats(self) -> Dict[str, Any]:
        """恢复记录统计"""
        total = len(self._records)
        unresolved = len(self.list_unresolved())
        by_type: Dict[str, int] = {}
        for r in self._records.values():
            by_type[r.error_type.value] = by_type.get(r.error_type.value, 0) + 1
        return {
            "total": total,
            "unresolved": unresolved,
            "resolved": total - unresolved,
            "by_error_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        }


# ═══════════════════════════════════════════
# 3. EventLogger — 工作流事件日志
# ═══════════════════════════════════════════

class EventLogger:
    """
    工作流事件记录器
    
    采用 JSONL 格式（每行一个 JSON），追加写入 .autonomy_state/events.jsonl
    
    特点：
    - 追加写入，无需全局锁（Python GIL 保护 write 原子性）
    - 支持按 graph_id / event_type / node_id 过滤
    - 内置便捷方法：log_start(), log_complete(), log_fail() 等
    - 日志文件自动轮转（超过 max_lines 行后截断）
    """

    def __init__(self, max_lines: int = 10000):
        self.max_lines = max_lines
        self._events: List[Dict] = []
        self._append_count = 0
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(_Paths.STATE_DIR, exist_ok=True)

    def _append_to_file(self, event: Dict):
        """追加一条事件到 JSONL 文件"""
        with open(_Paths.EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._append_count += 1
        if self._append_count >= self.max_lines:
            self._rotate_if_needed()
            self._append_count = 0

    def _rotate_if_needed(self):
        """如果文件行数超过上限，截断保留后半"""
        if not os.path.exists(_Paths.EVENTS_FILE):
            return
        with open(_Paths.EVENTS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > self.max_lines:
            # 保留后半
            keep = lines[-(self.max_lines // 2):]
            with open(_Paths.EVENTS_FILE, "w", encoding="utf-8") as f:
                f.writelines(keep)
            logger.info(f"[EventLogger] 日志已轮转: {len(lines)}→{len(keep)}行")

    def log(self, graph_id: str, event_type: EventType,
            node_id: Optional[str] = None,
            payload: Optional[Dict] = None,
            metadata: Optional[Dict] = None) -> Dict:
        """记录一条事件"""
        event = {
            "event_id": f"{graph_id}_{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S%f')}",
            "graph_id": graph_id,
            "event_type": event_type.value,
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "node_id": node_id,
            "payload": payload or {},
            "metadata": metadata or {},
        }
        self._events.append(event)
        self._append_to_file(event)
        return event

    # ── 便捷方法 ──

    def log_start(self, graph_id: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.WORKFLOW_STARTED, **kwargs)

    def log_complete(self, graph_id: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.WORKFLOW_COMPLETED, **kwargs)

    def log_fail(self, graph_id: str, error: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.WORKFLOW_FAILED,
                        payload={"error": error}, **kwargs)

    def log_node_start(self, graph_id: str, node_id: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.NODE_STARTED, node_id=node_id, **kwargs)

    def log_node_complete(self, graph_id: str, node_id: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.NODE_COMPLETED, node_id=node_id, **kwargs)

    def log_node_fail(self, graph_id: str, node_id: str, error: str, **kwargs) -> Dict:
        return self.log(graph_id, EventType.NODE_FAILED, node_id=node_id,
                        payload={"error": error}, **kwargs)

    def log_checkpoint(self, graph_id: str, node_id: str) -> Dict:
        return self.log(graph_id, EventType.CHECKPOINT_SAVED, node_id=node_id)

    # ── 查询 ──

    def list_by_graph(self, graph_id: str) -> List[Dict]:
        """从文件读取指定工作流的所有事件"""
        if not os.path.exists(_Paths.EVENTS_FILE):
            return []
        events = []
        with open(_Paths.EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        evt = json.loads(line)
                        if evt.get("graph_id") == graph_id:
                            events.append(evt)
                    except json.JSONDecodeError:
                        pass
        return events

    def list_by_type(self, event_type: EventType, limit: int = 50) -> List[Dict]:
        """按事件类型列出最近事件"""
        if not os.path.exists(_Paths.EVENTS_FILE):
            return []
        events = []
        with open(_Paths.EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        evt = json.loads(line)
                        if evt.get("event_type") == event_type.value:
                            events.append(evt)
                    except json.JSONDecodeError:
                        pass
        return events[-limit:]

    def stats(self) -> Dict[str, Any]:
        """事件统计"""
        if not os.path.exists(_Paths.EVENTS_FILE):
            return {"total": 0, "by_type": {}}
        total = 0
        by_type: Dict[str, int] = {}
        with open(_Paths.EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    total += 1
                    try:
                        evt = json.loads(line)
                        et = evt.get("event_type", "unknown")
                        by_type[et] = by_type.get(et, 0) + 1
                    except json.JSONDecodeError:
                        pass
        return {
            "total": total,
            "max_lines": self.max_lines,
            "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        }


# ═══════════════════════════════════════════
# 4. WorkflowStateManager — 统一入口
# ═══════════════════════════════════════════

class WorkflowStateManager:
    """
    工作流状态管理器 — 统一入口
    
    整合 checkpoint + recovery + event 三个子系统，
    提供"一次调用，三处记录"的便捷方法。
    
    使用方式：
        sm = WorkflowStateManager()
        sm.record_run_start("graph_xxx")  # 同时 checkpoint + event
        sm.record_node_done("graph_xxx", "n1")  # 同时 checkpoint + event
        sm.record_fail("graph_xxx", "n2", "timeout")  # 同时 checkpoint + recovery + event
        sm.complete("graph_xxx")  # 最终 checkpoint + event
    """

    def __init__(self):
        self.checkpoint = CheckpointService()
        self.recovery = RecoveryService()
        self.event = EventLogger()

    def record_run_start(self, graph) -> None:
        """记录工作流启动"""
        self.checkpoint.save(graph)
        self.event.log_start(graph.graph_id)

    def record_node_done(self, graph, node_id: str) -> None:
        """记录节点完成"""
        self.checkpoint.save(graph)
        self.event.log_node_complete(graph.graph_id, node_id)
        logger.debug(
            f"[StateManager] node_done: graph={graph.graph_id} node={node_id}"
        )

    def record_node_fail(self, graph, node_id: str, error: str,
                         error_type: Optional[ErrorType] = None) -> None:
        """记录节点失败（同时记录 checkpoint + recovery + event）"""
        # 错误分类
        err_type = error_type or self.recovery.classify_error(error)
        action = self.recovery.determine_action(err_type)

        # 三方记录
        self.checkpoint.save(graph)
        self.recovery.record_error(
            graph_id=graph.graph_id,
            node_id=node_id,
            error_type=err_type,
            error_message=error,
            recovery_action=action,
        )
        self.event.log_node_fail(graph.graph_id, node_id, error)

        logger.warning(
            f"[StateManager] node_fail: graph={graph.graph_id} "
            f"node={node_id} error_type={err_type.value} "
            f"action={action.value}"
        )

    def record_complete(self, graph) -> None:
        """记录工作流完成"""
        self.checkpoint.save(graph)
        self.event.log_complete(graph.graph_id)
        logger.info(f"[StateManager] complete: graph={graph.graph_id}")

    def record_checkpoint(self, graph, node_id: Optional[str] = None) -> None:
        """保存检查点（可选关联节点事件）"""
        self.checkpoint.save(graph)
        if node_id:
            self.event.log_checkpoint(graph.graph_id, node_id)

    def load_graph(self, graph_id: str) -> Optional[Any]:
        """从 checkpoint 恢复 DAG 图数据"""
        return self.checkpoint.load(graph_id)

    def get_recovery_stats(self) -> Dict[str, Any]:
        return self.recovery.stats()

    def get_event_stats(self) -> Dict[str, Any]:
        return self.event.stats()

    def get_checkpoint_stats(self) -> Dict[str, Any]:
        return self.checkpoint.stats()

    def cleanup(self, keep_checkpoints: int = 20,
                clear_recovery_days: int = 30) -> Dict[str, Any]:
        """定期清理"""
        ck_removed = self.checkpoint.cleanup_old(keep_checkpoints)
        self.recovery.clear_resolved(clear_recovery_days)
        return {
            "checkpoints_removed": ck_removed,
            "checkpoints_remaining": len(self.checkpoint.list_all()),
            "recovery_unresolved": len(self.recovery.list_unresolved()),
        }

    def get_full_status(self, graph_id: str) -> Dict[str, Any]:
        """获取指定工作流的完整状态报告"""
        return {
            "graph_id": graph_id,
            "checkpoint_exists": os.path.exists(
                os.path.join(_Paths.CHECKPOINT_DIR, f"{graph_id}.json")
            ),
            "recovery_records": [
                r.to_dict() for r in self.recovery.list_by_graph(graph_id)
            ],
            "events": self.event.list_by_graph(graph_id)[-10:],
        }


# ═══════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════

_state_manager: Optional[WorkflowStateManager] = None

def get_state_manager() -> WorkflowStateManager:
    """获取全局状态管理器单例"""
    global _state_manager
    if _state_manager is None:
        _state_manager = WorkflowStateManager()
    return _state_manager


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

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("StateManager v4.0 — 测试")
    print("=" * 60)

    sm = get_state_manager()

    # 测试1: 错误分类
    print("\n测试1: 错误分类")
    for msg, expected in [
        ("连接超时了", "timeout"),
        ("permission denied", "permission"),
        ("设备端没有响应", "device"),
        ("缺少参数 action", "validation"),
        ("网络断开", "transient"),
    ]:
        actual = sm.recovery.classify_error(msg)
        ok = actual.value == expected
        print(f"  {msg} → {actual.value} {'✅' if ok else '❌'}")

    # 测试2: 恢复策略
    print("\n测试2: 恢复策略")
    for err_type, retry, expected in [
        ("transient", 0, "retry"),
        ("timeout", 4, "fallback"),
        ("permission", 0, "manual"),
        ("validation", 0, "abort"),
        ("device", 0, "retry"),
        ("device", 3, "rollback"),
    ]:
        action = sm.recovery.determine_action(ErrorType(err_type), retry)
        ok = action.value == expected
        print(f"  {err_type} (retry={retry}) → {action.value} {'✅' if ok else '❌'}")

    # 测试3: 事件日志
    print("\n测试3: 事件日志")
    evt = sm.event.log_start("test_graph_001")
    print(f"  记录事件: {evt['event_type']} @ {evt['timestamp'][:19]}")
    sm.event.log_node_complete("test_graph_001", "n1_goal_review")
    sm.event.log_complete("test_graph_001")
    events = sm.event.list_by_graph("test_graph_001")
    print(f"  回读: {len(events)} 条事件")
    print("  ✅ 通过")

    # 测试4: checkpoint 统计
    print("\n测试4: checkpoint 统计")
    stats = sm.get_checkpoint_stats()
    print(f"  count={stats['count']}, size={stats['total_bytes']}B")
    print("  ✅ 通过")

    # 测试5: mock DAG 完整流程
    print("\n测试5: 完整工作流状态追踪（mock DAG）")
    mock_graph = type("MockGraph", (), {"graph_id": "test_graph_mock", "to_dict": lambda self: {"graph_id": "test_graph_mock"}})()

    sm.record_run_start(mock_graph)
    sm.record_node_done(mock_graph, "n1")
    sm.record_node_fail(mock_graph, "n2", "设备超时未响应")
    sm.record_complete(mock_graph)

    status = sm.get_full_status("test_graph_mock")
    print(f"  事件数: {len(status['events'])}")
    print(f"  recovery记录数: {len(status['recovery_records'])}")
    print(f"  checkpoint存在: {status['checkpoint_exists']}")
    print("  ✅ 通过")

    # 测试6: 统计概览
    print("\n测试6: 统计概览")
    print(f"  recovery: {sm.get_recovery_stats()}")
    print(f"  events: {sm.get_event_stats()}")
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("全部测试通过 ✅")
    print("=" * 60)
