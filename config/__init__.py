
"""Canonical configuration namespace. Real config implementation lives here after V111.36."""
try:
    from .settings import *  # noqa: F401,F403
except Exception: pass
try:
    from .feature_flags import *  # noqa: F401,F403
except Exception: pass
try:
    from .safety_controls import *  # noqa: F401,F403
except Exception: pass
try:
    from .resource_paths import *  # noqa: F401,F403
except Exception: pass
try:
    from .runtime_modes import *  # noqa: F401,F403
except Exception: pass
try:
    from .default_skill_config import *  # noqa: F401,F403
except Exception: pass
