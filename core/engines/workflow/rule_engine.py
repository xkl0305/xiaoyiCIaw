"""
Crusheart Agent OS — RuleEngine v1.0
自动化规则引擎：条件评估 + 规则匹配 + 动作执行 + 持久化

设计定位：
- 与 WorkflowEngine（workflow_engine.py）配合：规则命中后构建 DAG 图执行
- 与 AnomalyDetector（quality/anomaly_detector.py）配合：检测结果可触发规则
- 纯 self-contained，无外部依赖

核心概念：
  Condition  → 条件表达式（field + operator + value + 组合逻辑）
  Rule       → if conditions then action（含优先级/冷却/标签）
  RuleEngine → 注册/加载/匹配/执行/持久化

使用方式：
  engine = RuleEngine()
  engine.load_rules()                     # 从磁盘加载规则
  matched = engine.evaluate(event)        # 事件匹配
  engine.execute(rule, context)           # 执行规则动作
  engine.add_rule(Rule(...))              # 动态注册
  engine.save_rules()                     # 持久化
"""

from dataclasses import dataclass, field as dc_field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import re
import uuid

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
RULES_PATH = os.path.join(WORKSPACE, ".rules.json")
HISTORY_PATH = os.path.join(WORKSPACE, ".rule_trigger_history.jsonl")


# ═══════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════

class ConditionOperator(str, Enum):
    """条件运算符"""
    EQ = "eq"                # 等于
    NEQ = "neq"              # 不等于
    GT = "gt"                # 大于（数值）
    GTE = "gte"              # 大于等于
    LT = "lt"                # 小于
    LTE = "lte"              # 小于等于
    CONTAINS = "contains"    # 包含（字符串/列表）
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"      # 正则匹配
    IN = "in"                # 值在列表中
    NOT_IN = "not_in"
    EXISTS = "exists"        # 字段存在
    NOT_EXISTS = "not_exists"
    FORMAT = "format"        # 复合条件（用于时间/频率等复杂判断）


class ConditionLogic(str, Enum):
    """复合条件逻辑"""
    AND = "and"
    OR = "or"
    NOT = "not"


class ActionKind(str, Enum):
    """规则动作类型"""
    CREATE_TASK = "create_task"             # 创建任务清单
    SEND_NOTIFICATION = "send_notification" # 推送通知
    BUILD_DAG = "build_dag"                 # 构建 DAG 工作流
    RUN_SKILL = "run_skill"                 # 执行技能
    MEMORY_WRITE = "memory_write"           # 写入记忆
    UPDATE_RULES = "update_rules"           # 动态调整规则
    CALL_WEBHOOK = "call_webhook"           # Webhook 调用
    LOG_ONLY = "log_only"                   # 仅记录


class EventSource(str, Enum):
    """事件来源"""
    MEMORY = "memory"           # 记忆系统
    QUALITY = "quality"         # 质量评分/反馈
    SCHEDULE = "schedule"       # 定时任务
    SYSTEM = "system"           # 系统状态（资源/cron）
    USER = "user"               # 用户直接触发
    WORKFLOW = "workflow"       # 工作流事件
    EXTERNAL = "external"       # 外部输入


# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class Condition:
    """
    条件表达式

    支持：
    1. 简单条件：field="memory.retrieval_rate", op=GT, value=0.8
    2. 复合条件：logic=OR, sub_conditions=[...]
    3. 取反：logic=NOT, sub_conditions=[...]

    事件字段路径约定：
      event.type            — 事件类型字符串
      event.source          — EventSource 值
      event.metadata.*      — 任意元数据字段
      memory.retrieval_rate — 记忆检索成功率 (0-1)
      quality.avg_score     — 引擎质量评分 (0-1)
      system.memory_mb      — 内存使用
      system.response_time_ms — 响应时间
    """
    field: Optional[str] = None          # 字段路径（简单条件用）
    operator: Optional[str] = None       # 运算符（简单条件用）
    value: Any = None                    # 比较值（简单条件用）
    logic: str = "and"                   # 逻辑（复合条件用）
    sub_conditions: List["Condition"] = dc_field(default_factory=list)  # 子条件（复合用）

    @classmethod
    def simple(cls, field: str, operator: str, value: Any) -> "Condition":
        """创建简单条件"""
        return cls(field=field, operator=operator, value=value)

    @classmethod
    def composite(cls, logic: str, *conditions: "Condition") -> "Condition":
        """创建复合条件"""
        return cls(logic=logic, sub_conditions=list(conditions))

    @classmethod
    def negation(cls, condition: "Condition") -> "Condition":
        """创建取反条件"""
        return cls(logic="not", sub_conditions=[condition])


