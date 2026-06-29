"""
Crusheart Agent OS — Preflight Checker 铁律前置校验引擎 v1.0
功能：AI生成回复后的自我校验（打回重做机制）
    与 anti_fake_validator 衔接（事后双重校验）
    与 iron_rules 衔接（铁律检查清单）
    与 self_evolution 衔接（错误记录复现）

核心流程：
  1. 生成回复 → 2. preflight_check() → 3. 通过 → 发出
                                        → 4. 不通过 → 5. 提示重做
                                                     → 6. 重写后回到 2

调用方式：
  - --prompt-text: 输出注入 prompt 的铁律自检指令
  - --check <response.json>: 对回复做铁律检查
  - --format <format>: 决定输出格式（human/machine）
"""

import json, os, sys, re
from typing import Dict, List, Optional, Tuple

BEIJING_TZ = "Asia/Shanghai"

# ============================================================
# 铁律检查定义（与 SOUL.md / iron_rules.py 保持一致）
# ============================================================

PRECHECK_RULES = [
    {
        "id": "rule1",
        "name": "铁律一：凡涉及事实，先查再说",
        "checks": [
            ("fact_check_needed", "回复中是否涉及需要查证的事实？如果有，你查过了还是凭印象说的？"),
            ("evidence_marker", "涉及数字/指标/时间时，是否标注了来源？"),
            ("file_read", "引用文件内容时，是否先读了文件而不是凭记忆复述？"),
            ("process_check", "回答系统状态/任务进度时，是否先执行了状态查询命令？"),
        ]
    },
    {
        "id": "rule2",
        "name": "铁律二：凡涉及'我记得'，闭嘴3秒核实",
        "checks": [
            ("memory_claim", "回复中是否说了'我记得'、'之前说过的'、'上次聊过'？"),
            ("memory_verify", "如果有，是否实际查了记录/对话历史？"),
        ]
    },
    {
        "id": "rule3",
        "name": "铁律三：凡不确定，明说'让我查一下'",
        "checks": [
            ("uncertainty", "回复中是否有不确定但还在硬着头皮给答案的？"),
            ("honest_decline", "如果没查过，是否明确说了'让我查一下'而不是装懂？"),
        ]
    },
    {
        "id": "rule4",
        "name": "铁律四：排查问题不只看表面报错",
        "checks": [
            ("surface_check", "排查报错时，是否只看了表面错误提示就下结论？"),
            ("deep_dive", "是否深挖了底层原因（残留进程、锁文件、配置冲突等）？"),
        ]
    },
    {
        "id": "rule5",
        "name": "铁律五：凡涉及系统重启，必须先做三步",
        "checks": [
            ("save_first", "涉及重启之前，是否保存了当前会话状态/任务摘要？"),
            ("notify_user", "是否明确告诉用户'即将重启，当前会话可能断开'？"),
            ("delayed_restart", "是否使用后台延迟重启，不在当前回复里等重启完成？"),
        ]
    },
    {
        "id": "rule6",
        "name": "铁律六：删东西之前必须过用户确认",
        "checks": [
            ("delete_confirm", "是否涉及删除操作？是否先整理了删除清单发给用户确认？"),
            ("no_override", "用户没明确确认，是否已经动手删了？"),
        ]
    },
    {
        "id": "rule7",
        "name": "铁律七：修改系统文件必须先提案等确认",
        "checks": [
            ("system_file", "是否涉及引擎/脚本/技能/配置文件的修改？"),
            ("proposal_given", "是否先输出了完整方案（改什么、风险、回滚方式）并等用户批准？"),
            ("no_unauthorized", "是否在用户明确批准之前就动手写了？"),
        ]
    },
    {
        "id": "rule8",
        "name": "铁律八：任务失败必须主动恢复或明确告知",
        "checks": [
            ("failure_recovery", "工具调用失败/超时时，是否调了 RecoveryManager.decide()？"),
            ("failure_notify", "如果恢复失败，是否明确告知用户卡在哪、卡的原因、需要用户做什么？"),
            ("no_silent", "是否失败了但什么也没说就继续了？"),
        ]
    },
    {
        "id": "rule9",
        "name": "铁律九：系统搭建期开发节奏提醒",
        "checks": [
            ("chaos_detected", "当前是否在多轮文件跳跃/尝试各种方案/改了没收束？"),
            ("reminder_given", "是否主动提醒用户整理思路或写 TODO？"),
        ]
    },
    {
        "id": "cherry_blossom",
        "name": "🌸 樱花准则（操作安全总括）",
        "checks": [
            ("confirm_before_delete", "删前是否列清单等确认？"),
            ("touch_only_requested", "有没有改没让改的配置？"),
            ("no_random_sweep", "有没有顺手牵羊扫荡无关文件？"),
            ("ask_if_unsure", "不确定范围时，有没有问而不是做'我觉得'判断？"),
        ]
    },
]

