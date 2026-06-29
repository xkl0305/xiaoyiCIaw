"""
Crusheart Agent OS — 会话管理器 v2.0
合并自 session_handoff + context_capsule

包含：
  - HandoffCapsule / ContextCapsule: 两种上下文胶囊数据结构
  - HandoffEngine: 会话交接引擎（保存/加载/检索胶囊）
  - ContextCapsuleManager: 跨会话连续性跟踪管理器
"""

import os, json, glob
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

# --- HandoffEngine 路径 ---
HANDOFF_DIR = os.path.join(WORKSPACE, "memory", "handoffs")
LATEST_CAPSULE_FILE = os.path.join(HANDOFF_DIR, ".latest_capsule.json")
MAX_CAPSULES = 50

RESUME_FILE = os.path.join(WORKSPACE, ".handoff_state", "last_resume_context.md")
os.makedirs(os.path.join(WORKSPACE, ".handoff_state"), exist_ok=True)

# --- ContextCapsuleManager 路径 ---
CAPSULE_PATH = os.path.join(WORKSPACE, ".context_capsule.json")

def _now_str() -> str:
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ================================================================
# 1. HandoffCapsule — 会话交接胶囊（原 session_handoff.ContextCapsule）
# ================================================================

class HandoffCapsule:
    """
    单个上下文胶囊（会话交接用）：
    - saved_at: 保存时间
    - task_summary: 当前任务摘要
    - pending_items: 待处理事项列表
    - key_decisions: 关键决策记录
    - open_questions: 开放问题
    - context_tags: 标签（用于检索匹配）
    - active_skill: 当前使用的 skill 名称
    - working_files: 正在处理的文件路径列表
    - user_intent: 用户当前意图描述
    """

    def __init__(self, data: Optional[dict] = None):
        self.data = data or {
            "saved_at": _now_str(),
            "task_summary": "",
            "pending_items": [],
            "key_decisions": [],
            "open_questions": [],
            "context_tags": [],
            "active_skill": "",
            "working_files": [],
            "user_intent": "",
        }

    def to_dict(self) -> dict:
        return self.data

    def to_resume_text(self) -> str:
        d = self.data
        parts = []
        if d.get("task_summary"):
            parts.append(f"📌 上次任务: {d['task_summary']}")
        if d.get("pending_items"):
            pending = "\n".join(f"  ⏳ {item}" for item in d["pending_items"])
            parts.append(f"待办事项:\n{pending}")
        if d.get("key_decisions"):
            decisions = "\n".join(f"  ✅ {dec}" for dec in d["key_decisions"])
            parts.append(f"关键决策:\n{decisions}")
        if d.get("open_questions"):
            questions = "\n".join(f"  ❓ {q}" for q in d["open_questions"])
            parts.append(f"开放问题:\n{questions}")
        if d.get("active_skill"):
            parts.append(f"🔧 活跃技能: {d['active_skill']}")
        return "\n\n".join(parts) if parts else "没有待接续的上下文。"

# 向后兼容别名
ContextCapsule = HandoffCapsule

# ================================================================
# 2. HandoffEngine — 会话交接引擎
# ================================================================

