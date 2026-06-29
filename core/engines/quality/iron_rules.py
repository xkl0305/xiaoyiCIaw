"""
Crusheart Agent OS — 系统铁律引擎（原名 three_rules → iron_rules v2.0）
来源：SOUL.md 全部铁律（原三条实战提炼 + 后续补充）
功能：每次回答前行为前置检查，与 anti-fake 内容验证互补
自包含，零外部依赖
"""

# 注意：2026-05-17 更名为 iron_rules.py（原 three_rules.py）
# 引用方已同步更新：anti_fake_validator, pipeline/engines, workflow/orchestrator

import os, sys

# ============================================================
# 铁律定义
# ============================================================

RULES = {
    "rule1": {
        "name": "铁律一：凡涉及事实，先查再说",
        "items": [
            "问模型状态 → 先跑 session_status",
            "问任务进度 → 先查文件/数据库",
            "问数据配置 → 先查原文",
            "禁止凭印象回答",
            "读取文件时务必翻到末尾，不只看开头就下结论",
            "看到数字/指标，先验证再下结论（来源可靠？和配置一致？有证据？）",
        ]
    },
    "rule2": {
        "name": "铁律二：凡涉及'我记得'，闭嘴3秒核实",
        "items": [
            "说'之前你说过' → 先查记录",
            "说'文件里写的' → 先查原文",
            "说'上次聊过' → 先查对话历史",
            "禁止凭记忆复述",
        ]
    },
    "rule3": {
        "name": "铁律三：凡不确定，明说'让我查一下'",
        "items": [
            "不确定就承认",
            "去查证再回答",
            "禁止装懂、禁止脑补",
        ]
    },
    "rule4": {
        "name": "铁律四：排查问题不只看表面报错",
        "items": [
            "报错说'重启 gateway' → 先查 Chrome 本身能不能跑、进程有没有残留、锁文件脏了没",
            "不要被'通用的错误提示'带偏，先自己深挖一层再说",
            "能直接查的就直接查，不依赖'按提示操作'",
        ]
    },
    "rule5": {
        "name": "铁律五：凡涉及 gateway / supervisor / 系统重启，必须先完成三步",
        "items": [
            "保存当前会话胶囊或任务摘要",
            "明确告诉用户：即将重启，当前会话可能断开，重启后新开会话继续",
            "使用后台延迟重启，不在当前回复里等待 restart 完成",
        ]
    },
    "rule6": {
        "name": "铁律六：删东西之前必须过用户确认",
        "items": [
            "收到删除指令后，先整理出完整删除清单（含路径和原因），发给用户确认",
            "未收到明确确认前，不动手删任何文件",
            "适用于：rm、trash、覆盖写入、清空目录等所有破坏性操作",
            "例外：临时文件、__pycache__ 等明确无害的缓存不受此限",
        ]
    },
    "rule7": {
        "name": "铁律七：修改系统文件必须先提案等确认",
        "items": [
            "适用范围：引擎代码(core/engines/)、核心脚本(scripts/核心)、技能代码(skills/)、配置文件(*.json, *.yaml 等系统配置)",
            "操作方式：必须先输出完整方案（改什么文件、改什么内容、风险等级、回滚方式），收到用户明确批准后方可执行",
            "禁止：即使觉得'改动很小'或用户说了'全部修复'四个字，也禁止未经确认直接写入",
            "不在此列：MEMORY.md、TOOLS.md、AGENTS.md、USER.md、SOUL.md 等用户文档（但自进化审批流程仍要走）",
            "执行前默念：这是系统文件吗？提案了吗？确认了吗？",
        ]
    },
    "rule8": {
        "name": "铁律八：任务失败必须主动恢复或明确告知",
        "items": [
            "工具调用超时、抛出异常或返回失败时，先调 RecoveryManager.decide() 判断能否恢复",
            "尝试恢复一次，成功则继续，失败则明确告知用户卡在哪、卡的原因、需要用户做什么",
            "禁止：失败后静默假装没发生过，或只给半截回复",
            "适用范围：所有多步任务、长时间任务",
        ]
    },
    "rule9": {
        "name": "铁律九：系统搭建期开发节奏提醒",
        "items": [
            "当持续多轮在文件间跳跃、不断尝试各种方案、改了一堆但没收束时，主动提醒用户整理思路写 TODO",
            "发现'干了但忘记录'的情况 → 主动问要不要写成 TODO 防忘",
            "仅限真正混乱时触发，不频繁打断正常开发节奏",
            "系统搭建期结束后由用户决定是否保留",
        ]
    },
    "cherry_blossom": {
        "name": "🌸 樱花准则（操作安全总括）",
        "items": [
            "删前必列清单等确认",
            "不改没让改的配置",
            "不顺手牵羊扫荡无关文件",
            "不确定范围就问，不做'我觉得'判断",
            "执行前默念三遍：这是要删的东西吗？就这些？确认了吗？",
        ]
    },
}

