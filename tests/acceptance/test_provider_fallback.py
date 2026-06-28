from __future__ import annotations
from core.personal_os_enterprise.local_persona_image_domain import persona_image_provider_chain_status
from core.personal_os_enterprise.local_providers import _endpoint_allowed

def test_domain_fallback():
    assert persona_image_provider_chain_status({})['blocked_reason']=='all_local_persona_image_providers_not_configured'
    assert persona_image_provider_chain_status({'local_sdxl_identity_provider': True})['selected_provider']=='local_sdxl_identity_provider'

def test_transport_fallback():
    assert _endpoint_allowed('http://127.0.0.1:8000/v1/chat/completions') is True
    assert _endpoint_allowed('https://example.com/v1/chat/completions') is False
