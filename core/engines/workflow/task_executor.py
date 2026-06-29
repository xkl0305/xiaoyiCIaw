"""
Crusheart Agent OS — TaskExecutor v4.0
任务执行引擎：解析 → 分解 → 路由 → 执行 → 验证 → 总结

与 WorkflowEngine / WorkflowOrchestrator 的关系：
- WorkflowEngine: DAG 图数据结构和构建
- WorkflowOrchestrator: DAG 图执行编排（状态机、生命周期、step驱动）
- TaskExecutor（本文件）: 单次任务的解析-分解-路由-执行-验证-总结 全流程

执行阶段 Pipeline:
  parse → validate → distribute → execute → verify → summarize → guard

与现有 Crusheart 体系对接：
- 使用 workflow_engine 的 NodeLayer/NodeStatus/GraphState
- 使用 orchestrator.py 的 GoalCompiler 进行目标编译
- 使用 unified_judge 进行治理审核
- 注入 step_executor 到 WorkflowOrchestrator
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import re
import subprocess
import uuid
import time
import asyncio

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


# ═══════════════════════════════════════════
# TODO 系统探测与任务捕获（Item 2: NL Task Capture）
# ═══════════════════════════════════════════

def detect_todo_mechanism() -> str:
    """
    探测当前环境的 TODO 系统
    返回: "today-task" | "taskflow" | "nlplanner" | "local"
    """
    # 1. today-task skill（负一屏推送）
    today_task_push = os.path.join(
        WORKSPACE, "skills", "today-task", "scripts", "task_push.py"
    )
    if os.path.exists(today_task_push):
        return "today-task"

    # 2. OpenClaw 内置 taskflow
    taskflow_path = os.path.join(WORKSPACE, "skills", "taskflow")
    if os.path.exists(taskflow_path):
        return "taskflow"

    # 3. natural-language-planner
    nlplanner_config = os.path.join(
        WORKSPACE, ".nlplanner", "config.json"
    )
    if os.path.exists(nlplanner_config):
        return "nlplanner"

    # 4. 兜底：本地 tasks 目录
    return "local"


def capture_task(
    text: str,
    project: str = "",
    priority: str = "medium",
    due_date: str = "",
) -> dict:
    """
    从自然语言捕获任务并推送到系统 TODO

    Args:
        text: 任务描述
        project: 所属项目/分类
        priority: high / medium / low
        due_date: 截止日期 (可选)

    Returns:
        {"mechanism": str, "status": str, "path": str, "error": ""}
    """
    mechanism = detect_todo_mechanism()

    if mechanism == "today-task":
        return _push_to_today_task(text, project, priority, due_date)
    elif mechanism == "taskflow":
        return _push_to_taskflow(text, project, priority, due_date)
    elif mechanism == "nlplanner":
        return _push_to_nlplanner(text, project, priority, due_date)
    else:
        return _push_to_local(text, project, priority, due_date)


def _push_to_today_task(text: str, project: str, priority: str, due_date: str) -> dict:
    """推送到 today-task 负一屏"""
    push_script = os.path.join(
        WORKSPACE, "skills", "today-task", "scripts", "task_push.py"
    )
    if not os.path.exists(push_script):
        return _push_to_local(text, project, priority, due_date)

    try:
        import json as _json
        tmp_data = _json.dumps({
            "task_name": project or "待办",
            "task_content": f"# {project or '任务'}\n\n{text}\n\n- 优先级: {priority}" + (f"\n- 截止: {due_date}" if due_date else ""),
            "task_result": "待办",
        }, ensure_ascii=False)
        tmp_file = os.path.join("/tmp", f"task_capture_{int(time.time())}.json")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(tmp_data)
        result = subprocess.run(
            ["python3", push_script, "--data", tmp_file],
            capture_output=True, text=True, timeout=10
        )
        os.unlink(tmp_file)
        if result.returncode == 0:
            return {"mechanism": "today-task", "status": "pushed", "path": "", "error": ""}
        else:
            return {"mechanism": "today-task", "status": "failed", "path": "",
                    "error": result.stderr[:200]}
    except Exception as e:
        return {"mechanism": "today-task", "status": "error", "path": "", "error": str(e)[:200]}


def _push_to_taskflow(text: str, project: str, priority: str, due_date: str) -> dict:
    """推送到 OpenClaw taskflow"""
    try:
        tasks_file = os.path.join(WORKSPACE, ".taskflow", "inbox.json")
        os.makedirs(os.path.dirname(tasks_file), exist_ok=True)
        entry = {
            "id": f"task_{int(time.time() * 1000)}",
            "text": text,
            "project": project,
            "priority": priority,
            "due_date": due_date,
            "created_at": datetime.now(BEIJING_TZ).isoformat(),
            "status": "pending",
        }
        existing = []
        if os.path.exists(tasks_file):
            with open(tasks_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(entry)
        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return {"mechanism": "taskflow", "status": "saved", "path": tasks_file, "error": ""}
    except Exception as e:
        return {"mechanism": "taskflow", "status": "error", "path": "", "error": str(e)[:200]}


def _push_to_nlplanner(text: str, project: str, priority: str, due_date: str) -> dict:
    """推送到 natural-language-planner"""
    try:
        planner_dir = os.path.join(WORKSPACE, ".nlplanner")
        os.makedirs(planner_dir, exist_ok=True)
        tasks_file = os.path.join(planner_dir, "inbox.csv" if os.path.exists(os.path.join(planner_dir, "inbox.csv")) else "tasks.json")
        if tasks_file.endswith(".csv"):
            with open(tasks_file, "a", encoding="utf-8") as f:
                f.write(f'"{text}","{project}","{priority}","{due_date}","{datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")}",pending\n')
        else:
            entry = {"text": text, "project": project, "priority": priority,
                     "due_date": due_date, "created_at": datetime.now(BEIJING_TZ).isoformat(),
                     "status": "pending"}
            existing = []
            if os.path.exists(tasks_file):
                with open(tasks_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.append(entry)
            with open(tasks_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        return {"mechanism": "nlplanner", "status": "saved", "path": tasks_file, "error": ""}
    except Exception as e:
        return {"mechanism": "nlplanner", "status": "error", "path": "", "error": str(e)[:200]}


def _push_to_local(text: str, project: str, priority: str, due_date: str) -> dict:
    """兜底：写入本地 tasks 目录"""
    try:
        tasks_dir = os.path.join(WORKSPACE, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        tasks_file = os.path.join(tasks_dir, f"{today}.md")

        entry = f"- [ ] **{text}**"
        if project:
            entry += f" （{project}）"
        entry += f" 优先级: {priority}"
        if due_date:
            entry += f" 截止: {due_date}"
        entry += f" 创建: {datetime.now(BEIJING_TZ).strftime('%H:%M')}\n"

        with open(tasks_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return {"mechanism": "local", "status": "saved", "path": tasks_file, "error": ""}
    except Exception as e:
        return {"mechanism": "local", "status": "error", "path": "", "error": str(e)[:200]}


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class IntentType(str, Enum):
    """任务意图类型"""
    QUERY = "query"              # 查询/搜索
    CREATE = "create"            # 创建
    UPDATE = "update"            # 更新
    DELETE = "delete"            # 删除
    ORCHESTRATE = "orchestrate"  # 多步编排
    EXECUTE = "execute"          # 通用执行
    ANALYSIS = "analysis"        # 分析/总结
    CONFIRM = "confirm"          # 确认类
    UNKNOWN = "unknown"          # 未识别


class SubTaskStatus(str, Enum):
    """子任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerifyStatus(str, Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class Entity:
    """从用户输入中提取的实体"""
    action: Optional[str] = None       # 动作类型（create_note / set_alarm / search...）
    target: Optional[str] = None        # 操作目标（note / event / file / photo...）
    time: Optional[str] = None          # 时间实体
    count: Optional[int] = None         # 数量
    keywords: List[str] = field(default_factory=list)  # 关键词
    raw_input: str = ""                  # 原始输入
    verification_need: bool = False     # 是否需要验证


@dataclass
class SubTask:
    """
    子任务 — 解析-分解后的最小可执行单元
    
    与 TaskNode 的区别：
    - SubTask: 逻辑层面的任务分配单元（含技能路由信息）
    - TaskNode: 图执行层面的 DAG 节点（含设备侧/依赖/状态）
    """
    id: str
    name: str
    intent_type: IntentType
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    assigned_skill: Optional[str] = None
    priority: int = 0
    status: SubTaskStatus = SubTaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "intent_type": self.intent_type.value,
            "assigned_skill": self.assigned_skill,
            "status": self.status.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
        }


