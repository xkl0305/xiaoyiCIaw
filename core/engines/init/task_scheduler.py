"""
Crusheart Agent OS — 四引擎核心
1. SkillRouter — 技能自动分析+执行路由引擎
2. SkillAutoInvoker — 技能自动执行器
3. Orchestrator — 引擎编排路由（见 scripts/orchestrator.py）
4. TaskScheduler — 任务调度引擎
"""

import os, re, json, math, hashlib, time, sys, traceback, subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, field

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
SKILLS_DIR = os.path.join(WORKSPACE, "skills")
ENGINE_STATE_FILE = os.path.join(WORKSPACE, ".state", ".engine_state.json")

def now_str():
    return datetime.now(BEIJING_TZ).isoformat()

# ================================================================
# 引擎1: SkillRouter
# ================================================================
SKILL_INDEX_FILE = os.path.join(WORKSPACE, ".skill_auto_index.json")
# 技能分类关键词对照表
# 可通过 config.json 中的 skill_categories 字段扩展自定义分类
# 若 config.json 中存在 skill_categories，将自动合并
CATEGORY_KEYWORDS = {
    "搜索/查询": ["搜索", "查询", "查", "搜", "联网"],
    "天气": ["天气", "气象", "温度", "下雨"],
    "创作/写作": ["写作", "写", "创作", "文案", "文章", "故事"],
    "学术/论文": ["论文", "学术", "研究", "thesis", "research", "paper", "期刊", "文献", "综述"],
    "图像/视觉": ["图像", "图片", "照片", "作图"],
    "视频": ["视频", "剪辑", "录制", "vlog"],
    "音频/语音": ["音频", "语音", "音乐", "播客", "TTS"],
    "翻译": ["翻译", "英文", "日语"],
    "金融/股票": ["股票", "基金", "行情", "金融", "投资"],
    "文档/办公": ["文档", "Word", "Excel", "PPT", "PDF"],
    "开发/技术": ["编程", "代码", "开发", "部署", "Git", "Python"],
    "教育/学习": ["学习", "教育", "教学", "课程", "学生"],
    "出行/旅游": ["出行", "路线", "导航", "机票", "打车"],
    "邮件/通信": ["邮件", "发送", "Email"],
    "生活/工具": ["外卖", "优惠", "团购", "健身"],
    "系统/配置": ["配置", "设置", "安装", "更新", "插件", "技能"],
}

# 引擎3: TaskScheduler
# ================================================================
@dataclass
class Task:
    id: str = ""
    name: str = ""
    description: str = ""
    status: str = "pending"
    priority: int = 2
    depends_on: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    result: Any = None
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    checkpoint_data: Dict = field(default_factory=dict)
    parent_task_id: str = ""
    child_task_ids: List[str] = field(default_factory=list)

TASK_QUEUE_FILE = os.path.join(WORKSPACE, ".task_scheduler.json")

