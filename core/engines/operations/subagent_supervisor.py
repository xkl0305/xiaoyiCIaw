"""
Crusheart Agent OS — 子代理监督引擎 v1.0
=========================================

功能：
  1. 子代理注册 — Agent 层 spawn 后将 session_key 注册到此引擎
  2. 实时监督 — Agent 层定期调用 supervise() 获取进度，反馈给用户
  3. 进度日志 — 每次监督轮次自动记录摘要，可追溯全量日志
  4. 超时检测 — 自动标记超时子代理
  5. 干预接口 — steer/cancel 由引擎存储指令，Agent 层执行

设计原则：
  - 引擎层只做状态管理、持久化、超时检测
  - Agent 层负责实际的 sessions_spawn / sessions_send / sessions_history
  - 监督器为 Agent 提供 "查一下子代理在干嘛" 的能力，不阻塞主会话

集成方式：
  1. Agent 层调用 sessions_spawn → 获取 session_key
  2. Agent 层调用 supervisor.register(session_key, label, task_spec)
  3. Agent 层定期调用 supervisor.supervise(session_key) 检查进度
  4. Agent 层将进度整理后呈现给用户
"""

import os
import sys
import json
import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

BEIJING_TZ = timezone(timedelta(hours=8))
STATE_DIR = os.path.join(WORKSPACE, ".state")
SUPERVISION_FILE = os.path.join(STATE_DIR, "subagent_supervision.json")

logger = logging.getLogger("subagent_supervisor")

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

SUBAGENT_TIMEOUT_S = 600         # 10分钟超时
HARD_KILL_AFTER_S = 1800         # 30分钟硬杀（超时后最多再等20分钟）
MAX_REWAKEN_ATTEMPTS = 2          # 最大复生次数
REWAKEN_COOLDOWN_S = 60           # 复生后冷却60秒再判
MAX_PROGRESS_LOG = 50            # 最大进度日志条数
SUMMARY_TRUNCATE = 300           # 进度摘要截断

# AutoBrain 子代理任务模板前缀
AUTOBRAIN_SUBAGENT_PREAMBLE = """## 角色
你是 Crusheart AutoBrain 的一个子代理，继承了完整的引擎能力。

## 可用工具和引擎
在执行任务时，你可以使用以下 AutoBrain 引擎：

1. **记忆引擎** — `from core.engines.memory.auto_memory import AutoMemory; m = AutoMemory(); m.search(query)`
2. **防幻觉校验** — `from core.engines.quality.anti_fake_validator import anti_fake_validator; afv = AntiFakeValidator(); result = afv.validate(text)`
3. **熔断器** — `from core.engines.quality.circuit_breaker import get_breaker; breaker = get_breaker("xxx"); breaker.call(fn, timeout=30)`
4. **退化链** — `from core.engines.quality.circuit_breaker import get_breaker` 支持超时保护
5. **互斥锁** — `from core.engines.tools.mutex_engine import ToolMutex; mutex = ToolMutex(); mutex.acquire_background_lock()`

## 执行要求
1. 直接执行任务，不要等待用户确认
2. 每个关键步骤输出一条进度摘要（方便主会话监督）
3. 遇到错误时描述原因和已尝试的解决方案
4. 完成时输出完整结果报告
"""


# ═══════════════════════════════════════════════════════════
# SubAgentRecord — 子代理记录
# ═══════════════════════════════════════════════════════════

class SubAgentRecord:
    """单个子代理的监督记录"""

    def __init__(self, task_id: str, label: str, task_spec: str, session_key: str = ""):
        self.task_id = task_id
        self.label = label
        self.task_spec = task_spec
        self.session_key = session_key
        self.status = "registered"  # registered → running → completed / failed / canceled
        self.created_at = datetime.now(BEIJING_TZ).isoformat()
        self.completed_at: Optional[str] = None
        self.last_progress: str = ""
        self.progress_log: List[str] = []
        self.result: dict = {}
        self.error: str = ""
        self.supervision_rounds = 0
        self.last_supervised_at: Optional[str] = None
        self.rewaken_count: int = 0           # 已复生次数
        self.last_rewaken_at: Optional[str] = None  # 上次复生时间戳
        self.timeout_action: str = ""         # 当前超时决定：kill / rewaken / wait

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "status": self.status,
            "session_key": self.session_key,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error[:200],
            "supervision_rounds": self.supervision_rounds,
            "last_progress": self.last_progress[:200],
            "progress_summary": (self.progress_log[-1] if self.progress_log else "")[:200],
            "has_result": bool(self.result),
            "rewaken_count": self.rewaken_count,
            "timeout_action": self.timeout_action,
        }


