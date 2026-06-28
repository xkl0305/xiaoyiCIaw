from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .local_provider_base import LocalProviderResult
from .local_health_check import require_capabilities
from .local_model_registry import get_model_capability
from .observability_event_bus import emit_event

_ALLOWED_HOSTS = {'127.0.0.1', 'localhost', '::1'}
_DEFAULT_TIMEOUT = 60


def _blocked(capability: str, provider: str, reason: str = 'local_capability_not_available', **extra) -> Dict[str, Any]:
    return LocalProviderResult(
        status='blocked', capability=capability, provider=provider,
        blocked=True, blocked_reason=reason,
        metadata={'allow_external_fallback': False, 'network_egress_attempted': False, **extra}
    ).to_dict()


def _ok(capability: str, provider: str, output: Any, **metadata) -> Dict[str, Any]:
    return LocalProviderResult(
        status='executed', capability=capability, provider=provider,
        blocked=False, blocked_reason='', output=output,
        metadata={'allow_external_fallback': False, 'network_egress_attempted': False, **metadata}
    ).to_dict()


def _endpoint_allowed(endpoint: str) -> bool:
    try:
        parsed = urlparse(endpoint)
        return parsed.scheme in {'http', 'https'} and parsed.hostname in _ALLOWED_HOSTS
    except Exception:
        return False


def _endpoint_join(endpoint: str, path: str) -> str:
    endpoint = endpoint.rstrip('/')
    if endpoint.endswith(path.rstrip('/')):
        return endpoint
    if '/v1/' in endpoint:
        return endpoint
    return endpoint + path


def _post_json(url: str, payload: Dict[str, Any], *, timeout: int = _DEFAULT_TIMEOUT) -> Dict[str, Any]:
    if not _endpoint_allowed(url):
        return {'ok': False, 'status_code': 0, 'reason': 'non_local_endpoint_rejected'}
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            try:
                body = json.loads(raw)
            except Exception:
                body = {'raw': raw}
            return {'ok': 200 <= resp.getcode() < 300, 'status_code': resp.getcode(), 'body': body, 'http_client_used': 'urllib_local_loopback'}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        return {'ok': False, 'status_code': e.code, 'reason': raw[:500], 'http_client_used': 'urllib_local_loopback'}
    except Exception as e:
        return {'ok': False, 'status_code': 0, 'reason': str(e), 'http_client_used': 'urllib_local_loopback'}


def _format_command(command: str, **values: str) -> List[str]:
    safe = {k: str(v).replace('\n', ' ') for k, v in values.items()}
    formatted = command.format(**safe)
    return shlex.split(formatted)


def _run_command(command: str, *, stdin_text: str = '', timeout: int = _DEFAULT_TIMEOUT, **format_values) -> Dict[str, Any]:
    if not command:
        return {'ok': False, 'reason': 'command_not_configured'}
    try:
        argv = _format_command(command, **format_values)
    except Exception as e:
        return {'ok': False, 'reason': f'command_format_error:{e}'}
    if not argv:
        return {'ok': False, 'reason': 'command_empty'}
    try:
        started = time.time()
        proc = subprocess.run(argv, input=stdin_text, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            'ok': proc.returncode == 0,
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr[-1000:],
            'duration_ms': int((time.time() - started) * 1000),
            'command_adapter_used': True,
            'argv0': argv[0],
        }
    except Exception as e:
        return {'ok': False, 'reason': str(e), 'command_adapter_used': True, 'argv0': argv[0] if 'argv' in locals() and argv else ''}


def _registry_item(capability: str, root=None) -> Dict[str, Any]:
    return get_model_capability(capability, root=root)


def _require_one(capability: str, root=None) -> Optional[Dict[str, Any]]:
    ready = require_capabilities([capability], root=root)
    if not ready.get('ok'):
        return None
    return _registry_item(capability, root=root)


def _emit(event_type: str, payload: Dict[str, Any], root=None) -> None:
    try:
        emit_event(event_type, payload, root=root)
    except Exception:
        pass


