from __future__ import annotations
import yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_tail_root_attachment():
    p=ROOT/'xiaoyi_persona_visual/policy/body_schema.yaml'
    assert p.exists()
    text=p.read_text(encoding='utf-8')
    assert 'tailbone' in text or 'sacrum' in text or '后腰' in text
    assert 'floating' in text or '漂浮' in text
