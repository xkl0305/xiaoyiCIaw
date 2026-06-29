"""ConstitutionKernel (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class ConstitutionKernel:
    """规则引擎 — 基于正则匹配的 allow/block/approval 决策"""

    def __init__(self):
        self.store = JsonStore(os.path.join(STATE_DIR, "constitution_rules.json"))
        self._ensure_defaults()

    def _ensure_defaults(self):
        if self.store.read():
            return
        rules = [
            ConstitutionRule(new_id("rule"), "block_secret_export",
                             r"(导出|发送|发到|发给|群发|外部发送).*(密钥|密码|token|secret|隐私)",
                             RuleSeverity.BLOCK,
                             "密钥和隐私数据禁止导出", tags=["secret"]),
            ConstitutionRule(new_id("rule"), "block_payment_without_approval",
                             r"转账|付款|支付|打款|收款账户", RuleSeverity.APPROVAL_REQUIRED,
                             "资金操作需要明确授权", tags=["money"]),
            ConstitutionRule(new_id("rule"), "approval_delete_or_overwrite",
                             r"删除|清空|覆盖全部|格式化|永久移除", RuleSeverity.APPROVAL_REQUIRED,
                             "不可逆销毁操作需要审批", tags=["destructive"]),
            ConstitutionRule(new_id("rule"), "approval_external_send",
                             r"发给客户|发送邮件|群发|外部发送|发到群里|提交给平台",
                             RuleSeverity.APPROVAL_REQUIRED,
                             "外部副作用需要人工审批", tags=["external"]),
            ConstitutionRule(new_id("rule"), "approval_install_unknown",
                             r"安装未知|自动安装|pip install|下载执行|运行陌生代码",
                             RuleSeverity.APPROVAL_REQUIRED,
                             "未知代码安装需要沙箱评估和审批", tags=["install"]),
            ConstitutionRule(new_id("rule"), "warn_low_risk",
                             r"计划|整理|总结|检查|生成方案", RuleSeverity.ALLOW,
                             "低风险规划操作", tags=["low_risk"]),
        ]
        self.store.write([asdict(r) for r in rules])

    def list_rules(self) -> List[ConstitutionRule]:
        return [ConstitutionRule(**x) for x in self.store.read()]

    def add_rule(self, name: str, pattern: str, severity: RuleSeverity,
                 reason: str, tags: List[str] = None) -> ConstitutionRule:
        data = self.store.read()
        rule = ConstitutionRule(new_id("rule"), name, pattern, severity, reason, tags=tags or [])
        data.append(asdict(rule))
        self.store.write(data)
        return rule

    def evaluate(self, action_summary: str) -> ConstitutionDecision:
        matched = []
        for rule in self.list_rules():
            if not rule.enabled:
                continue
            if re.search(rule.pattern, action_summary, flags=re.I):
                matched.append(rule)

        if any(r.severity == RuleSeverity.BLOCK for r in matched):
            return ConstitutionDecision("block", [r.name for r in matched],
                                        "被硬规则阻止", max((r.tags[0] if r.tags else "unknown") for r in matched))
        if any(r.severity in (RuleSeverity.APPROVAL_REQUIRED,) for r in matched):
            return ConstitutionDecision("approval_required", [r.name for r in matched],
                                        "需要审批", max((r.tags[0] if r.tags else "unknown") for r in matched))
        return ConstitutionDecision("allow", [r.name for r in matched], "规则允许", "L1")


# ================================================================
# 3. CapabilityGapAnalyzer — 能力差距分析
# ================================================================

@dataclass