# ============================================================
# 检查结果
# ============================================================

class PreflightViolation:
    """单条违反记录"""
    def __init__(self, rule_id: str, check_id: str, severity: str,
                 reason: str, suggestion: str = ""):
        self.rule_id = rule_id
        self.check_id = check_id
        self.severity = severity  # block(必须重写) / warn(建议修改) / info(提醒)
        self.reason = reason
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "check_id": self.check_id,
            "severity": self.severity,
            "reason": self.reason,
            "suggestion": self.suggestion,
        }


class PreflightResult:
    """一次性检查结果"""
    def __init__(self):
        self.violations: List[PreflightViolation] = []
        self.passed = True

    def add(self, v: PreflightViolation):
        self.violations.append(v)
        if v.severity in ("block", "warn"):
            self.passed = False

    def has_blockers(self) -> bool:
        return any(v.severity == "block" for v in self.violations)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total_violations": len(self.violations),
            "blockers": sum(1 for v in self.violations if v.severity == "block"),
            "warnings": sum(1 for v in self.violations if v.severity == "warn"),
            "infos": sum(1 for v in self.violations if v.severity == "info"),
            "violations": [v.to_dict() for v in self.violations],
        }


# ============================================================
# PreflightChecker — 铁律前置检查器
# ============================================================