def run_local_llm(prompt: str, *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_llm', root=root)
    if not item:
        return _blocked('local_llm', 'local_llm_provider')
    provider = item.get('provider') or 'local_llm_provider'
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/chat/completions')
        payload = {
            'model': item.get('model') or item.get('model_path') or 'local-llm',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': float(ctx.get('temperature', 0.2)),
            'stream': False,
        }
        res = _post_json(url, payload, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_llm', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        body = res.get('body') or {}
        text = (((body.get('choices') or [{}])[0].get('message') or {}).get('content') or body.get('text') or body.get('raw') or '')
        out = _ok('local_llm', provider, {'text': text, 'raw': body}, endpoint=url, http_client_used=res.get('http_client_used'))
        _emit('local_provider_executed', {'capability': 'local_llm', 'provider': provider, 'status': 'executed'}, root=root)
        return out
    if item.get('command'):
        res = _run_command(str(item['command']), stdin_text=prompt, prompt=prompt, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_llm', provider, 'local_command_execution_failed', error=res)
        return _ok('local_llm', provider, {'text': res.get('stdout',''), 'stderr': res.get('stderr','')}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_llm', provider, 'adapter_not_configured')


def run_local_ocr(image_path: str, *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_ocr', root=root)
    if not item:
        return _blocked('local_ocr', 'local_ocr_provider')
    provider = item.get('provider') or 'local_ocr_provider'
    if item.get('command'):
        res = _run_command(str(item['command']), image_path=image_path, stdin_text='', timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_ocr', provider, 'local_command_execution_failed', error=res)
        return _ok('local_ocr', provider, {'text': res.get('stdout','').strip(), 'image_path': image_path}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/ocr')
        res = _post_json(url, {'image_path': image_path}, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_ocr', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        return _ok('local_ocr', provider, res.get('body'), endpoint=url, http_client_used=res.get('http_client_used'))
    return _blocked('local_ocr', provider, 'adapter_not_configured')


def run_local_vlm(image_path: str, prompt: str = '', *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_vlm', root=root)
    if not item:
        return _blocked('local_vlm', 'local_vlm_provider')
    provider = item.get('provider') or 'local_vlm_provider'
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/chat/completions')
        payload = {
            'model': item.get('model') or item.get('model_path') or 'local-vlm',
            'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt or 'describe image'}, {'type': 'image_path', 'image_path': image_path}]}],
            'stream': False,
        }
        res = _post_json(url, payload, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_vlm', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        body = res.get('body') or {}
        text = (((body.get('choices') or [{}])[0].get('message') or {}).get('content') or body.get('text') or body.get('raw') or '')
        return _ok('local_vlm', provider, {'text': text, 'raw': body, 'image_path': image_path}, endpoint=url, http_client_used=res.get('http_client_used'))
    if item.get('command'):
        res = _run_command(str(item['command']), image_path=image_path, prompt=prompt, stdin_text=prompt, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_vlm', provider, 'local_command_execution_failed', error=res)
        return _ok('local_vlm', provider, {'text': res.get('stdout','').strip(), 'image_path': image_path}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_vlm', provider, 'adapter_not_configured')


def run_local_asr(audio_path: str, *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_asr', root=root)
    if not item:
        return _blocked('local_asr', 'local_asr_provider')
    provider = item.get('provider') or 'local_asr_provider'
    if item.get('command'):
        res = _run_command(str(item['command']), audio_path=audio_path, stdin_text='', timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_asr', provider, 'local_command_execution_failed', error=res)
        return _ok('local_asr', provider, {'text': res.get('stdout','').strip(), 'audio_path': audio_path}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_asr', provider, 'adapter_not_configured')


def run_local_tts(text: str, *, root=None, output_path: str = '', **ctx) -> Dict[str, Any]:
    item = _require_one('local_tts', root=root)
    if not item:
        return _blocked('local_tts', 'local_tts_provider')
    provider = item.get('provider') or 'local_tts_provider'
    if item.get('command'):
        res = _run_command(str(item['command']), text=text, output_path=output_path, stdin_text=text, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_tts', provider, 'local_command_execution_failed', error=res)
        return _ok('local_tts', provider, {'text': text, 'output_path': output_path, 'stdout': res.get('stdout','')}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_tts', provider, 'adapter_not_configured')


def run_local_embedding(text: str, *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_embedding', root=root)
    if not item:
        return _blocked('local_embedding', 'local_embedding_provider')
    provider = item.get('provider') or 'local_embedding_provider'
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/embeddings')
        res = _post_json(url, {'model': item.get('model') or 'local-embedding', 'input': text}, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_embedding', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        body = res.get('body') or {}
        embedding = (((body.get('data') or [{}])[0]).get('embedding') or body.get('embedding') or [])
        return _ok('local_embedding', provider, {'embedding': embedding, 'raw': body}, endpoint=url, http_client_used=res.get('http_client_used'))
    if item.get('command'):
        res = _run_command(str(item['command']), text=text, stdin_text=text, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_embedding', provider, 'local_command_execution_failed', error=res)
        try:
            emb = json.loads(res.get('stdout') or '[]')
        except Exception:
            emb = []
        return _ok('local_embedding', provider, {'embedding': emb, 'raw_stdout': res.get('stdout','')}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_embedding', provider, 'adapter_not_configured')


def run_local_image_provider(prompt: str, *, root=None, output_path: str = '', **ctx) -> Dict[str, Any]:
    item = _require_one('local_image_provider', root=root)
    if not item:
        return _blocked('local_image_provider', 'local_image_provider')
    provider = item.get('provider') or 'local_image_provider'
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/images/generations')
        res = _post_json(url, {'prompt': prompt, 'output_path': output_path}, timeout=int(ctx.get('timeout', 180)))
        if not res.get('ok'):
            return _blocked('local_image_provider', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        return _ok('local_image_provider', provider, res.get('body'), endpoint=url, http_client_used=res.get('http_client_used'))
    if item.get('command'):
        res = _run_command(str(item['command']), prompt=prompt, output_path=output_path, stdin_text=prompt, timeout=int(ctx.get('timeout', 180)))
        if not res.get('ok'):
            return _blocked('local_image_provider', provider, 'local_command_execution_failed', error=res)
        return _ok('local_image_provider', provider, {'output_path': output_path, 'stdout': res.get('stdout','')}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_image_provider', provider, 'adapter_not_configured')

# --- V111.52.12 additions: reranker + unified local capability executor ---
def run_local_reranker(query: str, documents: List[str], *, root=None, **ctx) -> Dict[str, Any]:
    item = _require_one('local_reranker', root=root)
    if not item:
        return _blocked('local_reranker', 'local_reranker_provider')
    provider = item.get('provider') or 'local_reranker_provider'
    if item.get('endpoint'):
        url = _endpoint_join(str(item['endpoint']), '/v1/rerank')
        res = _post_json(url, {'model': item.get('model') or 'local-reranker', 'query': query, 'documents': documents}, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_reranker', provider, 'local_endpoint_execution_failed', endpoint=url, error=res)
        return _ok('local_reranker', provider, res.get('body'), endpoint=url, http_client_used=res.get('http_client_used'))
    if item.get('command'):
        payload = json.dumps({'query': query, 'documents': documents}, ensure_ascii=False)
        res = _run_command(str(item['command']), query=query, documents=payload, stdin_text=payload, timeout=int(ctx.get('timeout', _DEFAULT_TIMEOUT)))
        if not res.get('ok'):
            return _blocked('local_reranker', provider, 'local_command_execution_failed', error=res)
        try:
            ranked = json.loads(res.get('stdout') or '[]')
        except Exception:
            ranked = []
        return _ok('local_reranker', provider, {'ranked': ranked, 'raw_stdout': res.get('stdout','')}, command_adapter_used=True, duration_ms=res.get('duration_ms'))
    return _blocked('local_reranker', provider, 'adapter_not_configured')


def execute_local_capability(capability: str, *, root=None, **kwargs) -> Dict[str, Any]:
    ctx = dict(kwargs)
    if capability == 'local_llm':
        prompt = ctx.pop('prompt', ctx.pop('text', ''))
        return run_local_llm(prompt, root=root, **ctx)
    if capability == 'local_vlm':
        image_path = ctx.pop('image_path', '')
        prompt = ctx.pop('prompt', '')
        return run_local_vlm(image_path, prompt, root=root, **ctx)
    if capability == 'local_ocr':
        image_path = ctx.pop('image_path', '')
        return run_local_ocr(image_path, root=root, **ctx)
    if capability == 'local_asr':
        audio_path = ctx.pop('audio_path', '')
        return run_local_asr(audio_path, root=root, **ctx)
    if capability == 'local_tts':
        text = ctx.pop('text', '')
        output_path = ctx.pop('output_path', '')
        return run_local_tts(text, root=root, output_path=output_path, **ctx)
    if capability == 'local_embedding':
        text = ctx.pop('text', '')
        return run_local_embedding(text, root=root, **ctx)
    if capability == 'local_reranker':
        query = ctx.pop('query', '')
        documents = ctx.pop('documents', [])
        return run_local_reranker(query, documents, root=root, **ctx)
    if capability == 'local_image_provider':
        prompt = ctx.pop('prompt', '')
        output_path = ctx.pop('output_path', '')
        return run_local_image_provider(prompt, root=root, output_path=output_path, **ctx)
    return _blocked(capability, 'local_provider_executor', 'unknown_local_capability')
