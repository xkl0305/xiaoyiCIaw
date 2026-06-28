
from __future__ import annotations
import importlib.util
from pathlib import Path
_target = Path(__file__).resolve().parents[1] / 'safety_governor' / 'risk_levels.py'
_spec = importlib.util.spec_from_file_location('_v11135_risk_levels_impl', _target)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
for _name in dir(_mod):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_mod, _name)