@dataclass
class TaskExecutionResult:
    """
    一次任务执行的完整结果
    
    给上层（对话系统/用户界面）使用，包含：
    - 执行摘要（哪些成功、哪些失败）
    - 验证结果
    - 用户响应文本
    - 证据链
    """
    status: str                                  # "success" | "failed" | "partial"
    summary: str                                 # 摘要描述
    completed_items: List[str] = field(default_factory=list)
    failed_items: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    execution_trace: List[Dict] = field(default_factory=list)
    total_latency_ms: float = 0.0
    task_id: str = ""
    intent: str = ""


# ═══════════════════════════════════════════
# 任务解析器
# ═══════════════════════════════════════════

class TaskParser:
    """
    任务解析器
    
    把用户自然语言输入解析成结构化 Task。
    当前实现基于关键词/正则，后续可接入 LLM 解析器。
    """

    ACTION_PATTERNS = {
        "create_note": ["创建备忘录", "新建备忘录", "添加备忘录", "记下来",
                        "写备忘", "创建笔记", "新建笔记"],
        "create_event": ["创建日程", "新建日程", "添加日程", "安排",
                         "创建事件", "新建事件"],
        "create_alarm": ["创建闹钟", "设置闹钟", "定闹钟", "添加闹钟"],
        "search_note": ["搜索备忘录", "查找备忘录", "找备忘录", "查备忘录"],
        "search_event": ["搜索日程", "查找日程", "查日程", "搜索事件"],
        "search_web": ["搜索", "查找", "查一下", "搜一下", "百度一下",
                       "search", "find", "google"],
        "send_message": ["发送消息", "发短信", "发消息", "发微信"],
        "call_phone": ["打电话", "拨打电话", "拨号"],
        "search_photo": ["搜索照片", "找照片", "查照片", "搜图片"],
        "analyze": ["分析", "总结", "归纳", "汇总", "整理"],
        "config": ["设置", "配置", "调整", "修改"],
    }

    TARGET_PATTERNS = {
        "note": ["备忘录", "笔记", "记事", "note"],
        "event": ["日程", "事件", "会议", "event", "calendar"],
        "alarm": ["闹钟", "提醒", "alarm"],
        "photo": ["照片", "图片", "相册", "photo", "image"],
        "contact": ["联系人", "通讯录", "contact"],
        "file": ["文件", "文档", "file", "document"],
        "weather": ["天气", "温度", "weather", "temperature"],
        "news": ["新闻", "资讯", "news"],
    }

    def parse(self, user_input: str) -> Entity:
        """解析用户输入为结构化实体"""
        entity = Entity(raw_input=user_input)

        # 1. 提取目标动作
        for action, keywords in self.ACTION_PATTERNS.items():
            if any(kw in user_input for kw in keywords):
                entity.action = action
                break

        # 2. 提取操作目标
        for target, keywords in self.TARGET_PATTERNS.items():
            if any(kw in user_input for kw in keywords):
                entity.target = target
                break

        # 3. 提取时间实体
        if "今天" in user_input:
            entity.time = "today"
        elif "明天" in user_input:
            entity.time = "tomorrow"
        elif "后天" in user_input:
            entity.time = "day_after_tomorrow"
        elif "昨天" in user_input:
            entity.time = "yesterday"

        # 4. 提取数字
        num_match = re.search(r'(\d+)', user_input)
        if num_match:
            entity.count = int(num_match.group(1))

        # 5. 判断是否需要验证
        if entity.action in [
            "create_note", "create_event", "create_alarm",
            "send_message", "call_phone"
        ]:
            entity.verification_need = True

        # 6. 提取关键词（去除停用词后的核心词）
        stop_words = {"的", "了", "在", "是", "有", "我", "你", "他",
                       "这", "那", "和", "与", "就", "也", "还", "都"}
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', user_input)
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        entity.keywords = keywords[:5]

        logger.debug(f"[TaskParser] 解析结果: action={entity.action} "
                     f"target={entity.target} time={entity.time}")

        return entity

    def detect_intent(self, entity: Entity) -> IntentType:
        """根据实体推断意图类型"""
        if entity.action:
            action = entity.action
            if action.startswith("create_"):
                return IntentType.CREATE
            elif action.startswith("search_"):
                return IntentType.QUERY
            elif action == "send_message" or action == "call_phone":
                return IntentType.EXECUTE
            elif action == "analyze":
                return IntentType.ANALYSIS
            elif action == "config":
                return IntentType.UPDATE
        return IntentType.UNKNOWN


