from __future__ import annotations
import re, time
from typing import Dict, Any, Iterable
VERSION = 'V111.52.12_FULL_LOCAL_STACK_EMBODIED_OPS_FINAL'
DATA_CLASSES = {'S0':{'name':'runtime_secret','default_ttl_days':0,'persist':False},'S1':{'name':'raw_audio_screenshot_chat','default_ttl_days':14,'persist':True},'S2':{'name':'embedding_ocr_cache','default_ttl_days':60,'persist':True},'S3':{'name':'public_models_templates_indexes','default_ttl_days':3650,'persist':True}}
SECRET_PATTERNS = [re.compile(r'(?i)(sk|ark|api[_-]?key|token|secret)[=:][A-Za-z0-9_\-]{12,}'), re.compile(r'(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}')]
def classify_path(path: str) -> str:
    p = str(path).lower()
    if any(x in p for x in ['secret','.env','token','key']): return 'S0'
    if any(x in p for x in ['screenshot','audio','chat','conversation']): return 'S1'
    if any(x in p for x in ['embedding','ocr','cache','rerank']): return 'S2'
    return 'S3'
def redact_text(text: str) -> str:
    out = str(text or '')
    for pat in SECRET_PATTERNS: out = pat.sub('[REDACTED_SECRET]', out)
    return out
def retention_decision(path: str, *, now: float | None = None) -> Dict[str, Any]:
    now = now or time.time(); cls = classify_path(path); meta = DATA_CLASSES[cls]; ttl = meta['default_ttl_days']
    return {'path': path, 'data_class': cls, 'ttl_days': ttl, 'persist_allowed': bool(meta['persist']), 'delete_after_epoch': None if ttl <= 0 else int(now + ttl*86400), 'version': VERSION}
def scan_runtime_paths(paths: Iterable[str]) -> Dict[str, Any]:
    items = [retention_decision(p) for p in paths]
    return {'items': items, 's0_count': sum(1 for i in items if i['data_class']=='S0'), 'version': VERSION}