class HandoffEngine:
    """
    会话交接引擎：
    - 保存当前会话状态到上下文胶囊
    - 新会话启动时自动加载最近胶囊
    - 胶囊按标签检索匹配
    """

    def __init__(self):
        self._capsule: Optional[HandoffCapsule] = None

    def save_capsule(
        self,
        task_summary: str = "",
        pending_items: Optional[List[str]] = None,
        key_decisions: Optional[List[str]] = None,
        open_questions: Optional[List[str]] = None,
        context_tags: Optional[List[str]] = None,
        active_skill: str = "",
        working_files: Optional[List[str]] = None,
        user_intent: str = "",
    ) -> str:
        """保存上下文胶囊，返回文件路径。"""
        import uuid
        timestamp = datetime.now(BEIJING_TZ).strftime("%Y%m%d_%H%M%S") + f"_{uuid.uuid4().hex[:4]}"
        capsule = HandoffCapsule({
            "saved_at": _now_str(),
            "timestamp": timestamp,
            "task_summary": task_summary,
            "pending_items": pending_items or [],
            "key_decisions": key_decisions or [],
            "open_questions": open_questions or [],
            "context_tags": context_tags or [],
            "active_skill": active_skill,
            "working_files": working_files or [],
            "user_intent": user_intent,
        })

        filename = f"capsule_{timestamp}.json"
        filepath = os.path.join(HANDOFF_DIR, filename)
        os.makedirs(HANDOFF_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(capsule.to_dict(), f, ensure_ascii=False, indent=2)

        with open(LATEST_CAPSULE_FILE, "w", encoding="utf-8") as f:
            json.dump({"latest": filepath, "saved_at": _now_str()}, f, ensure_ascii=False, indent=2)

        self._capsule = capsule
        self._cleanup_old()
        return filepath

    def get_latest(self) -> Optional[HandoffCapsule]:
        if self._capsule:
            return self._capsule
        if os.path.exists(LATEST_CAPSULE_FILE):
            try:
                with open(LATEST_CAPSULE_FILE, encoding="utf-8") as f:
                    meta = json.load(f)
                latest_path = meta.get("latest", "")
                if latest_path and os.path.exists(latest_path):
                    with open(latest_path, encoding="utf-8") as f:
                        data = json.load(f)
                    self._capsule = HandoffCapsule(data)
                    return self._capsule
            except Exception:
                pass
        files = sorted(glob.glob(os.path.join(HANDOFF_DIR, "capsule_*.json")), reverse=True)
        for fp in files:
            if fp == LATEST_CAPSULE_FILE:
                continue
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                self._capsule = HandoffCapsule(data)
                with open(LATEST_CAPSULE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"latest": fp, "saved_at": _now_str()}, f, ensure_ascii=False, indent=2)
                return self._capsule
            except Exception:
                continue
        return None

    def get_resume_prompt(self) -> str:
        caps = self.get_latest()
        return caps.to_resume_text() if caps else ""

    def search_by_tags(self, tags: List[str]) -> List[dict]:
        results = []
        files = sorted(glob.glob(os.path.join(HANDOFF_DIR, "capsule_*.json")), reverse=True)
        for fp in files[:20]:
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                if set(data.get("context_tags", [])) & set(tags):
                    results.append(data)
            except Exception:
                continue
        return results

    def list_history(self, limit: int = 10) -> List[dict]:
        results = []
        files = sorted(glob.glob(os.path.join(HANDOFF_DIR, "capsule_*.json")), reverse=True)
        for fp in files[:limit]:
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "saved_at": data.get("saved_at", ""),
                    "task_summary": data.get("task_summary", ""),
                    "tag_count": len(data.get("context_tags", [])),
                    "pending_count": len(data.get("pending_items", [])),
                })
            except Exception:
                continue
        return results

    def _cleanup_old(self):
        files = sorted(glob.glob(os.path.join(HANDOFF_DIR, "capsule_*.json")))
        if len(files) > MAX_CAPSULES:
            for fp in files[:len(files) - MAX_CAPSULES]:
                try:
                    os.remove(fp)
                except OSError:
                    pass

    def clear(self):
        for fp in glob.glob(os.path.join(HANDOFF_DIR, "capsule_*.json")):
            try:
                os.remove(fp)
            except OSError:
                pass
        if os.path.exists(LATEST_CAPSULE_FILE):
            try:
                os.remove(LATEST_CAPSULE_FILE)
            except OSError:
                pass
        self._capsule = None

def get_handoff() -> HandoffEngine:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(HandoffEngine)def check_on_startup() -> bool:
    """会话启动时检查是否有待续接的上下文。"""
    handoff = get_handoff()
    prompt = handoff.get_resume_prompt()
    if prompt:
        ts = _now_str()
        print(f"\n[{ts}] 📎 检测到上次会话记录：\n{prompt}\n")
        try:
            resume_md = f"# 上次会话摘要\n\n> 保存时间: {ts}\n\n{prompt}\n"
            with open(RESUME_FILE, "w", encoding="utf-8") as f:
                f.write(resume_md)
            print(f"✅ 会话摘要已写入 {RESUME_FILE}")
        except Exception as e:
            print(f"  ⚠️ 写入会话摘要失败: {e}")
        return True
    try:
        if os.path.exists(RESUME_FILE):
            os.remove(RESUME_FILE)
    except Exception:
        pass
    return False

def auto_save(task_summary: str = "", pending_items=None,
              key_decisions=None, open_questions=None,
              context_tags=None, active_skill="",
              working_files=None, user_intent=""):
    """便捷保存胶囊。"""
    handoff = get_handoff()
    return handoff.save_capsule(
        task_summary=task_summary,
        pending_items=pending_items or [],
        key_decisions=key_decisions or [],
        open_questions=open_questions or [],
        context_tags=context_tags or ["auto_save"],
        active_skill=active_skill,
        working_files=working_files or [],
        user_intent=user_intent,
    )

