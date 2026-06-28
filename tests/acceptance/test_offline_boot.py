from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_offline_boot_profile():
    oc=json.loads((ROOT/'openclaw.json').read_text(encoding='utf-8'))
    assert oc['ALLOW_NETWORK'] is False
    assert oc['NO_EXTERNAL_API'] is True
    assert oc['OFFLINE_MODE'] is True
    assert oc['ONLINE_MODE'] is False