CHECKLIST = [
    "涉及事实？→ 先查",
    "说'我记得'？→ 先核实",
    "不确定？→ 明说'让我查一下'",
    "涉及决策？→ 先算成本和收益，不要凭感觉",
    "涉及 gateway/supervisor/系统重启？→ 先保存胶囊、告知用户、后台延迟重启（铁律五）",
    "涉及系统文件改动？→ 先提案等确认（铁律七）",
    "任务超时/失败？→ 调 RecoveryManager 恢复或明确告知（铁律八）",
    "长脚本（>10行 Python）？→ 用 pyrun.sh 写文件执行",
    "涉及'模块可用'判定？→ 不止验证 import/实例化，还要检查调用链路是否连通、路径是否准确、异常是否静默",
]


def init():
    """引擎初始化 — 打印九条铁律(+樱花准则)已加载"""
    print("  📋 九条铁律+樱花准则: 已加载（防'我以为'行为前置检查）")


def get_rules_text():
    """获取完整的九条铁律(+樱花准则)文本"""
    lines = []
    lines.append("🧱 九条铁律+樱花准则 — 防'我以为'操作守则")
    lines.append("")
    for key, rule in RULES.items():
        lines.append(f"### {rule['name']}")
        for item in rule["items"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("### 每轮回答前检查清单")
    for item in CHECKLIST:
        lines.append(f"- □ {item}")
    lines.append("")
    lines.append("### 触发机制")
    lines.append("- 用户说'铁律' → 立即拉回铁律三，不确定就说'让我查一下'")
    lines.append("- 做任务时默认启用全部九条铁律+樱花准则")
    return "\n".join(lines)


def validate_response_needed(task_type="normal"):
    """
    根据任务类型判断是否需要先执行铁律检查。
    返回: (should_check: bool, trigger_rules: list)
    """
    triggers = {
        "factual": ["rule1", "rule2"],
        "recall": ["rule2"],
        "uncertain": ["rule3"],
        "decision": ["rule1", "rule3"],
        "normal": [],
    }
    rules = triggers.get(task_type, [])
    return len(rules) > 0, [RULES[r]["name"] for r in rules]


def trigger_kind(text):
    """
    分析用户输入是否触发了铁律。
    返回: (triggered: bool, kind: str)
    """
    text_lower = text.lower()
    if "铁律" in text_lower:
        return True, "iron_rule"
    if "查一下" in text_lower or "查查" in text_lower:
        return True, "check_first"
    if "我记得" in text_lower or "我记得" in text_lower:
        return True, "recall_verify"
    return False, ""


# ============================================================
# Guardrail — 被动负反馈守卫
# 在每次 action 执行前拦截，检查是否违反铁律
# 极端场景/边界情况由 handle_boundary() 处理
# ============================================================


class GuardrailResult:
    """守卫拦截结果"""
    def __init__(self, allowed: bool, rule: str = "",
                 action: str = "", reason: str = "",
                 severity: str = "info"):
        self.allowed = allowed
        self.rule = rule
        self.action = action
        self.reason = reason
        self.severity = severity  # info / warn / block


# 边界场景定义 — 两个铁律冲突时的优先级
BOUNDARY_RULES = {
    "uncertain_but_user_pushing": {
        "description": "不确定但用户催着要答案",
        "action": "优先铁律三（明说查一下），给出预计耗时",
        "priority": "铁律三 > 用户催促",
    },
    "offline_no_network": {
        "description": "离线/无网络环境，无法查证事实",
        "action": "明说目前查不了，给出离线范围内的最佳回答并标注不确定性",
        "priority": "铁律三（告知限制）+ 铁律一降级",
    },
    "rule1_vs_rule7": {
        "description": "铁律一（先查再说）vs 铁律七（先提案等确认），查了就不能提案",
        "action": "先提案再查。提案本身不涉及系统修改，提案通过后再查证实现细节",
        "priority": "铁律七 > 铁律一",
    },
    "high_frequency_trigger": {
        "description": "同一铁律短时间内反复触发，用户开始烦躁",
        "action": "阈值自调整：连续触发≥3次则自动升一档宽松度"
                 "（如铁律七从 block 降为 warn），但保留日志",
        "priority": "用户体验 > 规则严格度（规则可松不可删）",
    },
    "emergency_override": {
        "description": "用户明确说'照做，后果我承担'",
        "action": "记录用户声明到 exec_logger，降低拦截等级至 warn 而非 block"
                 "，但核心安全（樱花准则：删除/不可逆操作）仍需确认",
        "priority": "用户意图 > 铁律六/七，但樱花准则核心不可绕过",
    },
}


class Guardrail:
    """被动负反馈守卫 — 执行前拦截 + 边界场景处理"""

    # 高频触发计数 — 用于阈值自调整
    _trigger_counter = {}  # {rule_key: count}
    _trigger_window = []  # [(timestamp, rule_key)]

    @classmethod
    def check(cls, action: str = "", context: dict = None) -> GuardrailResult:
        """
        执行前拦截检查。
        context 字段：
          - action_type: factual / recall / delete / system-edit / task / normal
          - has_verified: bool 是否已经查证
          - has_memory_search: bool 是否有 memory_search
          - has_proposal: bool 是否已有提案确认
          - task_failed: bool 任务是否失败
          - notified_user: bool 是否已告知用户
        """
        ctx = context or {}
        action_type = ctx.get("action_type", "normal")

        # — 铁律七：系统文件修改 —
        if action_type == "system-edit":
            if not ctx.get("has_proposal"):
                sev = cls._get_severity("rule7")
                return GuardrailResult(
                    allowed=sev != "block",
                    rule="rule7",
                    action=action,
                    reason="系统文件修改必须先提案等确认",
                    severity=sev,
                )

        # — 铁律一：事实未查 —
        if action_type == "factual":
            if not ctx.get("has_verified"):
                sev = cls._get_severity("rule1")
                return GuardrailResult(
                    allowed=sev != "block",
                    rule="rule1",
                    action=action,
                    reason="涉及事实，请先查再说",
                    severity=sev,
                )

        # — 铁律二：凭记忆 —
        if action_type == "recall":
            if not ctx.get("has_memory_search"):
                sev = cls._get_severity("rule2")
                return GuardrailResult(
                    allowed=sev != "block",
                    rule="rule2",
                    action=action,
                    reason="涉及'我记得'，请先核实再回答",
                    severity=sev,
                )

        # — 铁律八：任务失败未告知 —
        if action_type == "task" and ctx.get("task_failed"):
            if not ctx.get("notified_user"):
                sev = cls._get_severity("rule8")
                return GuardrailResult(
                    allowed=sev != "block",
                    rule="rule8",
                    action=action,
                    reason="任务失败必须明确告知用户原因",
                    severity=sev,
                )

        return GuardrailResult(allowed=True, action=action,
                               reason="无铁律冲突", severity="info")

    @classmethod
    def handle_boundary(cls, scenario: str, context: dict = None) -> dict:
        """边界/极端场景处理"""
        boundary = BOUNDARY_RULES.get(scenario)
        if not boundary:
            return {"handled": False, "action": "未知场景，按默认规则处理"}

        ctx = context or {}

        if scenario == "high_frequency_trigger":
            # 自调整：连续触发≥3次升一档宽松度
            rule_key = ctx.get("rule", "unknown")
            cls._trigger_counter[rule_key] = cls._trigger_counter.get(rule_key, 0) + 1
            count = cls._trigger_counter[rule_key]
            if count >= 3:
                return {
                    "handled": True,
                    "action": f"{rule_key} 已连续触发{count}次，规则宽松度提升一档",
                    "relaxed": True,
                    "boundary": boundary,
                }
            return {"handled": True, "action": boundary["action"],
                    "relaxed": False, "boundary": boundary}

        return {"handled": True, "action": boundary["action"],
                "relaxed": False, "boundary": boundary}

    @classmethod
    def _get_severity(cls, rule_key: str) -> str:
        """
        获取铁律的当前拦截等级。
        仅非安全规则（非 block）可高频触发后降级。
        rule6（删除前确认）/ rule7（提案确认）为安全红线，永不可降级。
        """
        base = {
            "rule1": "warn",
            "rule2": "warn",
            "rule3": "info",
            "rule4": "warn",
            "rule5": "warn",
            "rule6": "block",  # 安全红线：永不可降级
            "rule7": "block",  # 安全红线：永不可降级
            "rule8": "warn",
        }
        # 安全红线规则，永远 block，不受触发频率影响
        NEVER_DOWNGRADE = {"rule6", "rule7"}
        if rule_key in NEVER_DOWNGRADE:
            return base.get(rule_key, "block")
        
        default = base.get(rule_key, "warn")
        count = cls._trigger_counter.get(rule_key, 0)
        if count >= 3 and default == "block":
            return "warn"  # 非安全规则高频触发降级
        return default

    @classmethod
    def get_boundary_list(cls) -> dict:
        """获取所有边界场景定义，供注入 prompt"""
        return BOUNDARY_RULES

    @classmethod
    def get_trigger_stats(cls) -> dict:
        """获取触发统计"""
        return dict(cls._trigger_counter)


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

    init()
    print()
    print(get_rules_text())
    print()
    print("=" * 50)
    print("Guardrail 测试")
    g = Guardrail.check("edit_file", {"action_type": "system-edit", "has_proposal": False})
    print(f"  system-edit: allowed={g.allowed}, severity={g.severity}, reason={g.reason}")
    g2 = Guardrail.check("answer", {"action_type": "factual", "has_verified": True})
    print(f"  factual(have verified): allowed={g2.allowed}")
    g3 = Guardrail.check("answer", {"action_type": "factual", "has_verified": False})
    print(f"  factual(no verify): allowed={g3.allowed}, severity={g3.severity}")
    print()
    print("边界场景:")
    for k, v in BOUNDARY_RULES.items():
        print(f"  {k}: {v['description']} → {v['action'][:50]}...")