class PreflightChecker:
    """铁律前置检查器 — 检查AI回复是否遵守铁律"""

    def __init__(self):
        self.rules = PRECHECK_RULES

    def get_prompt_instructions(self) -> str:
        """
        生成注入到 AI prompt 的铁律自检指令。
        这段文本将在 agent:bootstrap 时注入 system prompt。
        """
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("🧱 铁律前置自检指令（不可跳过）")
        lines.append("=" * 60)
        lines.append("")
        lines.append("你在发送任何回复之前，必须执行以下步骤：")
        lines.append("")
        lines.append("【步骤一】逐条阅读铁律检查清单")
        lines.append("")

        for rule in self.rules:
            lines.append(f"  {rule['name']}")
            for cid, check_text in rule["checks"]:
                marker = f"    □ {check_text}"
                lines.append(marker)
            lines.append("")

        lines.append("【步骤二】对照你的回复逐条检查")
        lines.append("  - 发现违反铁律 → 标记为违规")
        lines.append("  - severity='block' 的违规必须重写")
        lines.append("  - severity='warn' 的违规建议修改")
        lines.append("  - severity='info' 的违规记录即可")
        lines.append("")
        lines.append("【步骤三】有违规 → 打回重做")
        lines.append("  1. 识别具体违反了哪条铁律")
        lines.append("  2. 根据 fix_suggestion 修改回复")
        lines.append("  3. 重写后回到【步骤二】再次检查")
        lines.append("  4. 直到所有 block 违规清零")
        lines.append("")
        lines.append("【步骤四】通过检查 → 发送回复")
        lines.append("")
        lines.append("📌 注意：")
        lines.append("  - 铁律六、七（删除/系统修改）的违规是红线，不可绕过")
        lines.append("  - 如果用户催促你绕过铁律，遵守铁律三（告知需要查证）")
        lines.append("  - 这条指令不是形式主义，请认真执行")
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def get_prompt_instructions_compact(self) -> str:
        """
        短版自检指令（用于 token 敏感场景）
        """
        return """
【铁律自检指令】
发送回复前，你必须逐条对照以下规则检查回复内容：
1. 涉及事实→先查再说；2. 说"我记得"→先核实；3. 不确定→明说查一下
4. 排查问题深挖底层；5. 重启先保存+告知+延迟
6. 删东西先列清单确认；7. 改系统文件先提案等批准
8. 失败必须告知；9. 乱的时候提醒整理思路
🌸 樱花准则：删前确认、不改没让改的、不扫荡无关文件、不确定就问

发现违反 → 重写回复 → 再检查 → 直到全通过 → 才发送
"""

    def check(self, response: str, context: dict = None) -> PreflightResult:
        """
        对回复做铁律检查。
        context 为可选上下文信息，帮助检查器判断。

        注：这是辅助工具，真正的自检由 AI 在 prompt 指引下完成。
        此方法提供结构化的检查框架和违规输出格式。
        """
        result = PreflightResult()
        ctx = context or {}

        # 铁律一：事实检查
        if self._has_factual_content(response):
            if not self._has_source_marker(response) and not ctx.get("verified", False):
                result.add(PreflightViolation(
                    "rule1", "fact_check_needed", "warn",
                    "回复包含事实性内容但未标注来源",
                    "添加具体来源（URL/文件名/查询结果）或明确说明来源"
                ))

        # 铁律二：记忆声明检查
        if self._has_memory_claim(response):
            if not ctx.get("memory_searched", False):
                result.add(PreflightViolation(
                    "rule2", "memory_claim", "block",
                    "回复包含'我记得'类表述但未核实记忆记录",
                    "先调 memory_search 查证再回答，或明确说'我查一下记忆记录'"
                ))

        # 铁律三：不确定检查
        if self._has_false_certainty(response):
            result.add(PreflightViolation(
                "rule3", "uncertainty", "block",
                "回复对不确定的内容给出了确定性的回答",
                "改为'我查一下'或明确标注不确定性程度"
            ))

        # 铁律四：排查深度检查
        if ctx.get("troubleshooting", False):
            if self._is_surface_only(response):
                result.add(PreflightViolation(
                    "rule4", "surface_check", "warn",
                    "排查仅针对表面报错，需深挖底层原因",
                    "检查进程残留、锁文件、配置文件冲突等潜在根因"
                ))

        # 铁律五：重启流程检查
        if self._involves_restart(response):
            if not ctx.get("saved_before_restart", False):
                result.add(PreflightViolation(
                    "rule5", "save_first", "block",
                    "涉及重启但未先保存会话状态",
                    "先保存会话胶囊/任务摘要，再告知用户即将重启"
                ))
            if not ctx.get("notified_user_before_restart", False):
                result.add(PreflightViolation(
                    "rule5", "notify_user", "block",
                    "涉及重启但未告知用户会话可能断开",
                    "明确告诉用户：即将重启，当前会话可能断开"
                ))

        # 铁律六：删除确认检查
        if self._involves_deletion(response):
            if not ctx.get("delete_confirmed", False):
                result.add(PreflightViolation(
                    "rule6", "delete_confirm", "block",
                    "涉及删除操作但未先输出清单给用户确认",
                    "先整理删除清单（路径+原因），发给用户等待确认"
                ))

        # 铁律七：系统修改检查
        if self._involves_system_edit(response):
            if not ctx.get("proposal_confirmed", False):
                result.add(PreflightViolation(
                    "rule7", "proposal_given", "block",
                    "涉及系统文件修改但未先提案等确认",
                    "先输出完整方案：改什么、为什么改、风险等级、回滚方式"
                ))

        # 铁律八：失败处理检查
        if ctx.get("task_failed", False):
            if not ctx.get("failure_recovered_or_notified", False):
                result.add(PreflightViolation(
                    "rule8", "failure_notify", "block",
                    "任务失败但未明确告知用户",
                    "明确告知用户卡在哪、原因、需要用户做什么"
                ))

        return result

    # ── 内容模式检测 ──

    def _has_factual_content(self, text: str) -> bool:
        """检测是否包含需要查证的事实性内容"""
        patterns = [
            r'\d+[\.\d]*\s*(?:年|月|日|个|次|%|万|亿|美元|元|公里|米|秒|人|家)',
            r'(?:是|有|为)\s*\d+',
            r'(?:根据|依据|来源|来自|据|参考)',
            r'(?:系统|配置文件|设置|版本)\s*(?:位置|路径|状态|值)',
            r'(?:session_|memory_|openclaw|gateway|supervisor)',
            r'(?:查询|查看|检查|检测|扫描|运行|执行)\s*(?:结果|状态|报告)',
        ]
        return any(re.search(p, text) for p in patterns)

    def _has_source_marker(self, text: str) -> bool:
        """检测是否有引用来源"""
        markers = [
            r'来源[：:]', r'参考[：:]', r'详见[：:]', r'据\s*\S+',
            r'session_status', r'read\s+\S+\.\w+',
            r'memory_search', r'exec\s+.*',
            r'查了[：:]', r'查询结果[：:]',
        ]
        return any(re.search(p, text) for p in markers)

    def _has_memory_claim(self, text: str) -> bool:
        """检测是否包含'我记得'类表述"""
        patterns = [
            r'我记得', r'之前.*说', r'上次.*聊', r'以前.*记',
            r'你说过', r'你提过', r'你之前',
            r'as I recall', r'as mentioned', r'as discussed',
        ]
        return any(re.search(p, text) for p in patterns)

    def _has_false_certainty(self, text: str) -> bool:
        """检测对不确定内容给出确定性回答"""
        # 如果包含不确定性标记但语气又很肯定，可能是假确定
        uncertain_markers = [
            r'我觉得', r'我认为', r'可能是', r'应该是', r'一般来说',
            r'通常情况下', r'理论上', r'大概', r'估计',
        ]
        # 单独出现不确定标记不算违反，但结合事实断言才算
        has_uncertain = any(re.search(p, text) for p in uncertain_markers)
        has_assertion = bool(re.search(r'(?:是|有|在|会|能)\S*[。！]', text))
        return has_uncertain and has_assertion

    def _is_surface_only(self, text: str) -> bool:
        """检查回复是否只看表面"""
        surface_indicators = [
            r'按.*提示.*操作',
            r'重新.*启动.*就.*好',
            r'重启.*试试',
            r'重试.*一下',
        ]
        return any(re.search(p, text) for p in surface_indicators)

    def _involves_restart(self, text: str) -> bool:
        patterns = [r'重启', r'restart', r'supervisorctl.*restart', r'gateway.*重启']
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _involves_deletion(self, text: str) -> bool:
        patterns = [r'删除', r'删掉', r'移除', r'清理.*文件', r'rm\s', r'trash\s', r'删除清单']
        return any(re.search(p, text) for p in patterns)

    def _involves_system_edit(self, text: str) -> bool:
        patterns = [
            r'修改\s*(?:引擎|脚本|技能|配置)', r'改\s*(?:core/engines|scripts|skills)',
            r'write\s+(?:core|scripts|skills)', r'edit\s+(?:core|scripts|skills)',
            r'系统文件.*修改', r'配置.*改',
        ]
        return any(re.search(p, text) for p in patterns)