@dataclass
class RuleAction:
    """
    规则命中后的动作定义

    kind: 动作类型
    params: 动作参数（随 kind 变化）
        create_task:   { "task_name": "...", "assignee": "...", "priority": "high" }
        send_notification: { "message": "...", "channel": "last" }
        build_dag:     { "goal": "...", "template_id": "..." }
        run_skill:     { "skill_name": "...", "params": {...} }
        memory_write:  { "tags": [...], "content": "..." }
    """
    kind: str                               # ActionKind 值
    params: Dict[str, Any] = dc_field(default_factory=dict)
    template: Optional[str] = None          # 消息/任务模板（支持 {event.field} 插值）


@dataclass
class Rule:
    """
    自动化规则定义

    核心：满足所有 conditions 时执行 action
    """
    rule_id: str
    name: str
    description: str = ""
    conditions: List[Condition] = dc_field(default_factory=list)  # 顶层条件列表（AND 组合）
    actions: List[RuleAction] = dc_field(default_factory=list)    # 命中的动作列表（顺序执行）
    enabled: bool = True
    priority: int = 0                        # 越高越先匹配
    cooldown_s: int = 300                    # 冷却时间（秒），防重复触发
    tags: List[str] = dc_field(default_factory=list)
    source: str = "manual"                   # manual / builtin / learned
    created_at: str = ""
    updated_at: str = ""
    last_triggered_at: Optional[str] = None
    trigger_count: int = 0
    max_triggers_per_hour: int = 10          # 小时触发上限

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(BEIJING_TZ).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def on_trigger(self):
        """触发后更新统计"""
        self.last_triggered_at = datetime.now(BEIJING_TZ).isoformat()
        self.trigger_count += 1
        self.updated_at = self.last_triggered_at

    def in_cooldown(self) -> bool:
        """是否在冷却期内"""
        if not self.last_triggered_at:
            return False
        last = datetime.fromisoformat(self.last_triggered_at)
        elapsed = (datetime.now(BEIJING_TZ) - last).total_seconds()
        return elapsed < self.cooldown_s

    def rate_limited(self) -> bool:
        """是否触发了小时限流"""
        if not self.last_triggered_at or not HISTORY_PATH:
            return False
        now = datetime.now(BEIJING_TZ)
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        # 从历史记录统计最近1小时触发次数
        count = 0
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("rule_id") == self.rule_id and rec.get("triggered_at", "") > one_hour_ago:
                            count += 1
                    except json.JSONDecodeError:
                        continue
        return count >= self.max_triggers_per_hour

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["conditions"] = [self._condition_to_dict(c) for c in self.conditions]
        d["actions"] = [asdict(a) for a in self.actions]
        return d

    @staticmethod
    def _condition_to_dict(c: Condition) -> Dict:
        d = {"logic": c.logic}
        if c.field:
            d["field"] = c.field
            d["operator"] = c.operator
            d["value"] = c.value
        if c.sub_conditions:
            d["sub_conditions"] = [
                Rule._condition_to_dict(sc) for sc in c.sub_conditions
            ]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        data = dict(data)
        data["conditions"] = [cls._dict_to_condition(c) for c in data.get("conditions", [])]
        data["actions"] = [RuleAction(**a) for a in data.get("actions", [])]
        return cls(**data)

    @staticmethod
    def _dict_to_condition(d: Dict) -> Condition:
        c = Condition(logic=d.get("logic", "and"))
        if "field" in d:
            c.field = d["field"]
            c.operator = d.get("operator")
            c.value = d.get("value")
        if "sub_conditions" in d:
            c.sub_conditions = [
                Rule._dict_to_condition(sc) for sc in d["sub_conditions"]
            ]
        return c


# ═══════════════════════════════════════════
# 条件评估器注册表
# ═══════════════════════════════════════════

