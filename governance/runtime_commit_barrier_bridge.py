from __future__ import annotations
"""V111.24 online-connected commit barrier.

Online provider access is no longer blocked by offline flags. Real-world commit
classes (payment, signing, external send, physical device, destructive actions)
are not default-denied forever; they require explicit strong confirmation.
"""
import json, time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'governance' / 'audit' / 'runtime_commit_barrier_bridge.jsonl'
AUDIT.parent.mkdir(parents=True, exist_ok=True)

COMMIT_KEYWORDS = {
    'payment': ['pay','payment','purchase','buy','order','checkout','transfer','下单','付款','支付','转账','购买'],
    'signature': ['sign','signature','contract','agreement','签署','签字','合同'],
    'external_send': ['send','email','post','publish','webhook','feishu','push','上传','发送','邮件','发布','飞书'],
    'physical': ['device','robot','door','lock','move','actuator','设备','机器人','开门','门锁','机械臂','物理'],
    'destructive': ['delete','remove','drop','destroy','wipe','rm -rf','删除','销毁','清空'],
    'identity_commit': ['promise as me','authorize as me','identity commitment','代表我承诺','身份承诺'],
}

def online_connected() -> bool:
    try:
        from infrastructure.online_runtime_policy import is_online_runtime_enabled
        return bool(is_online_runtime_enabled())
    except Exception:
        return True

def offline_or_pending_access() -> bool:
    return not online_connected()

def classify_action(text: Any = '') -> Dict[str, Any]:
    s = str(text or '').lower()
    matched=[]
    for category, words in COMMIT_KEYWORDS.items():
        if any(w.lower() in s for w in words):
            matched.append(category)
    return {'action_text': str(text or ''), 'commit_categories': matched, 'is_commit': bool(matched), 'action_semantic': 'commit' if matched else 'analyze_prepare_direct'}

def _write_audit(payload: Dict[str, Any]) -> None:
    try:
        with AUDIT.open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False)+'\n')
    except Exception:
        pass

def _confirmed(payload: Any=None) -> bool:
    return isinstance(payload, dict) and bool(payload.get('strong_confirmation') or payload.get('confirmed') or payload.get('confirmation_token'))

def check_action(goal: Any=None, payload: Any=None, source: str='runtime_commit_barrier_bridge') -> Dict[str, Any]:
    text=' '.join([str(goal or ''), str(payload or '')[:500]])
    cls=classify_action(text)
    confirmed=_confirmed(payload)
    if cls['is_commit'] and not confirmed:
        status='confirmation_required'
        commit_blocked=True
        blocked_reason='strong_confirmation_required'
        reason='online connected, but commit/high-risk side effect requires explicit strong confirmation'
    elif cls['is_commit'] and confirmed:
        status='ok'
        commit_blocked=False
        blocked_reason=None
        reason='strong confirmation supplied'
    else:
        status='ok'
        commit_blocked=False
        blocked_reason=None
        reason='safe/direct online-connected action'
    result={
        'status': status,
        'source': source,
        'commit_blocked': commit_blocked,
        'requires_strong_confirmation': bool(cls['is_commit'] and not confirmed),
        'side_effects': bool(cls['is_commit']),
        'requires_api': False,
        'offline_or_pending_access': offline_or_pending_access(),
        'online_connected': online_connected(),
        'classification': cls,
        'blocked_reason': blocked_reason,
        'reason': reason,
        'ts': time.time(),
    }
    _write_audit(result)
    return result

def assert_commit_actions_blocked() -> Dict[str, Any]:
    probes=['please pay invoice','sign contract','send email','open robot device','delete all files','代表我承诺']
    results=[check_action(p, source='assert_probe') for p in probes]
    ok=all(r.get('requires_strong_confirmation') and r.get('commit_blocked') for r in results)
    return {'status':'pass' if ok else 'partial','probes':results,'commit_actions_require_strong_confirmation':ok}