def init() -> HandoffEngine:
    """engines.json init_fn 入口（HandoffEngine）"""
    return get_handoff()

# ================================================================
# 3. SessionCapsule — 跨会话连续性胶囊数据（原 context_capsule.ContextCapsule）
# ================================================================

@dataclass
class SessionCapsule:
    """跨会话连续性胶囊"""
    identity_summary: str = ""
    safety_red_lines: List[str] = field(default_factory=list)
    current_goal: str = ""
    next_best_action: str = ""
    persona_mood: str = "neutral"
    persona_energy: int = 80
    trust_level: float = 50.0
    interaction_count: int = 0
    last_session_key: str = ""
    last_blocker: str = ""
    recent_events: List[Dict] = field(default_factory=list)
    last_updated: str = ""
    task_stack: List[Dict] = field(default_factory=list)
    pending_items: List[str] = field(default_factory=list)
    origin_session: str = ""

# ================================================================
# 4. ContextCapsuleManager — 上下文胶囊管理器
# ================================================================

class ContextCapsuleManager:
    """上下文胶囊管理器 — 读取/保存跨会话连续性"""

    def __init__(self):
        self.capsule = self._load()

    def _load(self) -> SessionCapsule:
        if os.path.exists(CAPSULE_PATH):
            try:
                with open(CAPSULE_PATH) as f:
                    data = json.load(f)
                for field_name in ("task_stack", "pending_items", "origin_session"):
                    if field_name not in data:
                        data[field_name] = [] if field_name != "origin_session" else ""
                return SessionCapsule(**data)
            except Exception:
                pass
        return SessionCapsule()

    def _save(self):
        self.capsule.last_updated = datetime.now(BEIJING_TZ).isoformat()
        os.makedirs(os.path.dirname(CAPSULE_PATH) or ".", exist_ok=True)
        with open(CAPSULE_PATH, "w") as f:
            json.dump(self.capsule.__dict__, f, ensure_ascii=False, indent=2)

    def get_summary(self) -> Dict:
        return {
            "identity": self.capsule.identity_summary,
            "safety_red_lines": self.capsule.safety_red_lines,
            "current_goal": self.capsule.current_goal,
            "next_best_action": self.capsule.next_best_action,
            "mood": self.capsule.persona_mood,
            "energy": self.capsule.persona_energy,
            "trust_level": self.capsule.trust_level,
            "last_blocker": self.capsule.last_blocker,
            "task_stack": self.capsule.task_stack,
            "pending_items": self.capsule.pending_items,
        }

    # ---- 任务栈管理 ----

    def start_task(self, goal: str, next_action: str = ""):
        # N6: append 不重置
        if not hasattr(self.capsule, 'task_stack') or not self.capsule.task_stack:
            self.capsule.task_stack = []
        self.capsule.task_stack.append({"step": goal, "status": "in_progress", "ts": datetime.now(BEIJING_TZ).isoformat(), "next_action": next_action})
        self.capsule.current_goal = goal
        self.capsule.next_best_action = next_action
        self._save()

    def push_step(self, step_desc: str):
        self.capsule.task_stack.append({"step": step_desc, "status": "in_progress", "ts": datetime.now(BEIJING_TZ).isoformat()})
        self._save()

    def complete_step(self, step_desc: str = ""):
        for s in reversed(self.capsule.task_stack):
            if s["status"] == "in_progress":
                if not step_desc or s["step"] == step_desc:
                    s["status"] = "completed"
                    s["ts"] = datetime.now(BEIJING_TZ).isoformat()
                    break
        self._save()

    def update_next_action(self, action: str):
        self.capsule.next_best_action = action
        self._save()

    def add_pending(self, item: str):
        if item not in self.capsule.pending_items:
            self.capsule.pending_items.append(item)
            self._save()

    def clear_task(self):
        if self.capsule.task_stack:
            self.capsule.task_stack[-1]["status"] = "completed"
            self.capsule.task_stack[-1]["ts"] = datetime.now(BEIJING_TZ).isoformat()
        self.capsule.current_goal = ""
        self.capsule.next_best_action = ""
        self._save()

    # ---- 旧 API 保持兼容 ----

    def update_goal(self, goal: str, next_action: str = ""):
        self.start_task(goal, next_action)

    def record_blocker(self, blocker: str):
        self.capsule.last_blocker = blocker
        self.capsule.recent_events.append({
            "type": "blocker",
            "content": blocker,
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        })
        if len(self.capsule.recent_events) > 20:
            self.capsule.recent_events = self.capsule.recent_events[-20:]
        self._save()

    def record_event(self, event_type: str, content: str):
        self.capsule.recent_events.append({
            "type": event_type,
            "content": content,
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        })
        if len(self.capsule.recent_events) > 20:
            self.capsule.recent_events = self.capsule.recent_events[-20:]
        self._save()

    def increment_interaction(self):
        self.capsule.interaction_count += 1
        self._save()

    def update_trust(self, delta: float):
        self.capsule.trust_level = max(0, min(100, self.capsule.trust_level + delta))
        self._save()

    def clear_goal(self):
        self.clear_task()

