from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
try:
    from infrastructure.unified_observability_ledger import record_event
except Exception:
    def record_event(*a, **k): return None

COMMIT_PATTERNS={
 'payment':['pay','payment','purchase','checkout','transfer','付款','支付','转账','下单'],
 'signature':['sign','signature','contract','签署','合同','签名'],
 'send':['send','email','publish','post','webhook','notify','发送','外发','发布','飞书'],
 'device':['device','robot','actuator','click','door','机械','设备','机器人','开门'],
 'delete':['delete','remove','drop','destroy','删除','销毁','清空'],
 'identity_commitment':['commit identity','promise as user','代表用户承诺','代表我承诺','身份承诺'],
}
@dataclass
class GovernanceDecision:
    allowed: bool
    action_class: str
    recommendation_mode: str
    risk_class: str
    reason: str
    blocked_reason: str|None=None
    requires_strong_confirmation: bool=False
    online_connected: bool=True
    no_external_api: bool=False
    no_real_send: bool=False
    no_real_payment: bool=False
    no_real_device: bool=False
    def to_dict(self): return asdict(self)

def classify_action(action: Any, context: dict|None=None):
    text=(str(action)+' '+str(context or {})).lower()
    for cls, keys in COMMIT_PATTERNS.items():
        if any(k.lower() in text for k in keys): return cls
    if any(k in text for k in ['http','requests','openai','api','calendar','web','seedream']): return 'external_api'
    return 'safe_direct'

def _online_connected() -> bool:
    try:
        from infrastructure.online_runtime_policy import is_online_runtime_enabled
        return bool(is_online_runtime_enabled())
    except Exception:
        return True

class UnifiedGovernanceGate:
    def check_action(self, action: Any, context: dict|None=None):
        context=context or {}
        action_class=classify_action(action, context)
        online=_online_connected()
        confirmed=bool(context.get('strong_confirmation') or context.get('confirmed') or context.get('confirmation_token'))
        env={'no_external_api':False,'no_real_send':False,'no_real_payment':False,'no_real_device':False}
        if action_class in {'payment','signature','send','device','delete','identity_commitment'} and not confirmed:
            d=GovernanceDecision(False,action_class,'strong_confirmation_required','commit_high','online connected; commit action requires explicit strong confirmation',f'{action_class}_strong_confirmation_required',True,online,**env)
        elif action_class in {'payment','signature','send','device','delete','identity_commitment'} and confirmed:
            d=GovernanceDecision(True,action_class,'confirmed_commit','commit_high','explicit strong confirmation supplied',None,False,online,**env)
        elif action_class=='external_api':
            d=GovernanceDecision(True,action_class,'standing_online_consent','external','online-connected runtime allows external providers without per-action online authorization',None,False,online,**env)
        else:
            d=GovernanceDecision(True,action_class,'direct','low','safe direct action allowed',None,False,online,**env)
        record_event('governance_decision', d.to_dict())
        return d

def check_action(action: Any, context: dict|None=None): return UnifiedGovernanceGate().check_action(action, context).to_dict()
