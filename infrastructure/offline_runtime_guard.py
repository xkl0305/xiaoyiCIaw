from __future__ import annotations
"""V111.24 online-compatible runtime guard.

This file remains only as a compatibility import target for older modules.
It no longer forces offline mode. Network/external calls are allowed when
openclaw.json says the runtime is online-connected. High-risk real-world
commit actions are routed to strong confirmation instead of blanket offline denial.
"""
import os, subprocess, urllib.request
from typing import Any, Dict

_ACTIVE=False
_ORIG_URLOPEN=urllib.request.urlopen
_ORIG_RUN=subprocess.run
_ORIG_POPEN=subprocess.Popen

class OfflineRuntimeBlocked(RuntimeError): pass

def _online_enabled() -> bool:
    try:
        from infrastructure.online_runtime_policy import is_online_runtime_enabled
        return bool(is_online_runtime_enabled())
    except Exception:
        return os.environ.get('ONLINE_MODE', '').lower() == 'true' and os.environ.get('OFFLINE_MODE', '').lower() != 'true'

def offline_mode() -> bool:
    if _online_enabled():
        return False
    return os.environ.get('OFFLINE_MODE')=='true' or os.environ.get('NO_EXTERNAL_API')=='true'

def no_real_send() -> bool:
    if _online_enabled():
        return False
    return os.environ.get('NO_REAL_SEND')=='true'

def _cmd_text(cmd):
    return ' '.join(map(str,cmd)) if isinstance(cmd,(list,tuple)) else str(cmd)

def _urlopen(*a,**kw):
    if offline_mode():
        raise OfflineRuntimeBlocked('external network call blocked by legacy offline mode')
    return _ORIG_URLOPEN(*a,**kw)

def _run(cmd,*a,**kw):
    t=_cmd_text(cmd).lower()
    if (offline_mode() or no_real_send()) and any(x in t for x in ['git push','curl ','wget ','ssh ','scp ','rsync ','gh ']):
        raise OfflineRuntimeBlocked('external command blocked by legacy offline mode: '+t[:120])
    return _ORIG_RUN(cmd,*a,**kw)

def _popen(cmd,*a,**kw):
    t=_cmd_text(cmd).lower()
    if (offline_mode() or no_real_send()) and any(x in t for x in ['git push','curl ','wget ','ssh ','scp ','rsync ','gh ']):
        raise OfflineRuntimeBlocked('external command blocked by legacy offline mode: '+t[:120])
    return _ORIG_POPEN(cmd,*a,**kw)

def activate(config=None, **kwargs):
    global _ACTIVE
    if not _ACTIVE:
        urllib.request.urlopen=_urlopen
        subprocess.run=_run
        subprocess.Popen=_popen
        _ACTIVE=True
    return {'status':'ok','active':_ACTIVE,'offline':offline_mode(),'online_connected':_online_enabled(),'config':config or kwargs,'compatibility_shim':True}

def status():
    return {'active':_ACTIVE,'offline':offline_mode(),'online_connected':_online_enabled(),'no_real_send':no_real_send(),'compatibility_shim':True}

def classify_commit_action(action: Any) -> Dict[str, Any]:
    txt=str(action or '').lower()
    groups={
        'payment':['pay','payment','transfer','purchase','checkout','付款','支付','转账','下单','购买'],
        'signature':['sign','signature','contract','agreement','签署','签字','合同'],
        'send_publish':['send','email','publish','post','webhook','push','发送','外发','发布','邮件'],
        'device':['device','robot','door','lock','move','actuator','设备','机器人','开门','物理'],
        'destructive':['delete','remove','drop','destroy','wipe','rm -rf','删除','清空','销毁'],
    }
    matched=[k for k, words in groups.items() if any(w in txt for w in words)]
    return {'is_commit': bool(matched), 'commit_categories': matched, 'action_text': str(action or '')}

def assert_safe_action(action, context=None):
    cls=classify_commit_action(action)
    if cls['is_commit']:
        confirmed = bool((context or {}).get('strong_confirmation') or (context or {}).get('confirmed'))
        return {
            'allowed': confirmed,
            'mode': 'confirmed_commit' if confirmed else 'strong_confirmation_required',
            'reason': 'confirmed by explicit strong confirmation' if confirmed else 'online connected, but high-risk side effect requires explicit strong confirmation',
            'requires_strong_confirmation': not confirmed,
            'classification': cls,
        }
    return {'allowed':True,'mode':'direct','reason':'safe online-connected action','requires_strong_confirmation':False,'classification':cls}
