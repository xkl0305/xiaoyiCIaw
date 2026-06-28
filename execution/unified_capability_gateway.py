#!/usr/bin/env python3
"""
from __future__ import annotations

V109 Unified Capability Gateway (V109)

统一能力网关：为所有 execution/capabilities/ 下的能力模块提供单一路由入口。
- 所有能力调用先经过网关的安全/路由检查
- 外部API能力在离线模式下降级为 mock
- commit类能力在无审批时阻断
- 保留原有能力模块的实现，不重构
"""
import os
from typing import Any, Dict, Optional
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NO_EXTERNAL_API = os.environ.get("NO_EXTERNAL_API", "true").lower() == "true"
NO_REAL_SEND = os.environ.get("NO_REAL_SEND", "true").lower() == "true"
NO_REAL_PAYMENT = os.environ.get("NO_REAL_PAYMENT", "true").lower() == "true"
NO_REAL_DEVICE = os.environ.get("NO_REAL_DEVICE", "true").lower() == "true"

# 定义各能力模块的安全属性
CAPABILITY_METADATA: Dict[str, dict] = {
    # 读/查询类 — 低风险
    "query_alarm": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_calendar_event": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_contact": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_file": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_note": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_photo": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_xiaoyi_note": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_message_status": {"risk": "low", "external_api": False, "requires_approval": False},
    "query_notification_status": {"risk": "low", "external_api": False, "requires_approval": False},
    "search_notes": {"risk": "low", "external_api": False, "requires_approval": False},
    "check_calendar_conflicts": {"risk": "low", "external_api": False, "requires_approval": False},
    "get_location": {"risk": "low", "external_api": False, "requires_approval": False},
    "list_calendar_events": {"risk": "low", "external_api": False, "requires_approval": False},
    "list_recent_messages": {"risk": "low", "external_api": False, "requires_approval": False},
    "list_recent_notes": {"risk": "low", "external_api": False, "requires_approval": False},
    "diagnostics": {"risk": "low", "external_api": False, "requires_approval": False},
    "explain_invocation_status": {"risk": "low", "external_api": False, "requires_approval": False},
    "explain_message_result": {"risk": "low", "external_api": False, "requires_approval": False},
    "explain_notification_auth_state": {"risk": "low", "external_api": False, "requires_approval": False},
    "export_history": {"risk": "low", "external_api": False, "requires_approval": False},
    "replay_run": {"risk": "low", "external_api": False, "requires_approval": False},
    "self_repair": {"risk": "low", "external_api": False, "requires_approval": False},
    "preview_side_effect": {"risk": "low", "external_api": False, "requires_approval": False},
    "refresh_notification_auth": {"risk": "low", "external_api": False, "requires_approval": False},

    # 写/变更类 — 中风险
    "create_alarm": {"risk": "medium", "external_api": False, "requires_approval": False},
    "create_album": {"risk": "medium", "external_api": False, "requires_approval": False},
    "create_contact": {"risk": "medium", "external_api": False, "requires_approval": False},
    "update_alarm": {"risk": "medium", "external_api": False, "requires_approval": False},
    "update_calendar_event": {"risk": "medium", "external_api": False, "requires_approval": False},
    "update_contact": {"risk": "medium", "external_api": False, "requires_approval": False},
    "update_note": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_alarm": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_calendar_event": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_contact": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_file": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_note": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_photo": {"risk": "medium", "external_api": False, "requires_approval": False},
    "delete_xiaoyi_note": {"risk": "medium", "external_api": False, "requires_approval": False},
    "cancel_notification": {"risk": "medium", "external_api": False, "requires_approval": False},
    "manage_file": {"risk": "medium", "external_api": False, "requires_approval": False},

    # 高/外部风险
    "make_call": {"risk": "high", "external_api": False, "requires_approval": True},
    "send_message": {"risk": "high", "external_api": True, "requires_approval": True},
    "resend_message": {"risk": "high", "external_api": True, "requires_approval": True},

    # 任务管理
    "schedule_task": {"risk": "medium", "external_api": False, "requires_approval": False},
    "cancel_task": {"risk": "medium", "external_api": False, "requires_approval": False},
    "pause_task": {"risk": "low", "external_api": False, "requires_approval": False},
    "resume_task": {"risk": "low", "external_api": False, "requires_approval": False},
    "retry_task": {"risk": "low", "external_api": False, "requires_approval": False},

    # 审批
    "approve_action": {"risk": "high", "external_api": False, "requires_approval": True},
    "confirm_invocation": {"risk": "high", "external_api": False, "requires_approval": True},
}


class UnifiedCapabilityGateway:
    """统一能力网关。"""

    def check(self, capability_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        检查一个能力调用是否允许执行。
        
        返回：
            status: ok / blocked / dry_run / approval_required
            execution_mode: direct / mock_only / approval_required / blocked
            risk_class: low / medium / high
            external_api: bool
            side_effects: bool
        """
        meta = CAPABILITY_METADATA.get(capability_name, {})
        risk = meta.get("risk", "medium")
        ext_api = meta.get("external_api", False)
        req_approval = meta.get("requires_approval", False)
        base = {
            "capability": capability_name,
            "risk_class": risk,
            "external_api": ext_api,
            "real_execution": False,
        }

        # 安全环境变量
        no_ext = NO_EXTERNAL_API
        no_send = NO_REAL_SEND
        no_payment = NO_REAL_PAYMENT
        no_device = NO_REAL_DEVICE

        # 阻断条件
        if ext_api and no_ext:
            return {**base, "status": "blocked", "execution_mode": "blocked",
                    "blocked_reason": "external_api_blocked_by_offline_mode",
                    "side_effects": False, "note": "外部API被离线模式阻断"}

        if risk == "high" and no_send:
            return {**base, "status": "blocked", "execution_mode": "blocked",
                    "blocked_reason": "high_risk_skill_blocked",
                    "side_effects": False, "note": "高风险能力被环境变量阻断"}

        if req_approval:
            return {**base, "status": "approval_required", "execution_mode": "approval_required",
                    "side_effects": False, "note": "需要用户审批才能执行"}

        # 外部API能力降级为mock
        if ext_api:
            return {**base, "status": "mock_only", "execution_mode": "mock_only",
                    "side_effects": False, "note": "外部API能力仅mock执行"}

        # 可执行
        return {**base, "status": "ok", "execution_mode": "direct",
                "side_effects": risk in ("medium", "high"),
                "note": "能力已通过网关检查"}

    def list_all(self) -> Dict[str, dict]:
        """列出所有能力及其安全属性。"""
        result = {}
        for name, meta in CAPABILITY_METADATA.items():
            result[name] = {
                "risk": meta["risk"],
                "external_api": meta["external_api"],
                "requires_approval": meta["requires_approval"],
            }
        return result

    def list_by_risk(self, risk_class: str) -> List[str]:
        """按风险等级列出能力。"""
        return [n for n, m in CAPABILITY_METADATA.items()
                if m.get("risk") == risk_class]


# 单例
_gateway: Optional[UnifiedCapabilityGateway] = None


def get_gateway() -> UnifiedCapabilityGateway:
    global _gateway
    if _gateway is None:
        _gateway = UnifiedCapabilityGateway()
    return _gateway


def check_capability(name: str, params: dict = None) -> dict:
    return get_gateway().check(name, params)


def list_capabilities() -> dict:
    return get_gateway().list_all()