# ═══════════════════════════════════════════
# 任务分解器
# ═══════════════════════════════════════════

class TaskDecomposer:
    """
    任务分解器
    
    根据意图类型，将 Entity 拆解为一系列 SubTask。
    
    分解策略：
    - CREATE: validate → execute → verify → summarize
    - QUERY: execute → summarize
    - UPDATE: validate → execute → verify
    - DELETE: validate → execute
    - ANALYSIS: execute → summarize
    - 默认: execute
    """

    # action → skill 名映射（decompose 中用此设置 subtask.assigned_skill）
    ACTION_TO_SKILL = {
        "create_note": "memo_create",
        "create_todo": "todo_create",
        "search_web": "web_search",
        "send_message": "messaging",
        "query_weather": "weather_query",
        "create_alarm": "alarm_create",
        "create_calendar": "calendar_create",
        "query_info": "info_query",
        "send_email": "email_send",
        "delegate": "agent_delegate",
    }

    def __init__(self):
        self._task_counter = 0

    def _next_id(self) -> str:
        self._task_counter += 1
        return f"st_{int(time.time() * 1000)}_{self._task_counter}"

    def decompose(self, entity: Entity, intent: IntentType) -> List[SubTask]:
        """将实体拆解为子任务列表"""
        self._task_counter = 0
        subtasks: List[SubTask] = []

        base_input = {
            "action": entity.action,
            "target": entity.target,
            "time": entity.time,
            "count": entity.count,
            "keywords": entity.keywords,
            "raw_input": entity.raw_input,
        }

        if intent == IntentType.CREATE:
            # validate → execute → verify → summarize
            subtasks.append(SubTask(
                id=self._next_id(), name="validate_input",
                intent_type=IntentType.EXECUTE, inputs={"validate": True, **base_input},
                priority=10
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name=f"execute_{entity.action or 'create'}",
                intent_type=intent, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=8, dependencies=[subtasks[0].id]
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name="verify_result",
                intent_type=IntentType.EXECUTE, inputs={"verify": True, **base_input},
                priority=5, dependencies=[subtasks[1].id]
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name="summarize_result",
                intent_type=IntentType.ANALYSIS, inputs={"summarize": True, **base_input},
                priority=3, dependencies=[subtasks[2].id]
            ))

        elif intent == IntentType.QUERY:
            # execute → summarize
            subtasks.append(SubTask(
                id=self._next_id(), name=f"search_{entity.target or 'web'}",
                intent_type=intent, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=8
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name="summarize_result",
                intent_type=IntentType.ANALYSIS,
                inputs={"summarize": True, **base_input},
                priority=3, dependencies=[subtasks[0].id]
            ))

        elif intent == IntentType.UPDATE:
            # validate → execute → verify
            subtasks.append(SubTask(
                id=self._next_id(), name="validate_input",
                intent_type=IntentType.EXECUTE, inputs={"validate": True, **base_input},
                priority=10
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name=f"update_{entity.target or 'config'}",
                intent_type=intent, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=8, dependencies=[subtasks[0].id]
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name="verify_result",
                intent_type=IntentType.EXECUTE,
                inputs={"verify": True, **base_input},
                priority=5, dependencies=[subtasks[1].id]
            ))

        elif intent == IntentType.DELETE:
            # validate → execute
            subtasks.append(SubTask(
                id=self._next_id(), name="validate_input",
                intent_type=IntentType.EXECUTE, inputs={"validate": True, **base_input},
                priority=10
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name=f"delete_{entity.target or 'item'}",
                intent_type=intent, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=8, dependencies=[subtasks[0].id]
            ))

        elif intent == IntentType.ANALYSIS:
            # execute → summarize
            subtasks.append(SubTask(
                id=self._next_id(), name="analyze_data",
                intent_type=intent, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=8
            ))
            subtasks.append(SubTask(
                id=self._next_id(), name="summarize_result",
                intent_type=IntentType.ANALYSIS,
                inputs={"summarize": True, **base_input},
                priority=3, dependencies=[subtasks[0].id]
            ))

        else:
            # 默认：单步执行
            subtasks.append(SubTask(
                id=self._next_id(), name="execute_default",
                intent_type=IntentType.EXECUTE, inputs=base_input,
                assigned_skill=self.ACTION_TO_SKILL.get(entity.action),
                priority=5
            ))

        # 拓扑排序（按优先级降序、依赖数升序）
        subtasks.sort(key=lambda t: (-t.priority, len(t.dependencies)))

        logger.debug(f"[TaskDecomposer] 分解结果: intent={intent.value} "
                     f"subtasks={[s.name for s in subtasks]}")
        return subtasks


