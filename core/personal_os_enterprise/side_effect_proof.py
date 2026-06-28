from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional

from . import SYSTEM_VERSION
from .runtime_secret_provider import require_secret

PROOF_VERSION = "side_effect_proof_v1"


def canonical_payload(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def payload_sha256(payload: Any) -> str:
    return sha256_text(canonical_payload(payload))


def _message(proof: Dict[str, Any]) -> str:
    fields = [
        proof.get("request_id", ""),
        proof.get("action_type", ""),
        proof.get("payload_sha256", ""),
        proof.get("risk_level", ""),
        proof.get("entrypoint", ""),
        proof.get("issuer", ""),
        str(proof.get("issued_at", "")),
        str(proof.get("expires_at", "")),
        proof.get("system_version", ""),
    ]
    return "|".join(map(str, fields))


def _token(proof: Dict[str, Any], root=None) -> str:
    secret = require_secret('default', 'side_effect_proof', root=root)
    return hmac.new(secret.encode("utf-8"), _message(proof).encode("utf-8"), hashlib.sha256).hexdigest()


def issue_side_effect_proof(
    *,
    action_type: str,
    payload: Any = None,
    risk_level: str = "low",
    entrypoint: str = "mainline",
    issuer: str = "personal_os_enterprise_core",
    ttl_seconds: int = 300,
    request_id: Optional[str] = None,
    root=None,
) -> Dict[str, Any]:
    now = int(time.time())
    proof = {
        "proof_version": PROOF_VERSION,
        "system_version": SYSTEM_VERSION,
        "request_id": request_id or uuid.uuid4().hex,
        "action_type": str(action_type),
        "payload_sha256": payload_sha256(payload),
        "risk_level": str(risk_level or "low"),
        "entrypoint": str(entrypoint or "mainline"),
        "issuer": str(issuer or "personal_os_enterprise_core"),
        "issued_at": now,
        "expires_at": now + int(ttl_seconds or 300),
    }
    proof["proof_token"] = _token(proof, root=root)
    return proof


def validate_side_effect_proof(proof: Optional[Dict[str, Any]], *, action_type: str, payload: Any = None, root=None) -> Dict[str, Any]:
    if not isinstance(proof, dict) or not proof:
        return {"valid": False, "reason": "missing_side_effect_proof"}
    if proof.get("proof_version") != PROOF_VERSION:
        return {"valid": False, "reason": "unsupported_proof_version"}
    if proof.get("system_version") != SYSTEM_VERSION:
        return {"valid": False, "reason": "system_version_mismatch"}
    if proof.get("action_type") != action_type:
        return {"valid": False, "reason": "action_type_mismatch"}
    if proof.get("payload_sha256") != payload_sha256(payload):
        return {"valid": False, "reason": "payload_hash_mismatch"}
    try:
        expires_at = int(proof.get("expires_at", 0))
    except Exception:
        return {"valid": False, "reason": "invalid_expiry"}
    if expires_at < int(time.time()):
        return {"valid": False, "reason": "proof_expired"}
    expected = _token(proof, root=root)
    if not hmac.compare_digest(str(proof.get("proof_token", "")), expected):
        return {"valid": False, "reason": "invalid_proof_token"}
    return {"valid": True, "reason": "", "proof": proof}


def issue_registered_side_effect_proof(
    *,
    action_type: str,
    payload: Any = None,
    risk_level: str = "low",
    entrypoint: str = "mainline",
    issuer: str = "personal_os_enterprise_core",
    ttl_seconds: int = 300,
    request_id: Optional[str] = None,
    root=None,
) -> Dict[str, Any]:
    """Issue a side-effect proof and register it for one-time consumption.

    This is the canonical V111.52.3 issuance path. Hand-written proofs or proofs
    issued without registry registration are not accepted by action_guard.
    """
    from .side_effect_registry import register_issued_proof
    from .observability_event_bus import emit_event

    proof = issue_side_effect_proof(
        action_type=action_type,
        payload=payload,
        risk_level=risk_level,
        entrypoint=entrypoint,
        issuer=issuer,
        ttl_seconds=ttl_seconds,
        request_id=request_id,
        root=root,
    )
    reg = register_issued_proof(proof, root=root)
    emit_event(
        "side_effect_proof_issued",
        {
            "request_id": proof.get("request_id"),
            "action_type": action_type,
            "risk_level": risk_level,
            "registered": bool(reg.get("registered")),
            "reason": reg.get("reason", ""),
        },
        root=root,
    )
    proof["registry_registered"] = bool(reg.get("registered"))
    return proof