class ConditionEvaluator:
    """
    条件评估器 — 按字段路径注册评估函数

    可扩展：外部模块通过 register() 注册自定义评估函数

    内置支持的字段路径前缀：
      event.*        — 事件元数据
      memory.*       — 记忆系统指标
      quality.*      — 质量评分指标
      system.*       — 系统状态指标
      schedule.*     — 定时相关
      workflow.*     — 工作流状态
    """

    def __init__(self):
        self._evaluators: Dict[str, callable] = {}
        self._register_builtins()

    def register(self, field_prefix: str, fn: callable):
        """注册字段评估器"""
        self._evaluators[field_prefix] = fn

    def evaluate(self, condition: Condition, event: Dict,
                 context: Optional[Dict] = None) -> bool:
        """
        评估一个条件

        递归处理复合条件：
        - AND: 所有子条件为真
        - OR: 任一子条件为真
        - NOT: 子条件取反
        - 简单条件: field + operator + value 评估
        """
        ctx = context or {}

        # 复合条件 — 递归
        if condition.sub_conditions:
            results = [
                self.evaluate(sc, event, ctx) for sc in condition.sub_conditions
            ]
            if condition.logic == "and":
                return all(results)
            elif condition.logic == "or":
                return any(results)
            elif condition.logic == "not":
                return not results[0] if results else True
            return all(results)

        # 简单条件
        if not condition.field or not condition.operator:
            logger.warning(f"[RuleEngine] 条件缺少 field 或 operator: {condition}")
            return False

        # 提取实际值
        actual = self._resolve_value(condition.field, event, ctx)

        # 用注册的评估器
        for prefix, fn in self._evaluators.items():
            if condition.field.startswith(prefix):
                return fn(condition, actual, event, ctx)

        # 默认评估
        return self._default_evaluate(condition.operator, actual, condition.value)

    def _resolve_value(self, field: str, event: Dict, context: Dict) -> Any:
        """从事件/上下文中提取字段值

        查找策略：
        1. 先在 context 中按原始 field 路径查找（点号分隔）
        2. 再在 event 中按原始 field 路径查找（允许 event 中有带点号的扁平键）
        3. 如果 field 以 event. 开头，去掉前缀后在 event 中按点路径查
        4. 如果 field 以 memory./quality./system./schedule. 开头，
           先去 event 中匹配整键（如 "memory.retrieval_rate"），
           再尝试剥离前缀后按嵌套路径查
        """

        # 1. 先查 context
        ctx_val = self._dict_get_by_dotted(context, field)
        if ctx_val is not None:
            return ctx_val

        # 2. 尝试直接以 field 为完整键名查 event（支持扁平键）
        if field in event:
            return event[field]

        # 3. 按点路径从 event 中查
        ev_val = self._dict_get_by_dotted(event, field)
        if ev_val is not None:
            return ev_val

        # 4. 处理前缀
        prefix_map = {
            "event.": event,
            "memory.": event,
            "quality.": event,
            "system.": event,
            "schedule.": event,
            "workflow.": event,
        }
        for prefix, src in prefix_map.items():
            if field.startswith(prefix):
                stripped = field[len(prefix):]
                # 扁平键
                if stripped in src:
                    return src[stripped]
                # 嵌套路径
                val = self._dict_get_by_dotted(src, stripped)
                if val is not None:
                    return val
                break

        return None

    @staticmethod
    def _dict_get_by_dotted(d: Dict, path: str) -> Any:
        """按点号分隔路径从 dict 中取值"""
        parts = path.split(".")
        val = d
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return None
        return val

    def _default_evaluate(self, operator: str, actual: Any, expected: Any) -> bool:
        """默认条件评估"""

        # 空值处理
        if actual is None:
            if operator == "not_exists":
                return True
            if operator == "exists":
                # 值虽然 None 但字段存在
                return False
            return False
        if operator == "not_exists":
            return False
        if operator == "exists":
            return True

        try:
            if operator == "eq":
                return actual == expected
            elif operator == "neq":
                return actual != expected
            elif operator in ("gt", ">"):
                return float(actual) > float(expected)
            elif operator in ("gte", ">="):
                return float(actual) >= float(expected)
            elif operator in ("lt", "<"):
                return float(actual) < float(expected)
            elif operator in ("lte", "<="):
                return float(actual) <= float(expected)
            elif operator == "contains":
                if isinstance(actual, str) and isinstance(expected, str):
                    return expected in actual
                if isinstance(actual, (list, tuple)):
                    return expected in actual
                return str(expected) in str(actual)
            elif operator == "not_contains":
                return not self._default_evaluate("contains", actual, expected)
            elif operator == "matches":
                return bool(re.search(str(expected), str(actual)))
            elif operator == "in":
                if isinstance(expected, (list, tuple)):
                    return actual in expected
                return str(actual) in str(expected)
            elif operator == "not_in":
                return not self._default_evaluate("in", actual, expected)
            else:
                logger.warning(f"[RuleEngine] 不支持的操作符: {operator}")
                return False
        except (ValueError, TypeError) as e:
            logger.warning(f"[RuleEngine] 评估异常: {e} (op={operator}, a={actual}, e={expected})")
            return False

    def _register_builtins(self):
        """注册内置评估函数（可被覆盖）"""
        # 所有字段类型统一用默认评估器（原 6 个专用方法完全相同，已合并）
        for prefix in ("memory", "quality", "system", "event", "schedule", ""):
            self.register(prefix, self._evaluate_default_field)

    @staticmethod
    def _evaluate_default_field(condition: Condition, actual: Any,
                                 event: Dict, ctx: Dict) -> bool:
        """兜底评估"""
        return ConditionEvaluator._static_default_eval(condition.operator, actual, condition.value)

    @staticmethod
    def _static_default_eval(operator: str, actual: Any, expected: Any) -> bool:
        """静态默认评估（供内置注册器复用）"""
        if actual is None:
            return operator == "not_exists"
        if operator == "not_exists":
            return False
        try:
            if operator == "eq":
                return actual == expected
            elif operator == "neq":
                return actual != expected
            elif operator in ("gt", ">"):
                return float(actual) > float(expected)
            elif operator in ("gte", ">="):
                return float(actual) >= float(expected)
            elif operator in ("lt", "<"):
                return float(actual) < float(expected)
            elif operator in ("lte", "<="):
                return float(actual) <= float(expected)
            elif operator == "contains":
                if isinstance(actual, str) and isinstance(expected, str):
                    return expected in actual
                if isinstance(actual, (list, tuple)):
                    return expected in actual
                return str(expected) in str(actual)
            elif operator == "matches":
                return bool(re.search(str(expected), str(actual)))
            elif operator == "in":
                if isinstance(expected, (list, tuple)):
                    return actual in expected
                return str(actual) in str(expected)
            elif operator == "not_in":
                return not ConditionEvaluator._static_default_eval("in", actual, expected)
            elif operator == "exists":
                return True
            return False
        except (ValueError, TypeError):
            return False


