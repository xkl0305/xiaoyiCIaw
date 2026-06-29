"""
Crusheart Agent OS — 统一仲裁器 v1.0
Crusheart Agent OS — 统一仲裁引擎
功能：
  - UnifiedJudge：根据风险等级和用户画像做出决策（allow/block/require_approval）
  - CapabilityRegistry：能力注册表 + 风险等级 L0~L4 + BLOCKED
集成点：GoalCompiler → UnifiedJudge → TaskScheduler
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json, os, uuid

from core.engines.memory.exec_logger import log_execution
BEIJING_TZ = timezone(timedelta(hours=8))


# ================================================================
# 1. UnifiedJudge
# ================================================================

@dataclass
class JudgeDecision:
    decision: str          # allow / block / require_approval / require_clarification
    risk_tier: str         # L1~L5
    reasons: List[str]
    approval_required: bool
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(BEIJING_TZ).isoformat()

    def to_dict(self) -> Dict:
        return {
            "decision": self.decision,
            "risk_tier": self.risk_tier,
            "reasons": self.reasons,
            "approval_required": self.approval_required,
            "created_at": self.created_at,
        }


class UnifiedJudge:
    """统一仲裁器 — 所有操作执行前的决策层"""

    # 硬代码块：直接拒绝，不可绕过
    HARD_BLOCK = {
        'exfiltrate_secret', 'bypass_auth', 'disable_safety',
        'irreversible_delete_without_backup',
    }

    # 需要审批的操作（L3~L4）
    APPROVAL_REQUIRED = {
        'send_external', 'payment', 'purchase', 'install_code',
        'delete', 'publish', 'calendar_invite', 'send_message',
    }

    def decide(self, action: Dict[str, Any],
               user_profile: Optional[Dict] = None,
               runtime: Optional[Dict] = None) -> JudgeDecision:
        """做出执行决策"""
        user_profile = user_profile or {}
        runtime = runtime or {}
        name = str(action.get('action', 'unknown'))

        # L5: 硬代码块
        if name in self.HARD_BLOCK:
            return JudgeDecision('block', 'L5',
                                 ['hard_codex_block'], False)

        # 风险等级判定
        if action.get('destructive') or name in {'delete', 'payment', 'purchase', 'install_code'}:
            risk = 'L4'
        elif action.get('external') or name in {'send_external', 'publish', 'calendar_invite', 'send_message'}:
            risk = 'L3'
        elif action.get('mutates_state'):
            risk = 'L2'
        else:
            risk = 'L1'

        # 上下文置信度过低
        if runtime.get('context_confidence', 1) < 0.55:
            return JudgeDecision('require_clarification', risk,
                                 ['low_context_confidence'], False)

        # 用户偏好：禁止自动外部发送
        if user_profile.get('no_auto_external_send') and name == 'send_external':
            return JudgeDecision('require_approval', 'L3',
                                 ['user_preference_no_auto_external_send'], True)

        # L3~L4 需要审批
        if name in self.APPROVAL_REQUIRED or risk in {'L3', 'L4'}:
            return JudgeDecision('require_approval', risk,
                                 [f'approval_required_by_{risk.lower()}_tier'], True)

        return JudgeDecision('allow', risk,
                             ['allowed_by_unified_judge'], False)


# ================================================================
# 2. CapabilityRegistry — 能力注册表
# ================================================================

class CapabilityCategory(Enum):
    COMMUNICATION = "communication"
    SCHEDULE = "schedule"
    STORAGE = "storage"
    NOTIFICATION = "notification"
    APP_CONTROL = "app_control"
    SCREEN_VISION = "screen_vision"
    INPUT_CONTROL = "input_control"
    SEARCH = "search"
    EXECUTION = "execution"


class RiskLevel(Enum):
    L0 = "L0"       # 查询、总结、解释 — 自动执行
    L1 = "L1"       # 轻写入 — 自动执行
    L2 = "L2"       # 短信、通知、批量 — 策略控制
    L3 = "L3"       # 删除、拨电话、重要修改 — 默认确认
    L4 = "L4"       # 支付、金融、账号、隐私 — 强确认
    BLOCKED = "BLOCKED"  # 违法、盗号、绕过反作弊 — 拒绝


@dataclass
class CapabilityDefinition:
    capability_id: str
    name: str
    category: CapabilityCategory
    description: str
    risk_level: RiskLevel
    side_effecting: bool = False
    requires_auth: bool = False
    requires_confirmation: bool = False
    can_auto_run: bool = True
    can_dry_run: bool = True
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """能力注册表 — 管理和查询所有可用能力"""

    def __init__(self):
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册默认能力"""
        defaults = [
            # 搜索
            CapabilityDefinition("search.web", "联网搜索", CapabilityCategory.SEARCH,
                                 "搜索互联网信息", RiskLevel.L0),
            CapabilityDefinition("search.memory", "记忆搜索", CapabilityCategory.SEARCH,
                                 "搜索系统中已存储的记忆", RiskLevel.L0),
            # 日程
            CapabilityDefinition("schedule.create_event", "创建日程", CapabilityCategory.SCHEDULE,
                                 "创建日历事件", RiskLevel.L1, side_effecting=True),
            CapabilityDefinition("schedule.delete_event", "删除日程", CapabilityCategory.SCHEDULE,
                                 "删除日历事件", RiskLevel.L3, side_effecting=True, requires_confirmation=True),
            # 存储
            CapabilityDefinition("storage.create_note", "创建备忘录", CapabilityCategory.STORAGE,
                                 "创建备忘录", RiskLevel.L1, side_effecting=True),
            CapabilityDefinition("storage.delete_note", "删除备忘录", CapabilityCategory.STORAGE,
                                 "删除备忘录", RiskLevel.L3, side_effecting=True, requires_confirmation=True),
            # 通知
            CapabilityDefinition("notification.push", "推送通知", CapabilityCategory.NOTIFICATION,
                                 "推送通知到用户设备", RiskLevel.L2, side_effecting=True),
            # 执行
            CapabilityDefinition("execution.run_script", "执行脚本", CapabilityCategory.EXECUTION,
                                 "运行 Python 脚本", RiskLevel.L3, side_effecting=True, requires_confirmation=True),
            # 通信
            CapabilityDefinition("communication.send_message", "发送消息", CapabilityCategory.COMMUNICATION,
                                 "向用户发送消息", RiskLevel.L2, side_effecting=True),
        ]
        for cap in defaults:
            self.register(cap)

    def register(self, capability: CapabilityDefinition):
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> Optional[CapabilityDefinition]:
        return self._capabilities.get(capability_id)

    def list_all(self) -> List[CapabilityDefinition]:
        return list(self._capabilities.values())

    def list_by_category(self, category: CapabilityCategory) -> List[CapabilityDefinition]:
        return [c for c in self._capabilities.values() if c.category == category]

    def list_by_risk(self, risk: RiskLevel) -> List[CapabilityDefinition]:
        return [c for c in self._capabilities.values() if c.risk_level == risk]

    def can_auto_execute(self, capability_id: str) -> bool:
        cap = self.get(capability_id)
        if not cap:
            return False
        return cap.risk_level in (RiskLevel.L0, RiskLevel.L1)
