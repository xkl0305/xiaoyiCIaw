from __future__ import annotations
import time
from pathlib import Path
from core.personal_os_enterprise.send_guard import validate_artifact_for_send

def test_stale_file(tmp_path):
    p=tmp_path/'old.png'; p.write_bytes(b'x')
    started=time.time()+10
    r=validate_artifact_for_send(path=str(p), generation_started_at=started, request_id='r', expected_request_id='r')
    assert r['blocked_send'] is True

def test_missing_file(tmp_path):
    r=validate_artifact_for_send(path=str(tmp_path/'missing.png'), generation_started_at=time.time(), request_id='r', expected_request_id='r')
    assert r['blocked_send'] is True
