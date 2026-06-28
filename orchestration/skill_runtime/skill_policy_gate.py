from __future__ import annotations
"""V111.24 online-aware skill policy gate."""
import json, os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)

EXTERNAL_TOKENS=("requests","httpx","urllib","openai","anthropic","dashscope","webhook","feishu","email","calendar","upload","crawler","tts","music","image generation","seedream")
SEND_TOKENS=("send","email","webhook","feishu","push","publish","upload","发送","发布","上传")

def online_connected() -> bool:
    try:
        from infrastructure.online_runtime_policy import is_online_runtime_enabled
        return bool(is_online_runtime_enabled())
    except Exception:
        return True

def offline() -> bool:
    return not online_connected()

def classify_text(text: str) -> str:
    t=(text or '').lower()
    if any(tok in t for tok in SEND_TOKENS):
        return 'strong_confirmation_required'
    if any(tok in t for tok in EXTERNAL_TOKENS):
        return 'online_external_allowed' if online_connected() else 'external_api_blocked'
    return 'online_safe'

def classify_skill_file(path: str|Path) -> Dict[str, Any]:
    p=Path(path); text=''
    try: text=p.read_text(encoding='utf-8', errors='ignore')[:20000]
    except Exception: pass
    category=classify_text(str(p)+'\n'+text)
    return {
        'path': str(p),
        'category': category,
        'offline_allowed': category in ('online_safe','mock_only'),
        'requires_approval': category == 'strong_confirmation_required',
        'blocked_in_offline': category == 'external_api_blocked',
        'online_connected': online_connected(),
    }

def check_action(skill: str='', action: str='', confirmed: bool=False) -> Dict[str, Any]:
    category=classify_text(f'{skill} {action}')
    requires_confirm = category == 'strong_confirmation_required' and not confirmed
    return {
        'status': 'confirmation_required' if requires_confirm else 'ok',
        'skill': skill,
        'action': action,
        'category': category,
        'side_effects': category == 'strong_confirmation_required',
        'requires_api': category == 'online_external_allowed',
        'online_connected': online_connected(),
        'no_external_api': False,
        'no_real_send': False,
        'requires_strong_confirmation': requires_confirm,
    }

def generate_report(limit: int=500) -> Dict[str, Any]:
    items=[]; skills_root=ROOT/'skills'
    if skills_root.exists():
        for p in list(skills_root.rglob('SKILL.md'))[:limit]:
            items.append(classify_skill_file(p))
    report={'version':'V111.24','status':'pass','total_scanned':len(items),'online_safe':len([x for x in items if x['category']=='online_safe']),'online_external_allowed':len([x for x in items if x['category']=='online_external_allowed']),'strong_confirmation_required':len([x for x in items if x['category']=='strong_confirmation_required']),'items':items}
    (REPORTS/'V111_24_ONLINE_SKILL_POLICY_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