class TaskScheduler:
    MAX_CONCURRENT = 4
    MAX_SUBTASKS = 10
    MAX_RETRY_WAIT = 300

    def __init__(self):
        self.tasks = {}
        self._load()

    def _load(self):
        if os.path.exists(TASK_QUEUE_FILE):
            try:
                with open(TASK_QUEUE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict): self.tasks[k] = Task(**v)
            except Exception:
                logging.exception("[task_scheduler.py] suppressed")
                self.tasks = {}

    def _save(self):
        data = {k: v.__dict__ for k, v in self.tasks.items()}
        os.makedirs(os.path.dirname(TASK_QUEUE_FILE), exist_ok=True)
        with open(TASK_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _gid(self):
        return hashlib.md5(f"{time.time()}{id(self)}".encode()).hexdigest()[:16]

    def create_task(self, name, description="", priority=2, depends_on=None):
        t = Task(id=self._gid(), name=name, description=description,
                 priority=max(0, min(3, priority)), depends_on=depends_on or [],
                 created_at=now_str(), updated_at=now_str())
        self.tasks[t.id] = t; self._save(); return t

    def split_task(self, task_id, subtasks):
        if task_id not in self.tasks: return []
        parent = self.tasks[task_id]
        if len(subtasks) > self.MAX_SUBTASKS: subtasks = subtasks[:self.MAX_SUBTASKS]
        created, prev_id = [], None
        for sub in subtasks:
            depends = sub.get("depends_on", [])
            if prev_id and not depends: depends = [prev_id]
            t = self.create_task(name=sub.get("name","子任务"), description=sub.get("description",""),
                                 priority=sub.get("priority", parent.priority), depends_on=depends)
            t.parent_task_id = task_id; created.append(t); prev_id = t.id
        parent.child_task_ids = [t.id for t in created]
        parent.status = "running"; self._save()
        return created

    def get_next_task(self):
        available = []
        for t in self.tasks.values():
            if t.status != "pending": continue
            deps_done = all(self.tasks.get(d) and self.tasks[d].status == "completed" for d in t.depends_on)
            if deps_done: available.append(t)
        available.sort(key=lambda x: (x.priority, x.created_at))
        return available[0] if available else None

    def get_top_n_tasks(self, n=None):
        n = n or self.MAX_CONCURRENT
        available = []
        for t in self.tasks.values():
            if t.status != "pending": continue
            deps_done = all(self.tasks.get(d) and self.tasks[d].status == "completed" for d in t.depends_on)
            if deps_done: available.append(t)
        available.sort(key=lambda x: (x.priority, x.created_at))
        return available[:n]

    def start_task(self, task_id):
        if task_id not in self.tasks: return False
        self.tasks[task_id].status = "running"
        self.tasks[task_id].updated_at = now_str(); self._save(); return True

    def complete_task(self, task_id, result=None):
        if task_id not in self.tasks: return
        self.tasks[task_id].status = "completed"
        self.tasks[task_id].result = result; self.tasks[task_id].updated_at = now_str(); self._save()

    def fail_task(self, task_id, error=""):
        if task_id not in self.tasks: return
        t = self.tasks[task_id]; t.error = error; t.retry_count += 1; t.updated_at = now_str()
        if t.retry_count <= t.max_retries:
            t.status = "pending"
            t.checkpoint_data["next_retry_after"] = min(2**(t.retry_count-1), self.MAX_RETRY_WAIT)
        else: t.status = "failed"
        self._save()

    def cancel_task(self, task_id):
        if task_id not in self.tasks: return
        self.tasks[task_id].status = "cancelled"; self.tasks[task_id].updated_at = now_str()
        for cid in self.tasks[task_id].child_task_ids: self.cancel_task(cid)
        self._save()

    def add_checkpoint(self, task_id, checkpoint):
        if task_id not in self.tasks: return
        cp = self.tasks[task_id].checkpoint_data
        if not isinstance(cp, dict): cp = {}
        cps = cp.get("checkpoints",[])
        cps.append({"time": now_str(), "message": checkpoint})
        cp["checkpoints"] = cps
        self.tasks[task_id].checkpoint_data = cp
        self.tasks[task_id].updated_at = now_str(); self._save()

    def get_checkpoints(self, task_id):
        if task_id not in self.tasks: return []
        cp = self.tasks[task_id].checkpoint_data
        return cp.get("checkpoints",[]) if isinstance(cp, dict) else []

    def has_active_tasks(self):
        return any(t.status in ("pending","running") for t in self.tasks.values())

    def get_active_tasks(self):
        return [t for t in self.tasks.values() if t.status in ("pending","running")]

    def format_task_summary(self, task):
        return {"id": task.id[:12], "name": task.name, "status": task.status,
                "priority": f"P{task.priority}", "checkpoints": len(self.get_checkpoints(task.id)),
                "retry": f"{task.retry_count}/{task.max_retries}" if task.retry_count > 0 else "首次",
                "subtasks": len(task.child_task_ids)}

    def get_queue_status(self):
        sc = Counter(t.status for t in self.tasks.values())
        return {"total": len(self.tasks), "pending": sc.get("pending",0),
                "running": sc.get("running",0), "completed": sc.get("completed",0),
                "failed": sc.get("failed",0), "cancelled": sc.get("cancelled",0),
                "has_active": self.has_active_tasks()}


# Orchestrator 在 core/engines/workflow/engine_orchestrator.py
import logging
try:
    from core.engines.workflow.engine_orchestrator import Orchestrator
except ImportError:
    Orchestrator = None
try:
    from core.engines.init.skill_engine import SkillRouter
except ImportError:
    SkillRouter = None


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

    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  analyze <task>  # 技能自动分析")
        print("  router <task>   # 引擎路由")
        print("  router-status   # 路由状态")
        print("  scheduler       # 调度状态")
        print("  scan            # 重扫技能")
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "analyze" and len(sys.argv) > 2:
        t = " ".join(sys.argv[2:])
        if SkillRouter is None:
            print("❌ SkillRouter 不可用，请先部署引擎"); sys.exit(1)
        a = SkillRouter(); r = a.analyze_task(t)
        print(f"📋 \"{t}\"")
        print(f"  分类: {r['matched_categories']}")
        print(f"  类型: {r['task_type']}")
        print(f"  技能数: {r['skill_count']}")
        for s in r['recommended_skills'][:5]:
            print(f"    [{s['score']:.2f}] {s['name']} — {s.get('reason','')}")
    elif cmd == "router" and len(sys.argv) > 2:
        t = " ".join(sys.argv[2:])
        from core.engines.workflow.engine_orchestrator import Orchestrator
        r = Orchestrator(); p = r.pre_process(t)
        print(f"🚦 前置: {p['mode']} — {p['reason']}")
        po = r.post_process(f"关于{t}的回答", ["https://example.com"])
        print(f"  防幻觉: {'✅' if po.get('safe') else '❌'} ({po.get('risk_level')})")
        f = r.finish_process({"content": t, "tool_calls": ["s","w"]})
        print(f"  进化: {'✅' if f.get('should_evolve') else '⏭️'} ({f.get('priority')})")
    elif cmd == "router-status":
        from core.engines.workflow.engine_orchestrator import Orchestrator
        print("🚦 Router:", Orchestrator().status())
    elif cmd == "scheduler":
        print("📊 Scheduler:", TaskScheduler().get_queue_status())
    elif cmd == "scan":
        if SkillRouter is None:
            print("❌ SkillRouter 不可用，请先部署引擎"); sys.exit(1)
        a = SkillRouter(); c = a.scan(); cats = a.get_category_summary()
        print(f"📋 扫描 {c} 个技能")
        for cat, cnt in sorted(cats.items(), key=lambda x: x[1], reverse=True)[:6]:
            print(f"  {cat}: {cnt}个")
