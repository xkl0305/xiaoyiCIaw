from __future__ import annotations

import hashlib
import hmac
import inspect
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from xiaoyi_persona_visual.policy.mainchain_proof_runtime_registry import register_issued_proof, consume_issued_proof

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ISSUER = 'persona_visual_auto_generation_bridge'
DEFAULT_TTL_SECONDS = 120


def _normalize_path(value: str) -> str:
    p = Path(str(value))
    try:
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        else:
            p = p.resolve()
    except Exception:
        p = Path(str(value))
    return str(p).replace('\\', '/').lower()


def _normalize_prompt(prompt: str) -> str:
    return ' '.join((prompt or '').split()).strip()


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def _reference_paths_sha256(reference_images: Iterable[str]) -> str:
    normalized = [_normalize_path(x) for x in (reference_images or []) if str(x).strip()]
    return _sha256_text('\n'.join(normalized))


def _canonical_json(obj: Dict[str, Any]) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _contract_sig(body: Dict[str, Any]) -> str:
    return hmac.new(_ensure_secret().encode('utf-8'), _canonical_json(body).encode('utf-8'), hashlib.sha256).hexdigest()


def _ensure_secret() -> str:
    for key in ('MAINCHAIN_PROOF_KEY', 'PERSONA_VISUAL_MAINCHAIN_SECRET'):
        value = os.environ.get(key, '').strip()
        if value:
            return value
    raise RuntimeError('missing_runtime_secret: MAINCHAIN_PROOF_KEY or PERSONA_VISUAL_MAINCHAIN_SECRET required')


def _proof_message(*, request_id: str, prompt_sha256: str, reference_paths_sha256: str, pipeline_entry: str, issued_by: str, controller: str, prompt_builder: str, expires_at: int) -> str:
    parts = [request_id, prompt_sha256, reference_paths_sha256, pipeline_entry, issued_by, controller, prompt_builder, str(expires_at)]
    return '|'.join(parts)


def _called_from_bridge() -> bool:
    try:
        for frame in inspect.stack()[1:8]:
            fn = str(frame.filename).replace('\\', '/')
            if fn.endswith('memory_context/persona_runtime/persona_visual_auto_generation_bridge.py'):
                return True
    except Exception:
        pass
    return False


