from __future__ import annotations

from typing import Dict, List

VERSION = "V111.52.13_ENTERPRISE_REPORT_REMAINING_CLOSE_FINAL"
ALLOWED_LOCAL_PERSONA_IMAGE_PROVIDERS = [
    'local_flux_identity_provider',
    'local_sdxl_identity_provider',
    'local_basic_img2img_provider',
]


def persona_image_provider_chain_status(configured: Dict[str, bool] | None = None) -> Dict[str, object]:
    configured = configured or {}
    attempts: List[Dict[str, str]] = []
    for name in ALLOWED_LOCAL_PERSONA_IMAGE_PROVIDERS:
        if configured.get(name):
            return {'ok': True, 'version': VERSION, 'selected_provider': name, 'external_fallback_allowed': False}
        attempts.append({'provider': name, 'reason': 'not_configured'})
    return {
        'ok': False,
        'version': VERSION,
        'status': 'blocked',
        'blocked_reason': 'all_local_persona_image_providers_not_configured',
        'provider_attempts': attempts,
        'external_fallback_allowed': False,
        'fail_closed': True,
    }
