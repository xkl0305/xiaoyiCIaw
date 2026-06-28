from __future__ import annotations
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import sys
import argparse, json
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_p = Path(__file__).resolve().parents[1] / 'seedream-image-gen' / 'skill.py'
_spec = spec_from_file_location('seedream_image_gen_skill', _p)
_mod = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
run = _mod.run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--input-image', default='')
    ap.add_argument('--size', default='2K')
    ap.add_argument('--negative-prompt', default='')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    print(json.dumps(run(prompt=args.prompt, input_image=args.input_image, size=args.size, negative_prompt=args.negative_prompt, dry_run=args.dry_run), ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