def issue_mainchain_proof(*, final_prompt: str, reference_images: List[str], pipeline_entry: str = 'post_reply', controller: str = 'PersonaVisualController', prompt_builder: str = 'persona_image_prompt_builder', wardrobe_loader: str = 'wardrobe_loader', focus_resolver: str = 'focus_semantic_parser+focus_view_resolver', issued_by: str = DEFAULT_ISSUER, request_id: str = '', ttl_seconds: int = DEFAULT_TTL_SECONDS, chain_id: str = '', entrypoint: str = '', policy_digest: str = '', issuer_version: str = '') -> Dict[str, Any]:
    request_id = request_id or uuid.uuid4().hex
    pipeline_entry = entrypoint or pipeline_entry
    chain_id = chain_id or request_id
    issuer_version = issuer_version or 'persona_visual_mainchain_proof_v2'
    policy_digest = policy_digest or 'persona_visual_default_policy'
    prompt_hash = _sha256_text(_normalize_prompt(final_prompt))
    refs_hash = _reference_paths_sha256(reference_images)
    issued_at = int(time.time())
    expires_at = issued_at + int(ttl_seconds or DEFAULT_TTL_SECONDS)
    body = {
        'request_id': request_id,
        'chain_id': chain_id,
        'entrypoint': pipeline_entry,
        'prompt_sha256': prompt_hash,
        'reference_sha256': refs_hash,
        'policy_digest': policy_digest,
        'issued_at': issued_at,
        'expires_at': expires_at,
        'issuer_version': issuer_version,
        'one_time_use': True,
    }
    sig = _contract_sig(body)
    message = _proof_message(request_id=request_id, prompt_sha256=prompt_hash, reference_paths_sha256=refs_hash, pipeline_entry=pipeline_entry, issued_by=issued_by, controller=controller, prompt_builder=prompt_builder, expires_at=expires_at)
    token = hmac.new(_ensure_secret().encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    proof = {
        'body': body,
        'sig': sig,
        'issued_by': issued_by,
        'pipeline_entry': pipeline_entry,
        'entrypoint': pipeline_entry,
        'chain_id': chain_id,
        'policy_digest': policy_digest,
        'issuer_version': issuer_version,
        'controller': controller,
        'prompt_builder': prompt_builder,
        'wardrobe_loader': wardrobe_loader,
        'focus_resolver': focus_resolver,
        'request_id': request_id,
        'prompt_sha256': prompt_hash,
        'reference_paths_sha256': refs_hash,
        'reference_sha256': refs_hash,
        'issued_at': issued_at,
        'expires_at': expires_at,
        'proof_token': token,
    }
    reg = register_issued_proof(proof, issued_by_bridge=_called_from_bridge())
    proof['runtime_registered'] = bool(reg.get('registered'))
    proof['runtime_registration_reason'] = reg.get('reason', '')
    return proof


def validate_mainchain_proof(persona_visual_context: Optional[Dict[str, Any]], final_prompt: str, reference_images: List[str], *, require_runtime_registry: bool = False) -> Dict[str, Any]:
    ctx = persona_visual_context or {}
    proof = ctx.get('mainchain_proof') if isinstance(ctx, dict) else None
    if not isinstance(proof, dict) or not proof:
        return {'valid': False, 'reason': 'manual_pvc_provider_call_blocked'}
    request_id = str(proof.get('request_id') or '').strip()
    pipeline_entry = str(proof.get('pipeline_entry') or '').strip()
    issued_by = str(proof.get('issued_by') or '').strip()
    controller = str(proof.get('controller') or '').strip()
    prompt_builder = str(proof.get('prompt_builder') or '').strip()
    prompt_sha256 = str(proof.get('prompt_sha256') or '').strip()
    refs_sha256 = str(proof.get('reference_paths_sha256') or '').strip()
    token = str(proof.get('proof_token') or '').strip()
    try:
        expires_at = int(proof.get('expires_at') or 0)
    except Exception:
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    if not all([request_id, pipeline_entry, issued_by, controller, prompt_builder, prompt_sha256, refs_sha256, token, expires_at]):
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    if expires_at < int(time.time()):
        return {'valid': False, 'reason': 'mainchain_proof_expired'}
    if prompt_sha256 != _sha256_text(_normalize_prompt(final_prompt)) or refs_sha256 != _reference_paths_sha256(reference_images):
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    expected_message = _proof_message(request_id=request_id, prompt_sha256=prompt_sha256, reference_paths_sha256=refs_sha256, pipeline_entry=pipeline_entry, issued_by=issued_by, controller=controller, prompt_builder=prompt_builder, expires_at=expires_at)
    try:
        expected_token = hmac.new(_ensure_secret().encode('utf-8'), expected_message.encode('utf-8'), hashlib.sha256).hexdigest()
    except RuntimeError as exc:
        return {'valid': False, 'reason': 'missing_runtime_secret', 'error': str(exc)}
    if not hmac.compare_digest(token, expected_token):
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    body = proof.get('body') if isinstance(proof, dict) else None
    sig = str(proof.get('sig') or '')
    if isinstance(body, dict) and sig:
        expected_body = {
            'request_id': request_id,
            'chain_id': str(body.get('chain_id') or request_id),
            'entrypoint': pipeline_entry,
            'prompt_sha256': prompt_sha256,
            'reference_sha256': refs_sha256,
            'policy_digest': str(body.get('policy_digest') or proof.get('policy_digest') or 'persona_visual_default_policy'),
            'issued_at': int(body.get('issued_at') or proof.get('issued_at') or 0),
            'expires_at': expires_at,
            'issuer_version': str(body.get('issuer_version') or proof.get('issuer_version') or 'persona_visual_mainchain_proof_v2'),
            'one_time_use': bool(body.get('one_time_use', True)),
        }
        try:
            if not hmac.compare_digest(sig, _contract_sig(expected_body)):
                return {'valid': False, 'reason': 'invalid_contract_signature'}
        except RuntimeError as exc:
            return {'valid': False, 'reason': 'missing_runtime_secret', 'error': str(exc)}
    if require_runtime_registry:
        consumed = consume_issued_proof(proof)
        if not consumed.get('valid'):
            return {'valid': False, 'reason': consumed.get('reason') or 'mainchain_proof_not_issued_by_bridge'}
    return {'valid': True, 'reason': '', 'proof': proof}
