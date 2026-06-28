from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

from .enterprise_runtime_db import insert_proof_record, consume_proof_record, get_proof_record


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def _payload_hash(payload: Any) -> str:
    if payload is None:
        return ''
    if isinstance(payload, str) and len(payload) == 64 and all(c in '0123456789abcdefABCDEF' for c in payload):
        return payload.lower()
    return hashlib.sha256(str(payload).encode('utf-8')).hexdigest()


def _normalize_proof(proof_or_request_id: Dict[str, Any] | str, token: Optional[str] = None, payload: Any = None) -> Dict[str, Any]:
    """Accept both the current proof-dict API and the older positional API.

    The older tests and some overlay scripts call:
        register_issued_proof(request_id, token, payload)
        consume_issued_proof(request_id, token)
    Keeping this compatibility makes the replay contract stable while the
    canonical code path remains proof-dict based.
    """
    if isinstance(proof_or_request_id, dict):
        return dict(proof_or_request_id)
    now = int(time.time())
    return {
        'request_id': str(proof_or_request_id or '').strip(),
        'proof_token': str(token or '').strip(),
        'payload_sha256': _payload_hash(payload),
        'action_type': 'compat_side_effect',
        'issuer': 'compat_registry_api',
        'issued_at': now,
        'expires_at': now + 300,
        'entrypoint': 'compat',
        'risk_level': 'low',
    }


def register_issued_proof(proof: Dict[str, Any] | str, token: Optional[str] = None, payload: Any = None, *, root=None) -> Dict[str, Any]:
    proof_obj = _normalize_proof(proof, token, payload)
    request_id = str(proof_obj.get('request_id') or '').strip()
    token_value = str(proof_obj.get('proof_token') or proof_obj.get('token') or '').strip()
    if not request_id or not token_value:
        return {'registered': False, 'ok': False, 'reason': 'missing_request_or_token'}
    result = insert_proof_record(
        proof_domain='side_effect',
        request_id=request_id,
        token_hash=_token_hash(token_value),
        payload_sha256=str(proof_obj.get('payload_sha256') or ''),
        action_type=str(proof_obj.get('action_type') or ''),
        issuer=str(proof_obj.get('issuer') or ''),
        issued_at=int(proof_obj.get('issued_at') or 0),
        expires_at=int(proof_obj.get('expires_at') or 0),
        metadata={'risk_level': proof_obj.get('risk_level'), 'entrypoint': proof_obj.get('entrypoint')},
        root=root,
    )
    result['ok'] = bool(result.get('registered'))
    return result


def consume_issued_proof(proof: Dict[str, Any] | str, token: Optional[str] = None, *, root=None) -> Dict[str, Any]:
    proof_obj = _normalize_proof(proof, token)
    request_id = str(proof_obj.get('request_id') or '').strip()
    token_value = str(proof_obj.get('proof_token') or proof_obj.get('token') or '').strip()
    if not request_id or not token_value:
        return {'valid': False, 'ok': False, 'reason': 'missing_request_or_token'}
    result = consume_proof_record(proof_domain='side_effect', request_id=request_id, token_hash=_token_hash(token_value), root=root)
    if result.get('reason') == 'side_effect_proof_not_issued_by_runtime_registry':
        result['reason'] = 'side_effect_proof_not_registered'
    if result.get('reason') == 'side_effect_proof_replay_blocked':
        result['reason'] = 'side_effect_proof_replay_blocked'
    result['ok'] = bool(result.get('valid'))
    return result
