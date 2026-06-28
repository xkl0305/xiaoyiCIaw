from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_p = Path(__file__).resolve().parents[1] / 'seedream-image-gen' / 'skill.py'
_spec = spec_from_file_location('seedream_image_gen_skill', _p)
_mod = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
run = _mod.run
