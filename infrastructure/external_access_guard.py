
from __future__ import annotations
import os, subprocess, urllib.request
from urllib.parse import urlparse
from typing import Any
_ACTIVE = False
_ORIG_URLOPEN = urllib.request.urlopen
_ORIG_RUN = subprocess.run
_ORIG_POPEN = subprocess.Popen
class ExternalAccessBlocked(RuntimeError): pass
def _local_url(url: Any) -> bool:
    try:
        parsed = urlparse(str(url)); host = (parsed.hostname or '').lower()
        return host in {'localhost', '127.0.0.1', '::1'} or host.endswith('.local')
    except Exception: return False
def zero_external() -> bool:
    try:
        from infrastructure.runtime_mode_resolver import is_zero_external
        return is_zero_external()
    except Exception:
        return os.environ.get('NO_EXTERNAL_API','').lower() == 'true' or os.environ.get('OFFLINE_MODE','').lower() == 'true'
def assert_external_allowed(kind: str = 'network', target: str = '') -> None:
    if zero_external(): raise ExternalAccessBlocked(f'{kind} blocked by V111.36 zero-external mode: {target[:160]}')
def _urlopen(url, *args, **kwargs):
    if zero_external() and not _local_url(url): raise ExternalAccessBlocked(f'urlopen blocked by zero-external mode: {url}')
    return _ORIG_URLOPEN(url, *args, **kwargs)
def _cmd_text(cmd: Any) -> str: return ' '.join(map(str, cmd)) if isinstance(cmd, (list, tuple)) else str(cmd)
def _is_external_cmd(cmd: Any) -> bool:
    t = _cmd_text(cmd).lower(); return any(x in t for x in ['curl ', 'wget ', 'ssh ', 'scp ', 'rsync ', 'git push', 'gh ', 'pip install', 'npm install', 'pnpm install'])
def _run(cmd, *args, **kwargs):
    if zero_external() and _is_external_cmd(cmd): raise ExternalAccessBlocked('subprocess.run external command blocked: ' + _cmd_text(cmd)[:160])
    return _ORIG_RUN(cmd, *args, **kwargs)
def _popen(cmd, *args, **kwargs):
    if zero_external() and _is_external_cmd(cmd): raise ExternalAccessBlocked('subprocess.Popen external command blocked: ' + _cmd_text(cmd)[:160])
    return _ORIG_POPEN(cmd, *args, **kwargs)
def activate() -> dict:
    global _ACTIVE
    if not _ACTIVE:
        urllib.request.urlopen = _urlopen; subprocess.run = _run; subprocess.Popen = _popen; _ACTIVE = True
    return {'status': 'ok', 'active': _ACTIVE, 'zero_external': zero_external()}
def status() -> dict: return {'active': _ACTIVE, 'zero_external': zero_external()}
