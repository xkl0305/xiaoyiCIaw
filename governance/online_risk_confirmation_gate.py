from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'governance' / 'audit' / 'online_risk_confirmation_gate.jsonl'
AUDIT.parent.mkdir(parents=True, exist_ok=True)

COMMIT_PATTERNS={
 'payment':['pay','payment','purchase','checkout','transfer','付款','支付','转账','下单','购买'],
 'signature':['sign','signature','contract','agreement','签署','签字','合同'],
 'send':['send','email','publish','post','webhook','notify','发送','外发','发布','飞书','邮件'],
 'device':['device','robot','actuator','click','door','lock','机械','设备','机器人','开门','物理'],
 'delete':['delete','remove','drop','destroy','wipe','rm -rf','删除','销毁','清空'],
 'identity_commitment':['commit identity','promise as user','authorize as me','代表用户承诺','代表我承诺','身份承诺'],
}

def online_runtime_enabled() -> bool:
    try:
        from infrastructure.online_runtime_policy import is_online_runtime_enabled
        return bool(is_online_runtime_enabled())
    except Exception:
        return True

def classify_action(action: Any, context: dict|None=None) -> Dict[str, Any]:
    text=(str(action or '')+' '+str(context or {})).lower()
    matched=[]
    for cls, keys in COMMIT_PATTERNS.items():
        if any(k.lower() in text for k in keys):
            matched.append(cls)
    external = any(k in text for k in ['http','requests','openai','api','calendar','webhook','upload','seedream','image generation'])
    return {
        'action_text': str(action or ''),
        'commit_categories': matched,
        'is_commit': bool(matched),
        'is_external': external,
        'action_semantic': 'commit' if matched else 'external_api' if external else 'safe_direct',
    }

def _confirmed(context: dict|None=None, payload: Any=None) -> bool:
    ctx=context or {}
    if ctx.get('strong_confirmation') or ctx.get('confirmed') or ctx.get('confirmation_token'):
        return True
    if isinstance(payload, dict) and (payload.get('strong_confirmation') or payload.get('confirmed') or payload.get('confirmation_token')):
        return True
    return False

def check_online_action(action: Any=None, payload: Any=None, context: dict|None=None, source: str='online_risk_confirmation_gate') -> Dict[str, Any]:
    cls=classify_action(' '.join([str(action or ''), str(payload or '')[:500]]), context)
    online=online_runtime_enabled()
    confirmed=_confirmed(context, payload)
    if cls['is_commit'] and not confirmed:
        status='confirmation_required'
        allowed=False
        mode='strong_confirmation_required'
        reason='online connected; high-risk real-world side effect requires explicit strong confirmation'
    elif cls['is_commit'] and confirmed:
        status='ok'
        allowed=True
        mode='confirmed_commit'
        reason='explicit strong confirmation supplied'
    elif cls['is_external']:
        status='ok'
        allowed=True
        mode='standing_online_consent'
        reason='online-connected runtime allows external provider without per-action online authorization'
    else:
        status='ok'
        allowed=True
        mode='direct'
        reason='safe direct action'
    out={
        'status': status,
        'allowed': allowed,
        'mode': mode,
        'reason': reason,
        'requires_strong_confirmation': bool(cls['is_commit'] and not confirmed),
        'online_runtime_enabled': online,
        'classification': cls,
        'source': source,
        'ts': time.time(),
    }
    try:
        with AUDIT.open('a', encoding='utf-8') as f:
            f.write(json.dumps(out, ensure_ascii=False)+'\n')
    except Exception:
        pass
    return out
