
from __future__ import annotations
from typing import Dict, Any
def load_online_runtime_config() -> Dict[str, Any]:
    from infrastructure.runtime_mode_resolver import resolve_runtime_mode
    resolved = resolve_runtime_mode()
    return {'online_mode': bool(resolved['online']), 'offline_mode': bool(resolved['offline']), 'no_external_api': bool(resolved['zero_external']), 'connected_runtime_always_on': False if resolved['zero_external'] else bool(resolved['online']), 'xiaoyi_capabilities_always_connected': False if resolved['zero_external'] else bool(resolved['online']), 'end_side_capabilities_always_connected': False if resolved['zero_external'] else bool(resolved['online']), 'device_bridge_always_connected': False if resolved['zero_external'] else bool(resolved['online']), 'no_per_action_online_authorization': False if resolved['zero_external'] else True, 'allow_external_providers_with_standing_consent': False if resolved['zero_external'] else bool(resolved['allow_external_api']), 'resolved': resolved}
def is_online_runtime_enabled() -> bool: return bool(load_online_runtime_config()['online_mode'])
def online_runtime_status() -> Dict[str, Any]:
    cfg = load_online_runtime_config(); cfg['online_runtime_enabled'] = is_online_runtime_enabled(); cfg['policy'] = 'zero_external_override' if cfg['no_external_api'] else 'online_connected_runtime'; return cfg
def online_allows_external_provider(provider: str = 'default') -> bool: return bool(load_online_runtime_config()['allow_external_providers_with_standing_consent'])
__all__ = ['load_online_runtime_config','is_online_runtime_enabled','online_runtime_status','online_allows_external_provider']