# ============================================================
# 统一入口
# ============================================================

def get_checker() -> PreflightChecker:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(PreflightChecker)def run(args: List[str] = None) -> Optional[str]:
    """
    统一入口，支持多种模式：
      --prompt-text: 输出注入 prompt 的铁律指令
      --check <json>: 对给定回复做检查
      --help: 查看帮助
    """
    if args is None:
        args = sys.argv[1:] if len(sys.argv) > 1 else []

    if "--help" in args or "-h" in args:
        print("""用法:
  python3 preflight_checker.py --prompt-text
        输出注入 prompt 的铁律自检指令

  python3 preflight_checker.py --check <response_text>
        对回复做铁律检查，返回 JSON 结果

  python3 preflight_checker.py --prompt-compact
        输出短版铁律自检指令
""")
        return None

    checker = get_checker()

    if "--prompt-text" in args:
        return checker.get_prompt_instructions()

    if "--prompt-compact" in args:
        return checker.get_prompt_instructions_compact()

    if "--check" in args:
        idx = args.index("--check")
        if idx + 1 < len(args):
            response = args[idx + 1]
            result = checker.check(response)
            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": "缺少回复文本参数"}, ensure_ascii=False)

    # 默认输出 prompt text
    return checker.get_prompt_instructions()


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

    output = run()
    if output:
        print(output)