# ═══════════════════════════════════════════════════════════
# SubAgentSupervisor — 子代理监督器
# ═══════════════════════════════════════════════════════════

class SubAgentSupervisor:
    """
    子代理监督器。
    
    使用方式（Agent 层）：
      1. subagent = sessions_spawn(task=..., runtime="subagent", mode="run")
      2. supervisor.register(task_id, "爬取新闻", task_spec, subagent.sessionKey)
      3. while True:
           status = supervisor.supervise(task_id)
           if status["completed"]: break
           整理 status["progress"] 给用户看
           time.sleep(5)
      4. result = supervisor.get_result(task_id)
    """

    def __init__(self):
        self._records: Dict[str, SubAgentRecord] = {}
        self._lock = threading.Lock()
        self._load_state()

    # ── 注册 / 更新 ──

    def register(self, task_id: str, label: str, task_spec: str,
                 session_key: str = "") -> dict:
        """注册一个子代理到监督体系"""
        record = SubAgentRecord(task_id, label, task_spec, session_key)
        with self._lock:
            self._records[task_id] = record
            self._save_state()
        return {"task_id": task_id, "status": "registered"}

    def mark_running(self, task_id: str, session_key: str):
        """标记子代理已启动运行"""
        with self._lock:
            record = self._records.get(task_id)
            if record:
                record.status = "running"
                record.session_key = session_key
                self._save_state()

    def mark_completed(self, task_id: str, result: dict = None, error: str = ""):
        """标记子代理已完成"""
        with self._lock:
            record = self._records.get(task_id)
            if not record:
                return
            record.status = "failed" if error else "completed"
            record.completed_at = datetime.now(BEIJING_TZ).isoformat()
            if error:
                record.error = str(error)[:500]
            if result:
                record.result = result
            self._save_state()

    def mark_canceled(self, task_id: str):
        """标记子代理已取消"""
        with self._lock:
            record = self._records.get(task_id)
            if record:
                record.status = "canceled"
                record.completed_at = datetime.now(BEIJING_TZ).isoformat()
                self._save_state()

    # ── 进度更新 ──

    def update_progress(self, task_id: str, progress_msg: str):
        """记录子代理进度摘要"""
        with self._lock:
            record = self._records.get(task_id)
            if not record:
                return
            record.last_progress = progress_msg[:SUMMARY_TRUNCATE]
            record.progress_log.append(
                f"[{datetime.now(BEIJING_TZ).strftime('%H:%M:%S')}] {progress_msg[:200]}"
            )
            if len(record.progress_log) > MAX_PROGRESS_LOG:
                record.progress_log = record.progress_log[-MAX_PROGRESS_LOG:]
            self._save_state()

    # ── 监督轮询（由 Agent 层调用） ──

    def supervise(self, task_id: str,
                  progress_from_history: str = "") -> dict:
        """
        单次监督查询。
        
        Agent 层先拉取 sessions_history，将最新 assistant 消息
        作为 progress_from_history 传入。
        
        返回进度摘要、状态、是否完成等。
        """
        with self._lock:
            record = self._records.get(task_id)
            if not record:
                return {"status": "not_found", "task_id": task_id}

            # 更新进度
            if progress_from_history:
                record.last_progress = progress_from_history[:SUMMARY_TRUNCATE]
                record.progress_log.append(
                    f"[R{record.supervision_rounds + 1}] {progress_from_history[:200]}"
                )
                if len(record.progress_log) > MAX_PROGRESS_LOG:
                    record.progress_log = record.progress_log[-MAX_PROGRESS_LOG:]

            record.supervision_rounds += 1
            record.last_supervised_at = datetime.now(BEIJING_TZ).isoformat()

            # 超时检测与决策
            if record.status == "running":
                created = datetime.fromisoformat(record.created_at)
                now = datetime.now(BEIJING_TZ)
                elapsed = (now - created).total_seconds()

                # 硬杀阈值：超过 HARD_KILL_AFTER_S 无任何活路
                if elapsed > HARD_KILL_AFTER_S:
                    record.status = "failed"
                    record.error = f"硬超时 ({HARD_KILL_AFTER_S}s)，强制终止"
                    record.timeout_action = "kill"
                    record.completed_at = now.isoformat()
                    self._save_state()
                    return {
                        "task_id": task_id,
                        "label": record.label,
                        "status": "failed",
                        "error": record.error,
                        "completed": True,
                        "timeout_action": "kill",
                    }

                if elapsed > SUBAGENT_TIMEOUT_S:
                    # ── 智能决策：杀还是复生？ ──
                    has_progress = len(record.progress_log) > 0
                    has_recent_progress = False
                    if record.last_progress:
                        # 检查最后一条进度是否在超时阈值内
                        try:
                            last_ts = record.progress_log[-1] if record.progress_log else ""
                            if last_ts:
                                # 格式 "[HH:MM:SS] xxx" 或 "[RN] xxx"
                                import re as _re
                                m = _re.search(r'\[(\d{2}:\d{2}:\d{2})\]', last_ts)
                                if m:
                                    last_time = datetime.strptime(m.group(1), '%H:%M:%S')
                                    now_time = now.time()
                                    diff = (datetime.combine(now.date(), now_time) - datetime.combine(now.date(), last_time)).total_seconds()
                                    has_recent_progress = diff < 180  # 3分钟内有过进度更新
                        except Exception:
                            pass

                    if has_recent_progress:
                        # 最近还有进度 → 子代理还在干活，给更多时间
                        record.timeout_action = "wait"
                        self._save_state()
                        return {
                            "task_id": task_id,
                            "label": record.label,
                            "status": "running",
                            "session_key": record.session_key,
                            "progress": f"超时{SUBAGENT_TIMEOUT_S}s但仍有进度，继续等待 ({int(elapsed)}s)",
                            "rounds": record.supervision_rounds,
                            "completed": False,
                            "timeout_action": "wait",
                            "suggested_action": "continue_waiting",
                        }

                    if (has_progress and
                        record.rewaken_count < MAX_REWAKEN_ATTEMPTS):
                        # 有过进展但停滞了 → 判断是陷入死循环 / 卡住 / 等外部资源
                        time_since_last_rewaken = elapsed
                        if record.last_rewaken_at:
                            try:
                                last_r = datetime.fromisoformat(record.last_rewaken_at)
                                time_since_last_rewaken = (now - last_r).total_seconds()
                            except Exception:
                                pass

                        if time_since_last_rewaken > REWAKEN_COOLDOWN_S:
                            # 冷却期已过 → 建议复生
                            record.timeout_action = "rewaken"
                            record.rewaken_count += 1
                            record.last_rewaken_at = now.isoformat()
                            self._save_state()
                            return {
                                "task_id": task_id,
                                "label": record.label,
                                "status": "running",
                                "session_key": record.session_key,
                                "progress": f"子代理停滞，建议复生 ({record.rewaken_count}/{MAX_REWAKEN_ATTEMPTS})",
                                "rounds": record.supervision_rounds,
                                "completed": False,
                                "timeout_action": "rewaken",
                                "suggested_action": "rewaken",
                                "rewaken_count": record.rewaken_count,
                                "max_rewaken": MAX_REWAKEN_ATTEMPTS,
                                "task_spec": record.task_spec,
                            }

                    # 兜底：杀
                    record.status = "failed"
                    record.error = f"超时 ({SUBAGENT_TIMEOUT_S}s)，无进展"
                    record.timeout_action = "kill"
                    record.completed_at = now.isoformat()
                    self._save_state()
                    return {
                        "task_id": task_id,
                        "label": record.label,
                        "status": "failed",
                        "error": record.error,
                        "completed": True,
                        "timeout_action": "kill",
                    }

            self._save_state()

            return {
                "task_id": task_id,
                "label": record.label,
                "status": record.status,
                "session_key": record.session_key,
                "progress": record.last_progress[:SUMMARY_TRUNCATE],
                "rounds": record.supervision_rounds,
                "completed": record.status in ("completed", "failed", "canceled"),
                "error": record.error,
            }

    # ── 查询 ──

    def get_result(self, task_id: str) -> dict:
        """获取子代理的最终结果"""
        with self._lock:
            record = self._records.get(task_id)
            if not record:
                return {"status": "not_found"}
            return {
                "task_id": task_id,
                "label": record.label,
                "status": record.status,
                "result": record.result,
                "error": record.error,
                "completed_at": record.completed_at,
                "progress_log": record.progress_log[-10:],
            }

    def get_status(self, task_id: str = None) -> dict:
        """查询状态概览"""
        with self._lock:
            if task_id:
                record = self._records.get(task_id)
                if not record:
                    return {"status": "not_found"}
                return record.to_dict()

            records = list(self._records.values())
            active = [r.to_dict() for r in records if r.status in ("registered", "running")]
            recent = [r.to_dict() for r in records[-10:]]
            return {
                "total": len(records),
                "active_count": len(active),
                "active": active,
                "recent": recent,
            }

    def get_progress_log(self, task_id: str) -> List[str]:
        """获取完整的进度日志"""
        with self._lock:
            record = self._records.get(task_id)
            return list(record.progress_log) if record else []

    # ── 子代理任务模板 ──

    def build_task_spec(self, user_task: str, with_autobrain: bool = True) -> str:
        """
        构建子代理任务描述。
        
        如果 with_autobrain=True，在任务前面加上 AutoBrain 引擎使用说明。
        """
        if with_autobrain:
            return f"{AUTOBRAIN_SUBAGENT_PREAMBLE}\n\n## 具体任务\n{user_task}"
        return user_task

    # ── 持久化 ──

    def _save_state(self):
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            data = {}
            for tid, r in self._records.items():
                record_dict = r.to_dict()
                record_dict["progress_log"] = r.progress_log[-20:]
                data[tid] = record_dict
            with open(SUPERVISION_FILE, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_state(self):
        if not os.path.exists(SUPERVISION_FILE):
            return
        try:
            with open(SUPERVISION_FILE) as f:
                data = json.load(f)
            for tid, d in data.items():
                r = SubAgentRecord(tid, d.get("label", ""), d.get("task_spec", ""), d.get("session_key", ""))
                r.status = d.get("status", "registered")
                r.created_at = d.get("created_at", datetime.now(BEIJING_TZ).isoformat())
                r.completed_at = d.get("completed_at")
                r.error = d.get("error", "")
                r.last_progress = d.get("last_progress", "")
                r.supervision_rounds = d.get("supervision_rounds", 0)
                r.result = d.get("result", {})
                r.progress_log = d.get("progress_log", [])
                self._records[tid] = r
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# 单例
# ═══════════════════════════════════════════════════════════

def get_supervisor() -> SubAgentSupervisor:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(SubAgentSupervisor)def init():
    """引擎初始化入口"""
    sv = get_supervisor()
    active = sv.get_status().get("active_count", 0)
    status_text = f"  👁️  子代理监督器: 已就绪"
    if active:
        status_text += f" (恢复监督 {active} 个活跃子代理)"
    else:
        status_text += f" (无待监督任务)"
    print(status_text)
    return {"status": "ok", "active_count": active}


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

    import json
    sv = SubAgentSupervisor()

    # 测试
    tid = "test_001"
    sv.register(tid, "测试任务", "搜索新闻并总结", "session_abc123")
    sv.mark_running(tid, "session_abc123")

    sv.update_progress(tid, "已开始搜索...")
    sv.update_progress(tid, "找到 10 条新闻，开始总结...")

    result = sv.supervise(tid, "已总结完成，共 3 个类别")
    print(f"监督结果: status={result['status']} completed={result['completed']} progress={result['progress'][:60]}")

    sv.mark_completed(tid, {"summary": "今日新闻总结完毕"})
    final = sv.get_result(tid)
    print(f"最终结果: status={final['status']} result={final['result']}")
    print("✅ SubAgentSupervisor 自测通过")
