"""
Crusheart Agent OS — UserDynamicPortraitEngine v2.0
用户动态画像引擎：从对话中实时收集并更新用户的偏好/决策/风险/习惯

四大子模型：
  PreferencePortrait  — 沟通风格偏好（直接/详细/列表/口语）
  DecisionPortrait    — 决策模式（是否倾向接受建议、偏好方案数）
  RiskPortrait        — 风险容忍度（确认频率、谨慎程度）
  HabitPortrait       — 行为节律（活跃时段、常见任务类型、平均消息长度）

新增 v2.0：
  信号质量门 — 同类型信号重复≥5次才向下游分发
  下游分发 — 自进化引擎（写MEMORY.md/SOUL.md/USER.md）+ 参数自调优引擎（改config）

使用方式：
  from core.engines.memory.user_dynamic_portrait import get_portrait
  portrait = get_portrait()
  portrait.update_from_message(message_text)    # 每次用户消息后更新
  summary = portrait.get_context_summary()      # 获取当前用户模型摘要
  pending = portrait.get_pending_signals()      # 获取待分发的合格信号
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from collections import Counter

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
PORTRAIT_FILE = os.path.join(WORKSPACE, ".state", "user_portrait.json")
os.makedirs(os.path.dirname(PORTRAIT_FILE), exist_ok=True)

# ================================================================
# 信号质量门配置
# ================================================================
SIGNAL_GATE_THRESHOLD = 5  # 同类型信号重复≥5次才通过质量门

# ================================================================
# 信号 → 下游目标映射
# ================================================================
SIGNAL_TARGET_MAP = {
    "preference.direct":    {"target": "self_evolution", "file": "SOUL.md",
                             "content_template": "对话风格偏好：用户{user}偏好直接简洁的回答方式，无需过多铺垫。"},
    "preference.detailed":  {"target": "self_evolution", "file": "SOUL.md",
                             "content_template": "对话风格偏好：用户{user}偏好详细展开的回答方式，希望解释清楚。"},
    "preference.list":      {"target": "self_evolution", "file": "SOUL.md",
                             "content_template": "输出格式偏好：用户{user}喜欢分条列出的格式，便于阅读。"},
    "decision.prefer_options":  {"target": "self_evolution", "file": "USER.md",
                                 "content_template": "决策偏好：用户{user}倾向于在决策时查看多个方案对比。"},
    "risk.low":             {"target": "self_evolution", "file": "SOUL.md",
                             "content_template": "风险偏好：用户{user}在操作前倾向先确认，谨慎型决策风格。"},
    "risk.high":            {"target": "self_evolution", "file": "SOUL.md",
                             "content_template": "风险偏好：用户{user}倾向直接执行，减少确认环节。"},
    "habit.peak_hour":      {"target": "self_evolution", "file": "USER.md",
                             "content_template": "活跃时段：用户{user}每日活跃高峰在{peak_hour}时左右。"},
    "habit.task_type":      {"target": "self_evolution", "file": "USER.md",
                             "content_template": "常见任务类型：用户{user}常做{task_types}类任务。"},
}

# 画像信号 → 参数调优映射（直接发调优信号）
TUNING_SIGNAL_MAP = {
    "preference.verbosity.short":  {"engine": "dual_mode", "field": "text_length_threshold",
                                    "suggested": 80, "reason": "用户偏好简洁回答，降低文本长度阈值减少Agent模式误切"},
    "preference.verbosity.long":   {"engine": "dual_mode", "field": "text_length_threshold",
                                    "suggested": 160, "reason": "用户偏好详细回答，提高文本长度阈值"},
    "risk.low":                    {"engine": "mutex", "field": "task_timeout_seconds",
                                    "suggested": 120, "reason": "谨慎型用户，减少任务超时时间降低等待"},
    "risk.high":                   {"engine": "mutex", "field": "task_timeout_seconds",
                                    "suggested": 300, "reason": "大胆型用户，提高任务超时时间容纳复杂操作"},
    "preference.direct":           {"engine": "dual_mode", "field": "fast_keyword_weight",
                                    "suggested": 15, "reason": "用户偏好直接快速回答，提高快速模式权重"},
    "preference.detailed":         {"engine": "dual_mode", "field": "agent_keyword_weight",
                                    "suggested": 12, "reason": "用户偏好详细回答，提高Agent模式权重"},
}


def _now_str() -> str:
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _now_hour() -> int:
    return datetime.now(BEIJING_TZ).hour


# ================================================================
# 子模型 1: PreferencePortrait — 沟通风格偏好
# ================================================================
class PreferencePortrait:
    """
    从用户消息信号中推断沟通风格偏好。
    追踪：回复风格偏好（直接/详细）、是否喜欢列表、语言风格。
    新增v2.0：计数器追踪每次信号重复次数，用于质量门。
    """
    DEFAULTS = {
        "style": "balanced",
        "format": "prose",
        "language": "zh_informal",
        "verbosity": "medium",
        "signal_count": 0,
        # 信号计数器（用于质量门）
        "signal_counter": {
            "direct": 0,
            "detailed": 0,
            "list": 0,
        },
    }

    DIRECT_SIGNALS = ["直接", "简单说", "快点", "快速", "别废话", "直接说", "简洁", "短一点", "简短"]
    DETAIL_SIGNALS = ["详细", "展开", "说清楚", "解释一下", "深入", "仔细", "完整", "全面", "详细说明"]
    LIST_SIGNALS = ["列出", "列一下", "列举", "分条", "逐条", "一条一条", "清单"]

    def infer(self, signals: List[str]) -> dict:
        pref = dict(self.DEFAULTS)
        text = " ".join(signals)
        pref["signal_count"] = len(signals)

        direct_hits = sum(1 for s in self.DIRECT_SIGNALS if s in text)
        detail_hits = sum(1 for s in self.DETAIL_SIGNALS if s in text)
        list_hits = sum(1 for s in self.LIST_SIGNALS if s in text)

        # 更新信号计数器
        if direct_hits > detail_hits:
            pref["style"] = "direct"
            pref["verbosity"] = "short"
            pref["signal_counter"]["direct"] = pref["signal_counter"].get("direct", 0) + 1
        elif detail_hits > direct_hits:
            pref["style"] = "detailed"
            pref["verbosity"] = "long"
            pref["signal_counter"]["detailed"] = pref["signal_counter"].get("detailed", 0) + 1

        if list_hits >= 2:
            pref["format"] = "list"
            pref["signal_counter"]["list"] = pref["signal_counter"].get("list", 0) + 1

        avg_len = sum(len(s) for s in signals) / max(len(signals), 1)
        if avg_len < 15:
            pref["verbosity"] = "short"
        elif avg_len > 80:
            pref["verbosity"] = "long"

        return pref

    def merge(self, existing: dict, new_signals: List[str]) -> dict:
        """增量更新：新信号融入时保持平滑"""
        fresh = self.infer(new_signals)
        merged = dict(existing)
        count = existing.get("signal_count", 0) + len(new_signals)
        merged["signal_count"] = count

        # 累计信号计数器
        counter = dict(existing.get("signal_counter", {}))
        for k, v in fresh.get("signal_counter", {}).items():
            counter[k] = counter.get(k, 0) + v
        merged["signal_counter"] = counter

        if fresh["style"] != "balanced":
            merged["style"] = fresh["style"]
        if fresh["format"] != "prose":
            merged["format"] = fresh["format"]
        if fresh["verbosity"] != "medium":
            merged["verbosity"] = fresh["verbosity"]

        return merged


# ================================================================
# 子模型 2: DecisionPortrait — 决策风格建模
# ================================================================
class DecisionPortrait:
    """
    建模用户的决策偏好：
    - prefer_options: 喜欢看多个方案 vs 直接给结论
    - accept_rate: 接受AI建议的比例
    - iteration_depth: 平均迭代几轮才定稿
    新增v2.0：信号计数器。
    """
    DEFAULTS = {
        "prefer_options": False,
        "accept_rate": 0.7,
        "iteration_depth": 1.5,
        "decision_count": 0,
        "override_count": 0,
        "signal_counter": {
            "prefer_options": 0,
        },
    }

    OPTIONS_SIGNALS = ["几个方案", "多个选项", "有哪些选择", "给我选项", "几种方法", "对比一下", "比较"]
    OVERRIDE_SIGNALS = ["不对", "不是这样", "你理解错了", "换一个", "重新来", "不用这个", "放弃", "算了换"]

    def model(self, decisions: List[dict]) -> dict:
        result = dict(self.DEFAULTS)
        if not decisions:
            return result
        result["decision_count"] = len(decisions)
        texts = [str(d) for d in decisions]
        combined = " ".join(texts)
        opt_hits = sum(1 for s in self.OPTIONS_SIGNALS if s in combined)
        if opt_hits >= 2:
            result["prefer_options"] = True
            result["signal_counter"]["prefer_options"] = result["signal_counter"].get("prefer_options", 0) + 1
        override_hits = sum(1 for s in self.OVERRIDE_SIGNALS if s in combined)
        result["override_count"] = override_hits
        if len(decisions) > 0:
            rate = max(0.2, min(0.95, 1.0 - (override_hits / len(decisions))))
            result["accept_rate"] = round(rate, 2)
        return result

    def update(self, existing: dict, message_text: str, user_accepted: bool = True) -> dict:
        merged = dict(existing)
        merged["decision_count"] = existing.get("decision_count", 0) + 1

        counter = dict(existing.get("signal_counter", {}))
        if any(s in message_text for s in self.OPTIONS_SIGNALS):
            merged["prefer_options"] = True
            counter["prefer_options"] = counter.get("prefer_options", 0) + 1
        merged["signal_counter"] = counter

        old_rate = existing.get("accept_rate", 0.7)
        new_signal = 1.0 if user_accepted else 0.0
        count = max(1, existing.get("decision_count", 1))
        alpha = min(0.3, 1.0 / count)
        merged["accept_rate"] = round(old_rate * (1 - alpha) + new_signal * alpha, 2)

        if any(s in message_text for s in self.OVERRIDE_SIGNALS):
            merged["override_count"] = existing.get("override_count", 0) + 1

        return merged


# ================================================================
# 子模型 3: RiskPortrait — 风险容忍度校准
# ================================================================
class RiskPortrait:
    """
    校准用户的风险容忍度。
    新增v2.0：信号计数器。
    """
    DEFAULTS = {
        "risk_tolerance": "medium",
        "caution_score": 0.5,
        "confirm_tendency": "ask_first",
        "feedback_count": 0,
        "signal_counter": {
            "risk_high": 0,
            "risk_low": 0,
        },
    }

    HIGH_RISK_SIGNALS = ["先问我", "别乱动", "确认一下", "小心", "备份", "别删", "你确定吗", "万一"]
    LOW_RISK_SIGNALS = ["直接做", "不用问", "别废话", "快点弄", "你决定", "随便", "无所谓", "按你说的"]

    def calibrate(self, feedback: List[dict]) -> dict:
        result = dict(self.DEFAULTS)
        if not feedback:
            return result
        result["feedback_count"] = len(feedback)
        texts = [str(f) for f in feedback]
        combined = " ".join(texts)
        high_hits = sum(1 for s in self.HIGH_RISK_SIGNALS if s in combined)
        low_hits = sum(1 for s in self.LOW_RISK_SIGNALS if s in combined)
        total = high_hits + low_hits
        if total > 0:
            caution = high_hits / total
            result["caution_score"] = round(caution, 2)
            if caution > 0.65:
                result["risk_tolerance"] = "low"
            elif caution < 0.35:
                result["risk_tolerance"] = "high"
        return result

    def update(self, existing: dict, message_text: str) -> dict:
        merged = dict(existing)
        merged["feedback_count"] = existing.get("feedback_count", 0) + 1

        high_hit = any(s in message_text for s in self.HIGH_RISK_SIGNALS)
        low_hit = any(s in message_text for s in self.LOW_RISK_SIGNALS)

        counter = dict(existing.get("signal_counter", {}))
        if high_hit:
            counter["risk_low"] = counter.get("risk_low", 0) + 1
        if low_hit:
            counter["risk_high"] = counter.get("risk_high", 0) + 1
        merged["signal_counter"] = counter

        if not high_hit and not low_hit:
            return merged

        old_score = existing.get("caution_score", 0.5)
        count = max(1, existing.get("feedback_count", 1))
        alpha = min(0.25, 1.0 / count)
        if high_hit:
            new_score = old_score * (1 - alpha) + 1.0 * alpha
        else:
            new_score = old_score * (1 - alpha) + 0.0 * alpha
        new_score = round(max(0.0, min(1.0, new_score)), 2)
        merged["caution_score"] = new_score
        if new_score > 0.65:
            merged["risk_tolerance"] = "low"
            merged["confirm_tendency"] = "ask_first"
        elif new_score < 0.35:
            merged["risk_tolerance"] = "high"
            merged["confirm_tendency"] = "just_do_it"
        else:
            merged["risk_tolerance"] = "medium"

        return merged


# ================================================================
# 子模型 4: HabitPortrait — 行为节律提取
# ================================================================
class HabitPortrait:
    """
    提取用户行为节律。
    新增v2.0：信号计数器。
    """
    DEFAULTS = {
        "peak_hour": -1,
        "active_hours": {},
        "common_task_types": [],
        "avg_message_len": 0,
        "total_messages": 0,
        "iteration_speed": "normal",
        "signal_counter": {
            "task_type": {},  # {task_type: count}
        },
    }

    TASK_TYPE_SIGNALS = {
        "coding":    ["代码", "编程", "写个", "实现", "函数", "bug", "报错", "Python", "脚本"],
        "writing":   ["写文章", "写作", "文案", "报告", "文档", "总结", "写一篇"],
        "search":    ["查一下", "搜索", "找找", "查查", "最新", "是什么", "有没有"],
        "analysis":  ["分析", "对比", "比较", "研究", "深入", "评估", "判断"],
        "system":    ["配置", "安装", "插件", "技能", "引擎", "重启", "cron", "系统"],
        "chat":      ["聊聊", "说说", "你觉得", "怎么看", "感觉", "闲聊"],
    }

    def extract(self, events: List[dict]) -> dict:
        result = dict(self.DEFAULTS)
        if not events:
            return result
        result["total_messages"] = len(events)
        hour_counts: Counter = Counter()
        total_len = 0
        task_type_hits: Counter = Counter()
        for evt in events:
            text = str(evt.get("text", ""))
            total_len += len(text)
            hour = evt.get("hour", -1)
            if 0 <= hour < 24:
                hour_counts[hour] += 1
            for task_type, signals in self.TASK_TYPE_SIGNALS.items():
                if any(s in text for s in signals):
                    task_type_hits[task_type] += 1
        if hour_counts:
            result["active_hours"] = {str(h): c for h, c in hour_counts.items()}
            result["peak_hour"] = hour_counts.most_common(1)[0][0]
        result["avg_message_len"] = int(total_len / max(len(events), 1))
        result["common_task_types"] = [t for t, _ in task_type_hits.most_common(3)]
        if len(events) >= 5:
            result["iteration_speed"] = "fast"
        elif len(events) >= 2:
            result["iteration_speed"] = "normal"
        return result

    def update(self, existing: dict, message_text: str, current_hour: Optional[int] = None) -> dict:
        merged = dict(existing)
        merged["total_messages"] = existing.get("total_messages", 0) + 1
        old_avg = existing.get("avg_message_len", 0)
        count = max(1, existing.get("total_messages", 1))
        merged["avg_message_len"] = int((old_avg * (count - 1) + len(message_text)) / count)

        hour = current_hour if current_hour is not None else _now_hour()
        active_hours = dict(existing.get("active_hours", {}))
        hour_key = str(hour)
        active_hours[hour_key] = active_hours.get(hour_key, 0) + 1
        merged["active_hours"] = active_hours
        if active_hours:
            merged["peak_hour"] = int(max(active_hours, key=lambda h: active_hours[h]))

        existing_types = list(existing.get("common_task_types", []))
        task_counter = dict(existing.get("signal_counter", {}).get("task_type", {}))
        for task_type, signals in self.TASK_TYPE_SIGNALS.items():
            if any(s in message_text for s in signals):
                task_counter[task_type] = task_counter.get(task_type, 0) + 1
                if task_type not in existing_types:
                    existing_types.insert(0, task_type)
                    if len(existing_types) > 5:
                        existing_types = existing_types[:5]
                break
        merged["signal_counter"] = {"task_type": task_counter}
        merged["common_task_types"] = existing_types
        return merged


# ================================================================
# 子模型 5: IdentityDriftGuard — 防画像越权/漂移
# ================================================================
class IdentityDriftGuard:
    """防止画像越权或产生有害漂移"""
    # 致命违规（直接尝试冒充用户/覆盖安全策略）→ 重置整个画像
    CRITICAL_PATTERNS = [
        "act as user", "i am the user", "impersonate", "override_safety",
    ]
    # 警告违规（提及但并非真正尝试绕过）→ 仅记录不重置
    WARNING_PATTERNS = [
        "bypass_confirmation", "skip_approval",
    ]

    def check(self, portrait_data: dict) -> dict:
        text = json.dumps(portrait_data, ensure_ascii=False).lower()
        critical_hits = [p for p in self.CRITICAL_PATTERNS if p in text]
        warning_hits = [p for p in self.WARNING_PATTERNS if p in text]

        if critical_hits:
            return {
                "status": "drift_detected",
                "violations": critical_hits,
                "severity": "critical",
                "portrait_is_preference_model_only": True,
                "checked_at": _now_str(),
            }
        if warning_hits:
            return {
                "status": "warning",
                "violations": warning_hits,
                "severity": "warning",
                "portrait_is_preference_model_only": True,
                "checked_at": _now_str(),
            }
        return {
            "status": "safe",
            "violations": [],
            "severity": "safe",
            "portrait_is_preference_model_only": True,
            "checked_at": _now_str(),
        }


# ================================================================
# 信号质量门 & 分发逻辑
# ================================================================
class SignalGate:
    """
    信号质量门 v2.0 新增
    检查各信号计数器是否≥阈值，产出待分发信号包。
    """

    @staticmethod
    def check_portrait(data: dict) -> List[dict]:
        """遍历画像数据，找出通过质量门的信号"""
        ready_signals = []
        pref = data.get("preference", {})
        dec = data.get("decision", {})
        risk = data.get("risk", {})
        habit = data.get("habit", {})

        # 偏好信号
        pref_counter = pref.get("signal_counter", {})
        if pref_counter.get("direct", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "preference.direct",
                "confidence": min(1.0, pref_counter["direct"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": pref_counter["direct"],
                "value": pref.get("style"),
            })
        if pref_counter.get("detailed", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "preference.detailed",
                "confidence": min(1.0, pref_counter["detailed"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": pref_counter["detailed"],
                "value": pref.get("style"),
            })
        if pref_counter.get("list", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "preference.list",
                "confidence": min(1.0, pref_counter["list"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": pref_counter["list"],
                "value": pref.get("format"),
            })

        # 决策信号
        dec_counter = dec.get("signal_counter", {})
        if dec_counter.get("prefer_options", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "decision.prefer_options",
                "confidence": min(1.0, dec_counter["prefer_options"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": dec_counter["prefer_options"],
                "value": True,
            })

        # 风险信号
        risk_counter = risk.get("signal_counter", {})
        if risk.get("risk_tolerance") == "low" and risk_counter.get("risk_low", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "risk.low",
                "confidence": min(1.0, risk_counter["risk_low"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": risk_counter["risk_low"],
                "value": "low",
            })
        if risk.get("risk_tolerance") == "high" and risk_counter.get("risk_high", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "risk.high",
                "confidence": min(1.0, risk_counter["risk_high"] / (SIGNAL_GATE_THRESHOLD + 5)),
                "count": risk_counter["risk_high"],
                "value": "high",
            })

        # 习惯信号
        habit_counter = habit.get("signal_counter", {}).get("task_type", {})
        top_tasks = habit.get("common_task_types", [])
        for tt in top_tasks:
            ct = habit_counter.get(tt, 0)
            if ct >= SIGNAL_GATE_THRESHOLD:
                ready_signals.append({
                    "signal_type": "habit.task_type",
                    "subtype": tt,
                    "confidence": min(1.0, ct / (SIGNAL_GATE_THRESHOLD + 5)),
                    "count": ct,
                    "value": tt,
                })

        peak = habit.get("peak_hour", -1)
        if peak >= 0 and habit.get("total_messages", 0) >= SIGNAL_GATE_THRESHOLD:
            ready_signals.append({
                "signal_type": "habit.peak_hour",
                "confidence": 0.7,
                "count": habit.get("total_messages", 0),
                "value": peak,
            })

        return ready_signals

    @staticmethod
    def build_dispatch_pack(signal: dict, portrait_data: dict) -> dict:
        """将信号包装为下游可消费的分发包"""
        signal_type = signal["signal_type"]
        pack = {
            "source": "user_dynamic_portrait",
            "signal_type": signal_type,
            "confidence": signal.get("confidence", 0.7),
            "count": signal.get("count", 0),
            "value": signal.get("value"),
            "generated_at": _now_str(),
        }

        # 填充下游目标
        if signal_type in SIGNAL_TARGET_MAP:
            tmpl = SIGNAL_TARGET_MAP[signal_type]
            pack["target"] = tmpl["target"]
            pack["target_file"] = tmpl["file"]
            # 填充模板
            habit = portrait_data.get("habit", {})
            content = tmpl["content_template"].format(
                user="用户",
                peak_hour=signal.get("value", "?") if signal_type == "habit.peak_hour" else "?",
                task_types=signal.get("value", "?") if signal_type == "habit.task_type" else "?",
            )
            pack["content"] = content

        # 填充调优信号
        if signal_type in TUNING_SIGNAL_MAP:
            ts = TUNING_SIGNAL_MAP[signal_type]
            pack["tuning_target"] = {
                "engine": ts["engine"],
                "field": ts["field"],
                "suggested_value": ts["suggested"],
                "reason": ts["reason"],
            }

        return pack


# ================================================================
# 主类: UserDynamicPortraitEngine — 统一入口
# ================================================================
class UserDynamicPortraitEngine:
    """
    用户动态画像引擎 v2.0

    使用方式：
        portrait = UserDynamicPortraitEngine()
        portrait.update_from_message("帮我快速搞一个脚本")  # 每次用户消息时调用
        summary = portrait.get_context_summary()            # 获取摘要注入session
        pending = portrait.get_pending_signals()            # 获取待分发的合格信号
        portrait.save()                                     # 持久化
    """

    def __init__(self):
        self.preference = PreferencePortrait()
        self.decision = DecisionPortrait()
        self.risk = RiskPortrait()
        self.habit = HabitPortrait()
        self.guard = IdentityDriftGuard()
        self.signal_gate = SignalGate()
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(PORTRAIT_FILE):
            try:
                with open(PORTRAIT_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_data()

    def _default_data(self) -> dict:
        return {
            "version": "2.0",
            "created_at": _now_str(),
            "updated_at": _now_str(),
            "preference": dict(PreferencePortrait.DEFAULTS),
            "decision": dict(DecisionPortrait.DEFAULTS),
            "risk": dict(RiskPortrait.DEFAULTS),
            "habit": dict(HabitPortrait.DEFAULTS),
            "message_count": 0,
            # v2.0: 记录已分发的信号（避免重复分发）
            "dispatched_signals": [],
            "privacy": "local_only",
        }

    def save(self):
        self._data["updated_at"] = _now_str()
        os.makedirs(os.path.dirname(PORTRAIT_FILE), exist_ok=True)
        with open(PORTRAIT_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def update_from_message(self, message_text: str, user_accepted: bool = True) -> dict:
        if not message_text:
            return self._data

        self._data["message_count"] = self._data.get("message_count", 0) + 1

        self._data["preference"] = self.preference.merge(
            self._data.get("preference", {}), [message_text]
        )
        self._data["decision"] = self.decision.update(
            self._data.get("decision", {}), message_text, user_accepted
        )
        self._data["risk"] = self.risk.update(
            self._data.get("risk", {}), message_text
        )
        self._data["habit"] = self.habit.update(
            self._data.get("habit", {}), message_text, _now_hour()
        )

        guard_result = self.guard.check(self._data)
        # 仅在 critical 级违规时重置整个画像（warning 级仅记录不重置）
        if guard_result.get("severity") == "critical":
            import logging
            logging.warning(f"[UserDynamicPortrait] 检测到 critical 级画像漂移: {guard_result['violations']}，重置为默认")
            self._data = self._default_data()

        self.save()
        return self._data

    def get_pending_signals(self) -> List[dict]:
        """
        获取本次通过质量门且尚未分发的信号包。
        每次调用后，已返回的信号会被标记为"已分发"。
        """
        raw_signals = self.signal_gate.check_portrait(self._data)
        dispatched = set(self._data.get("dispatched_signals", []))

        pending = []
        for sig in raw_signals:
            sig_id = f"{sig['signal_type']}"
            if "subtype" in sig:
                sig_id += f".{sig['subtype']}"
            if sig_id not in dispatched:
                pack = self.signal_gate.build_dispatch_pack(sig, self._data)
                pack["signal_id"] = sig_id
                pending.append(pack)
                # 标记已分发
                dispatched.add(sig_id)

        self._data["dispatched_signals"] = list(dispatched)
        self.save()
        return pending

    def dispatch_to_self_evolution(self, signal_pack: dict) -> dict:
        """
        将信号分发给自进化引擎。
        返回包装成 IntentContract 风格的信号。
        """
        return {
            "from_engine": "user_dynamic_portrait",
            "dispatch_type": "self_evolution",
            "goal": f"更新{signal_pack.get('target_file', '系统配置')}：{signal_pack.get('content', '')}",
            "signal_id": signal_pack.get("signal_id", ""),
            "target_file": signal_pack.get("target_file", ""),
            "content": signal_pack.get("content", ""),
            "confidence": signal_pack.get("confidence", 0.7),
        }

    def dispatch_to_auto_tuning(self, signal_pack: dict) -> dict:
        """
        将信号分发给参数自调优引擎。
        """
        tuning = signal_pack.get("tuning_target", {})
        if not tuning:
            return {"status": "skipped", "reason": "no tuning target"}
        return {
            "from_engine": "user_dynamic_portrait",
            "dispatch_type": "auto_tuning",
            "engine": tuning.get("engine", ""),
            "field": tuning.get("field", ""),
            "suggested_value": tuning.get("suggested_value"),
            "reason": tuning.get("reason", ""),
            "confidence": signal_pack.get("confidence", 0.7),
        }

    def get_context_summary(self) -> dict:
        pref = self._data.get("preference", {})
        dec = self._data.get("decision", {})
        risk = self._data.get("risk", {})
        habit = self._data.get("habit", {})

        notes = []
        if pref.get("style") == "direct":
            notes.append("偏好直接简洁的回答")
        elif pref.get("style") == "detailed":
            notes.append("偏好详细展开的回答")
        if pref.get("format") == "list":
            notes.append("喜欢分条列出")
        if risk.get("risk_tolerance") == "low":
            notes.append("操作前倾向先确认")
        elif risk.get("risk_tolerance") == "high":
            notes.append("倾向直接执行，减少确认")
        if dec.get("prefer_options"):
            notes.append("决策时倾向要多个方案对比")
        peak = habit.get("peak_hour", -1)
        if peak >= 0:
            notes.append(f"活跃峰值在{peak}时左右")
        task_types = habit.get("common_task_types", [])
        if task_types:
            notes.append(f"常见任务类型：{'/'.join(task_types[:3])}")

        return {
            "model": "UserDynamicPortraitEngine v2.0",
            "message_count": self._data.get("message_count", 0),
            "updated_at": self._data.get("updated_at", ""),
            "style": pref.get("style", "balanced"),
            "risk_tolerance": risk.get("risk_tolerance", "medium"),
            "confirm_tendency": risk.get("confirm_tendency", "ask_first"),
            "notes": notes,
            "summary": "；".join(notes) if notes else "尚无足够数据，使用默认模型",
        }

    def get_raw(self) -> dict:
        return dict(self._data)

    def reset(self):
        self._data = self._default_data()
        self.save()


# ================================================================
# 全局单例
# ================================================================
def get_portrait() -> UserDynamicPortraitEngine:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(UserDynamicPortraitEngine)

def init() -> UserDynamicPortraitEngine:
    """engines.json init_fn 入口"""
    return get_portrait()