# ================================================================
# 5. 全局单例
# ================================================================

_capsule_manager_instance: Optional[ContextCapsuleManager] = None

def get_capsule_manager() -> ContextCapsuleManager:
    global _capsule_manager_instance
    if _capsule_manager_instance is None:
        _capsule_manager_instance = ContextCapsuleManager()
    return _capsule_manager_instance

def init_capsule_manager():
    """ContextCapsuleManager 引擎初始化入口"""
    m = get_capsule_manager()
    print(f"  📋 上下文胶囊管理器: 已就绪")
    return {"status": "ok"}

# ── ContextStack — 多任务上下文管理（design 二 from 6/5） ──

class ContextStack:
    """多任务栈：支持任务压栈/弹栈/中断恢复"""
    
    def __init__(self, max_depth: int = 5):
        self._stack = []
        self._max_depth = max_depth
    
    def push(self, task: str, context: dict = None):
        """压入新任务上下文"""
        self._stack.append({
            "task": task,
            "context": context or {},
            "pushed_at": datetime.now(BEIJING_TZ).isoformat(),
            "interrupted": False,
        })
        if len(self._stack) > self._max_depth:
            self._stack.pop(0)
    
    def pop(self):
        """弹出栈顶任务"""
        return self._stack.pop() if self._stack else None
    
    def peek(self):
        """查看栈顶任务（不移除）"""
        return self._stack[-1] if self._stack else None
    
    def interrupt(self, reason: str = ""):
        """标记当前任务为中断状态"""
        if self._stack:
            self._stack[-1]["interrupted"] = True
            self._stack[-1]["interrupt_reason"] = reason
            self._stack[-1]["interrupted_at"] = datetime.now(BEIJING_TZ).isoformat()
    
    def resume(self):
        """恢复最近中断的任务"""
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].get("interrupted"):
                self._stack[i]["interrupted"] = False
                self._stack[i]["resumed_at"] = datetime.now(BEIJING_TZ).isoformat()
                return self._stack[i]
        return None
    
    def depth(self) -> int:
        return len(self._stack)
    
    def list_all(self) -> list:
        return list(self._stack)
    
    def clear(self):
        self._stack.clear()

class InterruptionHandler:
    """中断检测与恢复处理器"""
    
    def __init__(self, context_stack: ContextStack = None):
        self._stack = context_stack or ContextStack()
        self._interruptions = []
    
    def detect_interruption(self, current_task: str, new_incoming: str) -> bool:
        """检测新消息是否打断当前任务"""
        if not current_task or not new_incoming:
            return False
        current_kw = set(current_task.lower().split()[:10])
        new_kw = set(new_incoming.lower().split()[:10])
        overlap = len(current_kw & new_kw)
        return overlap < 1 and len(new_incoming) > 5
    
    def record_interruption(self, interrupted_task: str, new_task: str):
        """记录中断事件"""
        entry = {
            "interrupted_task": interrupted_task,
            "new_task": new_task,
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        }
        self._interruptions.append(entry)
        self._stack.interrupt(reason=f"被新任务打断: {new_task[:40]}")
    
    def try_restore(self):
        """尝试恢复最近中断的任务"""
        restored = self._stack.resume()
        if restored:
            self._interruptions.append({
                "action": "restore",
                "restored_task": restored.get("task", ""),
                "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            })
        return restored
    
    def get_stats(self) -> dict:
        return {
            "stack_depth": self._stack.depth(),
            "total_interruptions": len(self._interruptions),
            "recent": self._interruptions[-5:] if self._interruptions else [],
        }
