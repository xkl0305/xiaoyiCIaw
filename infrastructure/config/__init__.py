
"""DEPRECATED shim for infrastructure.config. Real implementation lives in root config/."""
from __future__ import annotations
import importlib, sys
_MODULES = ['default_skill_config', 'resource_paths', 'feature_flags', 'runtime_modes', 'settings', 'safety_controls']
for _name in _MODULES:
    try:
        _mod = importlib.import_module(f'config.{_name}')
        sys.modules[f'{__name__}.{_name}'] = _mod
        for _attr in getattr(_mod, '__all__', []):
            globals()[_attr] = getattr(_mod, _attr)
    except Exception:
        pass
try:
    from config import *  # noqa: F401,F403
except Exception:
    pass