# ═══════════════════════════════════════════
# 规则引擎实现
# ═══════════════════════════════════════════

class RuleEngine:
    """
    自动化规则引擎

    职责：
    1. 规则的注册/加载/持久化
    2. 事件 → 条件匹配 → 排序 → 动作执行
    3. 触发历史记录 + 冷却/限流管理
    4. 与 WorkflowEngine 的集成入口

    使用方式：
        engine = RuleEngine()
        engine.load_rules()
        matched = engine.evaluate(event)
        for rule in matched:
            engine.execute(rule, context)
    """

    def __init__(self, rules_path: Optional[str] = None,
                 history_path: Optional[str] = None):
        self._rules: List[Rule] = []
        self._rules_by_id: Dict[str, Rule] = {}
        self._evaluator = ConditionEvaluator()
        self._rules_path = rules_path or RULES_PATH
        self._history_path = history_path or HISTORY_PATH
        self._dirty = False

        # 注册内置规则（默认打开）
        self._register_builtin_rules()

    # ── 规则管理 ──

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules)

    @property
    def enabled_rules(self) -> List[Rule]:
        return [r for r in self._rules if r.enabled]

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self._rules_by_id.get(rule_id)

    def add_rule(self, rule: Rule) -> str:
        """添加规则，返回 rule_id"""
        if not rule.rule_id:
            rule.rule_id = "rule_" + uuid.uuid4().hex[:8]
        if rule.rule_id in self._rules_by_id:
            logger.warning(f"[RuleEngine] 规则 {rule.rule_id} 已存在，覆盖")
            self.remove_rule(rule.rule_id)
        self._rules.append(rule)
        self._rules_by_id[rule.rule_id] = rule
        self._dirty = True
        logger.info(f"[RuleEngine] 添加规则: {rule.name} ({rule.rule_id})")
        return rule.rule_id

    def remove_rule(self, rule_id: str) -> bool:
        """删除规则"""
        if rule_id in self._rules_by_id:
            self._rules = [r for r in self._rules if r.rule_id != rule_id]
            del self._rules_by_id[rule_id]
            self._dirty = True
            logger.info(f"[RuleEngine] 删除规则: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str, enabled: bool = True) -> bool:
        """启用/禁用规则"""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = enabled
            rule.updated_at = datetime.now(BEIJING_TZ).isoformat()
            self._dirty = True
            return True
        return False

    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """更新规则字段（name, description, conditions, actions, priority, cooldown_s 等）"""
        rule = self.get_rule(rule_id)
        if not rule:
            return False
        for k, v in kwargs.items():
            if hasattr(rule, k) and k not in ("rule_id", "created_at", "last_triggered_at", "trigger_count"):
                setattr(rule, k, v)
        rule.updated_at = datetime.now(BEIJING_TZ).isoformat()
        self._dirty = True
        return True

    # ── 持久化 ──

    def save_rules(self, path: Optional[str] = None):
        """保存规则到 JSON 文件"""
        target = path or self._rules_path
        os.makedirs(os.path.dirname(target) if os.path.dirname(target) else ".", exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": datetime.now(BEIJING_TZ).isoformat(),
            "rules": [r.to_dict() for r in self._rules],
        }
        with open(target, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._dirty = False
        logger.info(f"[RuleEngine] 规则已保存 ({len(self._rules)} 条) → {target}")

    def load_rules(self, path: Optional[str] = None) -> int:
        """从 JSON 文件加载规则"""
        target = path or self._rules_path
        if not os.path.exists(target):
            logger.info(f"[RuleEngine] 规则文件不存在: {target}，跳过加载")
            return 0

        try:
            with open(target) as f:
                data = json.load(f)
            loaded = 0
            for r_data in data.get("rules", []):
                try:
                    rule = Rule.from_dict(r_data)
                    self.add_rule(rule)
                    loaded += 1
                except Exception as e:
                    logger.warning(f"[RuleEngine] 规则加载失败: {e} → {r_data.get('name', '?')}")
            logger.info(f"[RuleEngine] 加载 {loaded}/{len(data.get('rules', []))} 条规则")
            self._dirty = False
            return loaded
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[RuleEngine] 规则文件读取失败: {e}")
            return 0

    def flush(self):
        """脏数据自动保存"""
        if self._dirty:
            self.save_rules()

    def get_stats(self) -> Dict[str, Any]:
        """获取规则引擎统计"""
        total = len(self._rules)
        enabled = len(self.enabled_rules)
        total_triggers = sum(r.trigger_count for r in self._rules)
        return {
            "total_rules": total,
            "enabled_rules": enabled,
            "disabled_rules": total - enabled,
            "total_triggers": total_triggers,
            "dirty": self._dirty,
            "rules_path": self._rules_path,
        }

    # ── 事件评估 ──

    def evaluate(self, event: Dict, context: Optional[Dict] = None) -> List[Rule]:
        """
        对事件进行规则匹配

        步骤：
        1. 按优先级降序排列启用的规则
        2. 逐一评估条件
        3. 跳过冷却中 / 限流中的规则
        4. 命中则记录触发历史

        Args:
            event: 事件字典（至少含 type 和 source 字段）
            context: 附加上下文

        Returns:
            命中的规则列表（按优先级排序）
        """
        if not event:
            return []

        matched: List[Rule] = []
        now = datetime.now(BEIJING_TZ)

        # 按优先级排序（高优先先匹配）
        candidates = sorted(self.enabled_rules, key=lambda r: -r.priority)

        for rule in candidates:
            # 冷却检查
            if rule.in_cooldown():
                continue

            # 限流检查
            if rule.rate_limited():
                continue

            # 条件评估（顶层条件默认 AND 组合）
            all_pass = True
            for condition in rule.conditions:
                if not self._evaluator.evaluate(condition, event, context):
                    all_pass = False
                    break

            if all_pass:
                rule.on_trigger()
                matched.append(rule)
                self._record_trigger(rule, event)

        return matched

    def evaluate_one(self, rule: Rule, event: Dict,
                     context: Optional[Dict] = None) -> bool:
        """评估单条规则是否匹配事件"""
        if not rule.enabled:
            return False
        if rule.in_cooldown():
            return False
        for condition in rule.conditions:
            if not self._evaluator.evaluate(condition, event, context):
                return False
        return True

    def _record_trigger(self, rule: Rule, event: Dict):
        """记录触发历史"""
        record = {
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "triggered_at": datetime.now(BEIJING_TZ).isoformat(),
            "event_type": event.get("type", "unknown"),
            "event_source": event.get("source", "unknown"),
        }
        os.makedirs(os.path.dirname(self._history_path) if os.path.dirname(self._history_path) else ".", exist_ok=True)
        with open(self._history_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 控制历史文件大小（保留最近 1000 条）
        self._trim_history(1000)

    def _trim_history(self, max_lines: int = 1000):
        if not os.path.exists(self._history_path):
            return
        with open(self._history_path) as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(self._history_path, "w") as f:
                f.writelines(lines[-max_lines:])

    def get_trigger_history(self, limit: int = 50,
                            rule_id: Optional[str] = None) -> List[Dict]:
        """获取触发历史"""
        if not os.path.exists(self._history_path):
            return []
        records = []
        with open(self._history_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rule_id and rec.get("rule_id") != rule_id:
                        continue
                    records.append(rec)
                except json.JSONDecodeError:
                    continue
        return records[-limit:]

    # ── 动作执行 ──

    def execute(self, rule: Rule, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行规则动作

        对 rule.actions 中的动作按顺序执行

        Args:
            rule: 命中的规则
            context: 执行上下文（事件、环境等）

        Returns:
            { "action": "...", "success": True/False, "results": [...] }
        """
        results = []
        ctx = context or {}

        for action in rule.actions:
            try:
                result = self._execute_action(action, rule, ctx)
                results.append({
                    "action_kind": action.kind,
                    "success": result.get("success", True),
                    "detail": result.get("detail", ""),
                })
            except Exception as e:
                logger.error(f"[RuleEngine] 动作执行失败: {action.kind} → {e}")
                results.append({
                    "action_kind": action.kind,
                    "success": False,
                    "detail": str(e),
                })

        # 触发后自动保存
        self.flush()

        return {
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "actions_count": len(rule.actions),
            "results": results,
        }

    def _execute_action(self, action: RuleAction, rule: Rule,
                        context: Dict) -> Dict[str, Any]:
        """执行单个动作"""
        kind = action.kind
        params = dict(action.params)

        # 模板插值 — 用 {event.field} 替换
        if action.template:
            for k, v in params.items():
                if isinstance(v, str):
                    params[k] = v.format(**context.get("event", {}))

        if kind == "log_only":
            logger.info(f"[RuleEngine] 规则命中（LOG）: {rule.name} | {params}")
            return {"success": True, "detail": "logged"}

        elif kind == "send_notification":
            msg = params.get("message", f"⚡ 规则触发: {rule.name}")
            channel = params.get("channel", "last")
            # 留给上层调用方实际发送
            logger.info(f"[RuleEngine] 通知推送: [{channel}] {msg}")
            return {
                "success": True,
                "detail": f"notification queued: {msg[:80]}",
                "pending_send": {
                    "channel": channel,
                    "message": msg,
                }
            }

        elif kind == "create_task":
            task_name = params.get("task_name", f"任务: {rule.name}")
            detail = params.get("detail", "")
            logger.info(f"[RuleEngine] 创建任务: {task_name}")
            return {
                "success": True,
                "detail": f"task queued: {task_name}",
                "pending_task": {
                    "name": task_name,
                    "detail": detail,
                    "source_rule": rule.rule_id,
                }
            }

        elif kind == "build_dag":
            goal = params.get("goal", f"执行规则: {rule.name}")
            logger.info(f"[RuleEngine] 构建 DAG 工作流: {goal}")
            return {
                "success": True,
                "detail": f"dag_build queued: {goal[:80]}",
                "pending_dag": {
                    "goal": goal,
                    "source_rule": rule.rule_id,
                    "params": params,
                }
            }

        elif kind == "run_skill":
            skill_name = params.get("skill_name", "")
            logger.info(f"[RuleEngine] 执行技能: {skill_name}")
            return {
                "success": True,
                "detail": f"skill_exec queued: {skill_name}",
                "pending_skill": {
                    "skill_name": skill_name,
                    "params": params.get("params", {}),
                }
            }

        elif kind == "memory_write":
            content = params.get("content", f"规则触发: {rule.name}")
            tags = params.get("tags", ["rule_triggered"])
            logger.info(f"[RuleEngine] 记忆写入: {content[:60]}")
            return {
                "success": True,
                "detail": f"memory_write queued",
                "pending_memory": {
                    "content": content,
                    "tags": tags,
                }
            }

        elif kind == "update_rules":
            target_rule_id = params.get("target_rule_id", "")
            changes = params.get("changes", {})
            if target_rule_id:
                self.update_rule(target_rule_id, **changes)
                logger.info(f"[RuleEngine] 动态调整规则: {target_rule_id}")
            return {"success": True, "detail": f"rules updated: {target_rule_id}"}

        else:
            logger.warning(f"[RuleEngine] 未支持的动作类型: {kind}")
            return {"success": False, "detail": f"unsupported action: {kind}"}

    # ── 内置规则 ──

    def _register_builtin_rules(self):
        """注册内置默认规则（未激活，需用户确认启用）"""
        self._builtin_rules = self._default_rules()

    @staticmethod
    def _default_rules() -> List[Rule]:
        """
        内置默认规则模板

        这些规则默认存在规则文件中，但 enabled=False，
        用户可根据需要开启。
        """
        now = datetime.now(BEIJING_TZ).isoformat()
        return [
            Rule(
                rule_id="builtin_memory_task",
                name="记忆中新项目任务自动创建清单",
                description="当记忆系统中新增关于某项目的条目时，自动创建对应的任务清单",
                enabled=False,
                priority=50,
                cooldown_s=600,
                tags=["memory", "auto_task"],
                source="builtin",
                conditions=[
                    Condition(
                        field="event.type",
                        operator="eq",
                        value="memory.saved"
                    ),
                    Condition(
                        field="event.metadata.tags",
                        operator="contains",
                        value="project"
                    ),
                ],
                actions=[
                    RuleAction(
                        kind="create_task",
                        params={
                            "task_name": "跟进项目: {event.metadata.summary}",
                            "priority": "normal",
                        }
                    ),
                    RuleAction(
                        kind="log_only",
                        params={"message": "记忆触发项目任务创建"},
                    ),
                ],
                created_at=now,
            ),
            Rule(
                rule_id="builtin_quality_degraded",
                name="质量评分持续下降告警",
                description="当引擎质量评分连续下降时推送告警",
                enabled=False,
                priority=80,
                cooldown_s=1800,
                tags=["quality", "alert"],
                source="builtin",
                conditions=[
                    Condition(
                        field="event.type",
                        operator="eq",
                        value="quality.score_recorded"
                    ),
                    Condition(
                        field="quality.avg_score",
                        operator="lt",
                        value=0.4
                    ),
                ],
                actions=[
                    RuleAction(
                        kind="send_notification",
                        params={
                            "message": "⚠️ 引擎质量评分偏低，建议检查",
                            "channel": "last",
                        }
                    ),
                ],
                created_at=now,
            ),
            Rule(
                rule_id="builtin_memory_retrieval_fail",
                name="记忆检索失败率过高告警",
                description="当记忆检索失败率超过阈值时推送告警",
                enabled=False,
                priority=70,
                cooldown_s=3600,
                tags=["memory", "alert"],
                source="builtin",
                conditions=[
                    Condition(
                        field="event.type",
                        operator="eq",
                        value="memory.retrieval_batch"
                    ),
                    Condition(
                        field="memory.retrieval_rate",
                        operator="lt",
                        value=0.6
                    ),
                ],
                actions=[
                    RuleAction(
                        kind="send_notification",
                        params={
                            "message": "⚠️ 记忆检索成功率偏低（{event.metadata.rate}），建议执行记忆维护",
                            "channel": "last",
                        }
                    ),
                ],
                created_at=now,
            ),
            Rule(
                rule_id="builtin_system_health",
                name="系统健康度低于阈值推送",
                description="定时巡检发现健康评分低于60分时推送",
                enabled=False,
                priority=90,
                cooldown_s=3600,
                tags=["system", "health", "alert"],
                source="builtin",
                conditions=[
                    Condition(
                        field="event.type",
                        operator="eq",
                        value="health.score_updated"
                    ),
                    Condition(
                        field="system.health_score",
                        operator="lt",
                        value=60
                    ),
                ],
                actions=[
                    RuleAction(
                        kind="send_notification",
                        params={
                            "message": "🚨 系统健康评分偏低（{event.metadata.score}），建议检查",
                            "channel": "last",
                        }
                    ),
                ],
                created_at=now,
            ),
            Rule(
                rule_id="builtin_response_slow",
                name="引擎响应时间异常告警",
                description="当引擎平均响应时间超过阈值时告警",
                enabled=False,
                priority=60,
                cooldown_s=1800,
                tags=["performance", "alert"],
                source="builtin",
                conditions=[
                    Condition(
                        field="event.type",
                        operator="eq",
                        value="system.response_time_report"
                    ),
                    Condition(
                        field="system.response_time_ms",
                        operator="gt",
                        value=15000
                    ),
                ],
                actions=[
                    RuleAction(
                        kind="send_notification",
                        params={
                            "message": "⚠️ 引擎响应变慢（{event.metadata.avg_ms}ms），建议关注",
                            "channel": "last",
                        }
                    ),
                ],
                created_at=now,
            ),
        ]

    def load_builtins(self, enable: bool = False) -> int:
        """
        加载内置规则到引擎中

        Args:
            enable: 是否默认启用

        Returns:
            加载的内置规则数
        """
        count = 0
        for rule in self._builtin_rules:
            if rule.rule_id not in self._rules_by_id:
                if enable:
                    rule.enabled = True
                self.add_rule(rule)
                count += 1
        return count

    # ── 集成入口 ──

    def on_event(self, event: Dict, context: Optional[Dict] = None) -> List[Dict]:
        """
        统一事件入口

        规则引擎对外暴露的唯一入口。外部模块（记忆/质量/巡检等）
        通过此方法注入事件，引擎自动匹配并执行规则。

        Args:
            event: 事件字典
                {
                    "type": "memory.saved",        # 事件类型
                    "source": "memory",              # 事件来源
                    "metadata": { ... },             # 事件元数据
                    "timestamp": "2026-05-18T..."    # 时间戳（可选）
                }
            context: 执行上下文

        Returns:
            执行结果列表
        """
        if not event.get("type"):
            logger.warning(f"[RuleEngine] 事件缺少 type 字段: {event}")
            return []

        if not event.get("timestamp"):
            event["timestamp"] = datetime.now(BEIJING_TZ).isoformat()

        # 匹配规则
        matched = self.evaluate(event, context)

        if not matched:
            return []

        # 执行规则
        results = []
        for rule in matched:
            result = self.execute(rule, {**(context or {}), "event": event})
            results.append(result)

        # 自动保存
        self.flush()

        return results


# ═══════════════════════════════════════════
# 内置事件推送封装
# ═══════════════════════════════════════════

class RuleEventBuilder:
    """事件构建辅助——给记忆/质量/巡检等模块快速构建标准事件"""

    @staticmethod
    def memory_saved(summary: str, tags: List[str],
                     metadata: Optional[Dict] = None) -> Dict:
        return {
            "type": "memory.saved",
            "source": "memory",
            "metadata": {
                "summary": summary,
                "tags": tags,
                **(metadata or {}),
            },
        }

    @staticmethod
    def memory_retrieval_batch(rate: float, total: int,
                               failed: int) -> Dict:
        return {
            "type": "memory.retrieval_batch",
            "source": "memory",
            "metadata": {
                "rate": rate,
                "total": total,
                "failed": failed,
            },
            "memory.retrieval_rate": rate,
        }

    @staticmethod
    def quality_score_recorded(engine: str, dimension: str,
                                score: float) -> Dict:
        return {
            "type": "quality.score_recorded",
            "source": "quality",
            "metadata": {
                "engine": engine,
                "dimension": dimension,
                "score": score,
            },
            "quality.avg_score": score,
        }

    @staticmethod
    def health_score_updated(score: float, level: str,
                             issues: int) -> Dict:
        return {
            "type": "health.score_updated",
            "source": "schedule",
            "metadata": {
                "score": score,
                "level": level,
                "issues": issues,
            },
            "system.health_score": score,
        }

    @staticmethod
    def response_time_report(avg_ms: float, max_ms: float,
                             sample_count: int) -> Dict:
        return {
            "type": "system.response_time_report",
            "source": "system",
            "metadata": {
                "avg_ms": avg_ms,
                "max_ms": max_ms,
                "sample_count": sample_count,
            },
            "system.response_time_ms": avg_ms,
        }


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

    print("=" * 60)
    print("RuleEngine v1.0 — 快速验证")
    print("=" * 60)

    engine = RuleEngine()

    # 测试1: 加载内置规则
    engine.load_builtins(enable=False)
    stats = engine.get_stats()
    print(f"\n[测试1] 内置规则加载: {stats['total_rules']} 条（默认禁用）")

    # 测试2: 添加自定义规则
    custom_rule = Rule(
        rule_id="test_rule_001",
        name="测试规则",
        description="测试条件评估",
        enabled=True,
        priority=100,
        conditions=[
            Condition.simple("event.type", "eq", "test.event"),
            Condition.simple("event.metadata.value", "gt", 50),
        ],
        actions=[
            RuleAction(kind="log_only", params={"message": "测试规则命中"}),
        ],
    )
    engine.add_rule(custom_rule)
    print(f"\n[测试2] 自定义规则添加: {custom_rule.rule_id}")

    # 测试3: 事件匹配
    event = {
        "type": "test.event",
        "source": "user",
        "metadata": {"value": 80, "label": "test"},
    }
    matched = engine.evaluate(event)
    print(f"\n[测试3] 事件匹配: {len(matched)} 条命中 → {[r.name for r in matched]}")

    # 测试4: 不匹配的事件
    event_no_match = {
        "type": "test.event",
        "source": "user",
        "metadata": {"value": 10, "label": "low"},
    }
    matched2 = engine.evaluate(event_no_match)
    print(f"[测试4] 不匹配事件: {len(matched2)} 条命中")

    # 测试5: 复合条件
    and_cond = Condition.composite(
        "and",
        Condition.simple("event.type", "eq", "complex.event"),
        Condition.composite(
            "or",
            Condition.simple("event.metadata.a", "gt", 10),
            Condition.simple("event.metadata.b", "lt", 5),
        ),
    )
    comp_rule = Rule(
        rule_id="test_complex",
        name="复合条件测试",
        enabled=True,
        conditions=[and_cond],
        actions=[RuleAction(kind="log_only")],
    )
    engine.add_rule(comp_rule)

    complex_event = {
        "type": "complex.event",
        "metadata": {"a": 15, "b": 3},
    }
    matched3 = engine.evaluate(complex_event)
    print(f"\n[测试5] 复合条件: {len(matched3)} 条命中 → {[r.name for r in matched3]}")

    # 测试6: 执行动作
    if matched:
        result = engine.execute(matched[0], {"event": event})
        print(f"\n[测试6] 动作执行: {result['rule_name']} → {result['results']}")

    # 测试7: 序列化/反序列化
    engine.save_rules("/tmp/test_rules.json")
    engine2 = RuleEngine(rules_path="/tmp/test_rules.json")
    loaded = engine2.load_rules("/tmp/test_rules.json")
    print(f"\n[测试7] 持久化: 保存→加载 {loaded} 条规则")

    print(f"\n{'=' * 60}")
    print("✅ 规则引擎验证完成")
