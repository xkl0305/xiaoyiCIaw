
"""Compatibility shim for domain.tasks."""
from __future__ import annotations
import importlib, sys
_specs = importlib.import_module('core.domain.tasks.specs')
sys.modules[__name__ + '.specs'] = _specs
try:
    _sm = importlib.import_module('core.domain.tasks.state_machine')
    sys.modules[__name__ + '.state_machine'] = _sm
except Exception:
    pass
for _name in dir(_specs):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_specs, _name)
try:
    __all__ = list(_specs.__all__)  # type: ignore[attr-defined]
except Exception:
    __all__ = [n for n in globals() if not n.startswith('_')]
