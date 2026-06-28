from __future__ import annotations

# Compatibility facade: old code imported offline_profile directly.
# V111.52.1 keeps this module, but action_guard defaults to always_connected_enterprise.

from .runtime_profile import (  # noqa: F401
    DEFAULT_ALWAYS_CONNECTED_ENTERPRISE_PROFILE,
    DEFAULT_ENTERPRISE_PROFILE,
    DEFAULT_OFFLINE_ENTERPRISE_PROFILE,
    connector_prompt_policy,
    is_network_allowed,
    load_enterprise_profile,
    load_offline_profile,
)