# ═══════════════════════════════════════════
# 任务执行器
# ═══════════════════════════════════════════

class TaskExecutor:
    """
    任务执行器
    
    职责：执行分解后的 SubTask 列表（按依赖关系），管理执行结果。
    
    注意：
    - SubTask 执行不依赖 WorkflowOrchestrator，是逻辑执行层
    - 与 WorkflowOrchestrator 的对接入口是注入 step_executor.register()
    - TaskExecutor 可以在 WorkflowOrchestrator 外部独立使用
    """

    def __init__(self):
        self.results: Dict[str, Any] = {}
        self._handlers: Dict[str, Any] = {}

    def register_skill(self, name: str, handler: Any) -> None:
        """注册技能执行器（name 匹配 SubTask.assigned_skill）"""
        self._handlers[name] = handler

    async def execute(self, subtasks: List[SubTask],
                      context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行子任务列表（按依赖关系拓扑执行）
        
        Args:
            subtasks: 已排好序的子任务列表
            context: 执行上下文
            
        Returns:
            { subtask_id: result, ... } 结果字典
        """
        context = context or {}
        executed: Set[str] = set()
        self.results = {}

        while len(executed) < len(subtasks):
            # 找出所有依赖已满足的待执行子任务
            ready = [
                t for t in subtasks
                if t.id not in executed
                and all(d in executed for d in t.dependencies)
            ]
            if not ready:
                # 剩余任务有未满足的依赖 → 循环依赖或死锁
                stuck = [t.id for t in subtasks if t.id not in executed]
                logger.error(f"[TaskExecutor] 无法继续执行，剩余任务: {stuck}")
                break

            # 执行 ready 子任务
            for task in ready:
                start = time.time()
                task.status = SubTaskStatus.RUNNING

                try:
                    result = await self._execute_single(task, context)
                    task.status = SubTaskStatus.COMPLETED
                    task.outputs = result if isinstance(result, dict) else {"result": result}
                    self.results[task.id] = task.outputs
                    executed.add(task.id)
                    task.latency_ms = (time.time() - start) * 1000

                    logger.info(
                        f"[TaskExecutor] 完成: {task.name} "
                        f"skill={task.assigned_skill} "
                        f"latency={task.latency_ms:.0f}ms"
                    )

                except Exception as e:
                    task.status = SubTaskStatus.FAILED
                    task.error = str(e)
                    executed.add(task.id)
                    task.latency_ms = (time.time() - start) * 1000
                    logger.error(
                        f"[TaskExecutor] 失败: {task.name} - {e}"
                    )

        return self.results

    async def _execute_single(self, task: SubTask, context: dict) -> Any:
        """执行单个子任务"""
        # 校验类任务（本地逻辑，不调用技能）
        if task.inputs.get("validate"):
            return self._do_validate(task)
        if task.inputs.get("verify"):
            return self._do_verify(task, self.results)
        if task.inputs.get("summarize"):
            return self._do_summarize(task, self.results)

        # 有注册的技能 → 调用技能
        if task.assigned_skill and task.assigned_skill in self._handlers:
            handler = self._handlers[task.assigned_skill]
            if asyncio.iscoroutinefunction(handler):
                return await handler(task, context)
            else:
                return handler(task, context)

        # 无技能可用 → 返回标记
        return {
            "status": "no_handler",
            "message": f"未注册执行器: {task.assigned_skill or 'none'}",
            "intent": task.intent_type.value,
        }

    def _do_validate(self, task: SubTask) -> Dict[str, Any]:
        """内置校验逻辑"""
        missing = []
        inputs = task.inputs
        if not inputs.get("action"):
            missing.append("action")

        return {
            "type": "validate",
            "valid": len(missing) == 0,
            "missing_params": missing,
            "message": "参数校验通过" if not missing else f"缺少参数: {missing}",
        }

    def _do_verify(self, task: SubTask, results: Dict[str, Any]) -> Dict[str, Any]:
        """内置验证逻辑"""
        evidences = []

        for tid, result in results.items():
            if not isinstance(result, dict):
                continue
            # 文件存在性
            if "file_path" in result or "output_file" in result:
                path = result.get("file_path") or result.get("output_file", "")
                import os
                exists = os.path.exists(path) if path else False
                evidences.append({"type": "file", "path": path, "exists": exists})

            # 记录 ID
            if "record_id" in result or "task_id" in result:
                rid = result.get("record_id") or result.get("task_id")
                evidences.append({"type": "record", "id": rid, "exists": True})

            # 内容
            if "content" in result or "text" in result:
                content = result.get("content") or result.get("text", "")
                evidences.append({
                    "type": "content", "length": len(content),
                    "exists": len(content) > 0
                })

        verified = any(e.get("exists") for e in evidences)
        return {
            "type": "verify",
            "verified": verified,
            "evidences": evidences,
            "message": "验证通过" if verified else "无有效证据",
        }

    def _do_summarize(self, task: SubTask, results: Dict[str, Any]) -> Dict[str, Any]:
        """内置总结逻辑"""
        completed = []
        failed = []
        evidence = {}

        for tid, result in results.items():
            if isinstance(result, dict):
                if result.get("error"):
                    failed.append({"task_id": tid, "error": result["error"]})
                elif result.get("valid") == False:
                    failed.append({"task_id": tid, "reason": "参数校验失败"})
                else:
                    completed.append(tid)
                    evidence.update(result)
            else:
                completed.append(tid)

        status = "success" if not failed else ("partial" if completed else "failed")

        return {
            "type": "summarize",
            "status": status,
            "completed_items": completed,
            "failed_items": failed,
            "evidence": evidence,
            "message": f"完成 {len(completed)} 项, 失败 {len(failed)} 项",
        }


# ═══════════════════════════════════════════
# TaskEngine — 完整闭环
# ═══════════════════════════════════════════

class TaskEngine:
    """
    任务引擎 — 完整闭环入口
    
    使用流程:
        engine = TaskEngine()
        engine.register_skill("web_search", my_search_handler)
        result = await engine.process("帮我查一下天津明天的天气")
        # result.status, result.summary, result.completed_items ...
    
    完整流水线:
        parse → detect_intent → decompose → execute → [optional verify/summarize]
    """

    def __init__(self):
        self.parser = TaskParser()
        self.decomposer = TaskDecomposer()
        self.executor = TaskExecutor()

    def register_skill(self, name: str, handler: Any) -> None:
        """注册技能执行器"""
        self.executor.register_skill(name, handler)

    async def process(self, user_input: str,
                      intent_override: Optional[IntentType] = None,
                      context: Optional[Dict] = None) -> TaskExecutionResult:
        """
        处理用户输入——执行完整的解析→分解→执行→验证→总结

        Args:
            user_input: 用户原始输入
            intent_override: 可选，强制指定意图类型
            context: 执行上下文

        Returns:
            TaskExecutionResult 包含最终结果
        """
        start = time.time()

        # 1. 解析
        entity = self.parser.parse(user_input)
        intent = intent_override or self.parser.detect_intent(entity)

        # 2. 分解
        subtasks = self.decomposer.decompose(entity, intent)

        logger.info(
            f"[TaskEngine] 开始处理: intent={intent.value} "
            f"subtasks={len(subtasks)} input={user_input[:50]}"
        )

        # 3. 执行
        _ = await self.executor.execute(subtasks, context)

        # 4. 构建执行追踪
        execution_trace = []
        completed_items = []
        failed_items = []

        for st in subtasks:
            trace_entry = st.to_dict()
            execution_trace.append(trace_entry)
            if st.status == SubTaskStatus.COMPLETED:
                completed_items.append(st.name)
            elif st.status == SubTaskStatus.FAILED:
                failed_items.append(st.name)

        # 5. 确定最终状态
        if not failed_items:
            final_status = "success"
        elif completed_items:
            final_status = "partial"
        else:
            final_status = "failed"

        # 6. 汇总证据
        evidence = {}
        for tid, result in self.executor.results.items():
            if isinstance(result, dict):
                evidence[tid] = {
                    k: v for k, v in result.items()
                    if k not in ("type",)
                }

        total_latency = (time.time() - start) * 1000

        # 7. 构建摘要
        summary_parts = []
        if completed_items:
            summary_parts.append(f"✅ 完成: {', '.join(completed_items)}")
        if failed_items:
            summary_parts.append(f"❌ 失败: {', '.join(failed_items)}")
        summary = " | ".join(summary_parts) if summary_parts else "处理完成（无明确结果）"

        result = TaskExecutionResult(
            status=final_status,
            summary=summary,
            completed_items=completed_items,
            failed_items=failed_items,
            evidence=evidence,
            execution_trace=execution_trace,
            total_latency_ms=round(total_latency, 2),
            task_id=f"task_{int(time.time() * 1000)}",
            intent=intent.value,
        )

        logger.info(
            f"[TaskEngine] 处理完成: status={final_status} "
            f"latency={total_latency:.0f}ms "
            f"completed={len(completed_items)} failed={len(failed_items)}"
        )

        return result


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

    import asyncio

    async def test():
        logging.basicConfig(level=logging.INFO)

        engine = TaskEngine()

        # 注册模拟 skill
        async def mock_search(task, ctx):
            return {"result": f"搜索完成: {task.inputs.get('keywords', [])}", "status": "ok"}
        engine.register_skill("web_search", mock_search)

        # 测试1: 查询类
        print("=" * 60)
        print("测试1: 查询类任务")
        print("=" * 60)
        r1 = await engine.process("帮我查一下天津明天的天气")
        print(f"  status: {r1.status}")
        print(f"  summary: {r1.summary}")
        print(f"  intent: {r1.intent}")
        print(f"  latency: {r1.total_latency_ms:.0f}ms")
        print(f"  completed: {r1.completed_items}")
        print(f"  failed: {r1.failed_items}")
        print()

        # 测试2: 创建类
        print("=" * 60)
        print("测试2: 创建类任务")
        print("=" * 60)
        r2 = await engine.process("帮我设置明天8点的闹钟")
        print(f"  status: {r2.status}")
        print(f"  summary: {r2.summary}")
        print(f"  subtask轨迹: {len(r2.execution_trace)}步")
        for t in r2.execution_trace:
            print(f"    {t['name']}: {t['status']}")
        print()

        # 测试3: 分析类
        print("=" * 60)
        print("测试3: 分析类任务")
        print("=" * 60)
        r3 = await engine.process("分析我这周的日志数据")
        print(f"  status: {r3.status}")
        print(f"  summary: {r3.summary}")
        print()

        # 测试4: 空输入
        print("=" * 60)
        print("测试4: 空意图任务")
        print("=" * 60)
        r4 = await engine.process("你好")
        print(f"  status: {r4.status}")
        print(f"  intent: {r4.intent}")
        print(f"  subtask: {[t['name'] for t in r4.execution_trace]}")
        print()

        print("所有测试通过 ✅")

    asyncio.run(test())
