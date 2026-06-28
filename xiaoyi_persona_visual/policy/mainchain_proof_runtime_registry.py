from __future__ import annotations

import hashlib
from typing import Any, Dict

from core.personal_os_enterprise.enterprise_runtime_db import insert_proof_record, consume_proof_record, get_proof_record

_VALID_ISSUERS = {'persona_visual_auto_generation_bridge'}
_IN_MEMORY: Dict[str, Dict[str, Any]] = {}


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def _key(request_id: str, proof_token: str) -> str:
    return f'{request_id}:{_token_hash(proof_token)}'


def register_issued_proof(proof: Dict[str, Any], *, issued_by_bridge: bool = False, root=None) -> Dict[str, Any]:
    if not issued_by_bridge:
        return {'registered': False, 'reason': 'not_bridge_issued'}
    if str(proof.get('issued_by') or '') not in _VALID_ISSUERS:
        return {'registered': False, 'reason': 'invalid_issuer'}
    request_id = str(proof.get('request_id') or '').strip()
    proof_token = str(proof.get('proof_token') or '').strip()
    if not request_id or not proof_token:
        return {'registered': False, 'reason': 'missing_request_or_token'}
    h = _token_hash(proof_token)
    rec = {
        'request_id': request_id,
        'proof_token_hash': h,
        'prompt_sha256': proof.get('prompt_sha256'),
        'reference_paths_sha256': proof.get('reference_paths_sha256'),
        'issued_by': proof.get('issued_by'),
        'issued_at': proof.get('issued_at'),
        'expires_at': proof.get('expires_at'),
        'consumed': False,
    }
    _IN_MEMORY[_key(request_id, proof_token)] = rec
    insert_proof_record(
        proof_domain='mainchain',
        request_id=request_id,
        token_hash=h,
        prompt_sha256=str(proof.get('prompt_sha256') or ''),
        reference_sha256=str(proof.get('reference_paths_sha256') or ''),
        issuer=str(proof.get('issued_by') or ''),
        issued_at=int(proof.get('issued_at') or 0),
        expires_at=int(proof.get('expires_at') or 0),
        metadata={'pipeline_entry': proof.get('pipeline_entry')},
        root=root,
    )
    return {'registered': True, 'reason': '', 'request_id': request_id}


def consume_issued_proof(proof: Dict[str, Any], *, root=None) -> Dict[str, Any]:
    request_id = str(proof.get('request_id') or '').strip()
    proof_token = str(proof.get('proof_token') or '').strip()
    if not request_id or not proof_token:
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    k = _key(request_id, proof_token)
    rec = _IN_MEMORY.get(k)
    if rec and rec.get('consumed'):
        return {'valid': False, 'reason': 'mainchain_proof_replay_blocked'}
    if rec and (rec.get('prompt_sha256') != proof.get('prompt_sha256') or rec.get('reference_paths_sha256') != proof.get('reference_paths_sha256')):
        return {'valid': False, 'reason': 'invalid_mainchain_proof'}
    result = consume_proof_record(proof_domain='mainchain', request_id=request_id, token_hash=_token_hash(proof_token), root=root)
    if not result.get('valid'):
        reason = result.get('reason') or 'mainchain_proof_not_issued_by_bridge'
        if reason == 'mainchain_proof_not_issued_by_runtime_registry':
            reason = 'mainchain_proof_not_issued_by_bridge'
        return {'valid': False, 'reason': reason}
    if rec:
        rec['consumed'] = True
        _IN_MEMORY[k] = rec
    return {'valid': True, 'reason': '', 'request_id': request_id}
