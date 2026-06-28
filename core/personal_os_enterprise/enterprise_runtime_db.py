from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def project_root(root: Optional[str | Path] = None) -> Path:
    if root is not None:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[2]


def runtime_db_path(root: Optional[str | Path] = None) -> Path:
    return project_root(root) / '.openclaw' / 'state' / 'personal_os_enterprise' / 'enterprise_runtime.sqlite3'


def connect(root: Optional[str | Path] = None) -> sqlite3.Connection:
    path = runtime_db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS proof_registry ('
        'request_id TEXT NOT NULL, proof_domain TEXT NOT NULL, token_hash TEXT NOT NULL, '
        'payload_sha256 TEXT, prompt_sha256 TEXT, reference_sha256 TEXT, action_type TEXT, issuer TEXT, '
        'status TEXT NOT NULL, issued_at INTEGER, expires_at INTEGER, consumed_at INTEGER, replay_blocked_at INTEGER, metadata_json TEXT, '
        'PRIMARY KEY (request_id, proof_domain, token_hash))'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS event_ledger ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, event_type TEXT NOT NULL, chain_id TEXT, request_id TEXT, payload_json TEXT)'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS action_ledger ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, action_type TEXT, request_id TEXT, status TEXT, payload_json TEXT)'
    )
    conn.commit()


def _json(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def insert_event(event_type: str, payload: Dict[str, Any] | None = None, root: Optional[str | Path] = None) -> Dict[str, Any]:
    payload = payload or {}
    ts = int(time.time())
    with connect(root) as conn:
        cur = conn.execute(
            'INSERT INTO event_ledger(ts,event_type,chain_id,request_id,payload_json) VALUES(?,?,?,?,?)',
            (ts, str(event_type), str(payload.get('chain_id') or ''), str(payload.get('request_id') or ''), _json(payload)),
        )
        conn.commit()
        return {'ok': True, 'event_id': cur.lastrowid, 'ts': ts}


def read_events(limit: int = 100, root: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    with connect(root) as conn:
        rows = conn.execute('SELECT * FROM event_ledger ORDER BY id DESC LIMIT ?', (int(limit),)).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        rec = dict(row)
        try:
            rec['payload'] = json.loads(rec.pop('payload_json') or '{}')
        except Exception:
            rec['payload'] = {}
        out.append(rec)
    return out


def insert_proof_record(*, proof_domain: str, request_id: str, token_hash: str, status: str = 'issued', payload_sha256: str = '', prompt_sha256: str = '', reference_sha256: str = '', action_type: str = '', issuer: str = '', issued_at: int | None = None, expires_at: int | None = None, metadata: Dict[str, Any] | None = None, root: Optional[str | Path] = None) -> Dict[str, Any]:
    with connect(root) as conn:
        conn.execute(
            'INSERT OR REPLACE INTO proof_registry(request_id,proof_domain,token_hash,payload_sha256,prompt_sha256,reference_sha256,action_type,issuer,status,issued_at,expires_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (request_id, proof_domain, token_hash, payload_sha256, prompt_sha256, reference_sha256, action_type, issuer, status, issued_at or int(time.time()), expires_at or 0, _json(metadata or {})),
        )
        conn.commit()
    return {'registered': True, 'request_id': request_id, 'proof_domain': proof_domain}


def get_proof_record(*, proof_domain: str, request_id: str, token_hash: str, root: Optional[str | Path] = None) -> Dict[str, Any] | None:
    with connect(root) as conn:
        row = conn.execute('SELECT * FROM proof_registry WHERE request_id=? AND proof_domain=? AND token_hash=?', (request_id, proof_domain, token_hash)).fetchone()
    return dict(row) if row else None


def consume_proof_record(*, proof_domain: str, request_id: str, token_hash: str, root: Optional[str | Path] = None) -> Dict[str, Any]:
    now = int(time.time())
    with connect(root) as conn:
        row = conn.execute('SELECT * FROM proof_registry WHERE request_id=? AND proof_domain=? AND token_hash=?', (request_id, proof_domain, token_hash)).fetchone()
        if not row:
            return {'valid': False, 'reason': f'{proof_domain}_proof_not_issued_by_runtime_registry'}
        rec = dict(row)
        if rec.get('status') == 'consumed' or rec.get('consumed_at'):
            conn.execute('UPDATE proof_registry SET replay_blocked_at=? WHERE request_id=? AND proof_domain=? AND token_hash=?', (now, request_id, proof_domain, token_hash))
            conn.commit()
            return {'valid': False, 'reason': f'{proof_domain}_proof_replay_blocked'}
        if rec.get('expires_at') and int(rec.get('expires_at') or 0) < now:
            return {'valid': False, 'reason': f'{proof_domain}_proof_expired'}
        conn.execute('UPDATE proof_registry SET status=?, consumed_at=? WHERE request_id=? AND proof_domain=? AND token_hash=?', ('consumed', now, request_id, proof_domain, token_hash))
        conn.commit()
    return {'valid': True, 'reason': '', 'request_id': request_id}
