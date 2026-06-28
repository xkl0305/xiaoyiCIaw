from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def _check_legacy(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    result = {
        'path': str(path.relative_to(ROOT)),
        'guard_present': '_legacy_block_persona_visual_request' in text,
        'helper_present': 'def _require_requests():' in text,
        'top_level_requests_import_removed': 'import requests\n' not in text and 'from requests import' not in text,
        'callable_block_ok': False,
        'cli_block_ok': False,
        'legacy_xiaoyi_text_removed': '小艺自身形象图' not in text,
    }
    spec = importlib.util.spec_from_file_location('legacy_with_skills_check', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    blocked = mod._legacy_block_persona_visual_request('看看腿')
    result['callable_block_ok'] = bool(blocked and blocked.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline')
    proc = subprocess.run([sys.executable, '-S', str(path), '--prompt', '看看腿'], cwd=str(path.parent), capture_output=True, text=True, timeout=20)
    out = (proc.stdout or '') + (proc.stderr or '')
    result['cli_block_ok'] = 'persona_visual_request_must_use_main_pipeline' in out
    result['output_preview'] = out[:300]
    return result


def main() -> int:
    checks = {}
    failures = []
    manifest = _load_json('release_manifest.json')
    checks['version'] = manifest.get('version')
    checks['package_mode'] = manifest.get('package_mode')
    checks['with_skills_overlay_final'] = manifest.get('with_skills_overlay_final') is True
    checks['physical_skills_present'] = manifest.get('physical_skills_present') is True
    checks['legacy_guard_import_order_final'] = manifest.get('legacy_guard_import_order_final') is True
    scripts = [p for p in ROOT.rglob('generate_seedream_legacy_v11146.py') if '__pycache__' not in str(p)]
    checks['legacy_script_count'] = len(scripts)
    checks['legacy_results'] = [_check_legacy(p) for p in scripts]

    if len(scripts) < 1:
        failures.append('physical_legacy_script_missing')
    for key in ['with_skills_overlay_final', 'physical_skills_present', 'legacy_guard_import_order_final']:
        if not checks[key]:
            failures.append(key)
    for r in checks['legacy_results']:
        for key in ['guard_present', 'helper_present', 'top_level_requests_import_removed', 'callable_block_ok', 'cli_block_ok', 'legacy_xiaoyi_text_removed']:
            if not r.get(key):
                failures.append(f'{key}:{r["path"]}')

    for k, v in checks.items():
        print(f'{k}={v}')
    print('failures=' + json.dumps(failures, ensure_ascii=False))
    print(f'overall={"passed" if not failures else "failed"}')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
