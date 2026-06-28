from __future__ import annotations
import os


def test_issue(monkeypatch):
    monkeypatch.setenv('MAINCHAIN_PROOF_KEY','unit_secret')
    from xiaoyi_persona_visual.policy.mainchain_proof import issue_mainchain_proof
    proof=issue_mainchain_proof(request_id='r1', chain_id='c1', entrypoint='test', final_prompt='hello', reference_images=['a.png'], policy_digest='p', issuer_version='test')
    assert proof and (proof.get('sig') or proof.get('proof_token') or proof.get('token') or proof.get('body'))


def test_replay():
    from core.personal_os_enterprise.side_effect_registry import register_issued_proof, consume_issued_proof
    token='tok-replay-unit'
    register_issued_proof('req-replay', token, 'payload', root=None)
    assert consume_issued_proof('req-replay', token, root=None).get('ok') is True
    assert consume_issued_proof('req-replay', token, root=None).get('ok') is False


def test_manual_provider_call_blocked():
    from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
    r=persona_image_provider_chain_status({})
    assert r['status']=='blocked'
    assert r['external_fallback_allowed'] is False
