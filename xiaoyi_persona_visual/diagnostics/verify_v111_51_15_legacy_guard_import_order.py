from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.51.20_MAINCHAIN_PROOF_TAIL_ANCHOR_FINAL'


def _load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def _check_legacy_file(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    result = {
        'path': str(path.relative_to(ROOT)),
        'guard_present': '_legacy_block_persona_visual_request' in text,
        'top_level_requests_import_removed': 'import requests\n' not in text and 'from requests import' not in text,
        'cli_guard_present': '_legacy_cli_text' in text or 'raise SystemExit(0)' in text,
        'callable_block_ok': False,
        'subprocess_block_ok': False,
        'output_preview': '',
    }
    try:
        spec = importlib.util.spec_from_file_location('legacy_check_v111_51_15', path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        blocked = mod._legacy_block_persona_visual_request('看看腿')
        result['callable_block_ok'] = bool(blocked and blocked.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline')
    except Exception as e:
        result['callable_error'] = repr(e)
    try:
        proc = subprocess.run(
            [sys.executable, '-S', str(path), '--prompt', '看看腿'],
            cwd=str(path.parent), capture_output=True, text=True, timeout=20,
        )
        out = (proc.stdout or '') + (proc.stderr or '')
        result['output_preview'] = out[:500]
        result['subprocess_block_ok'] = 'persona_visual_request_must_use_main_pipeline' in out or '拒绝' in out
    except Exception as e:
        result['subprocess_error'] = repr(e)
    return result


def main() -> int:
    checks = {}
    failures = []

    for rel in ['release_manifest.json', 'xiaoyi_persona_visual/version.json', '.openclaw/hooks/manifest.json']:
        try:
            obj = _load_json(rel)
            checks[f'{rel}:version'] = obj.get('version')
            if obj.get('version') != VERSION:
                failures.append(f'version_not_unified:{rel}:{obj.get("version")}')
        except Exception as e:
            failures.append(f'cannot_read_version:{rel}:{e}')
    try:
        oc = _load_json('openclaw.json')
        checks['openclaw_personaVisual_version'] = oc.get('personaVisual', {}).get('version')
        if oc.get('personaVisual', {}).get('version') != VERSION:
            failures.append('openclaw_personaVisual_version_not_unified')
    except Exception as e:
        failures.append(f'cannot_read_openclaw:{e}')

    manifest = _load_json('release_manifest.json')
    checks['manifest_legacy_guard_import_order_final'] = manifest.get('legacy_guard_import_order_final') is True
    checks['manifest_legacy_guard_before_imports'] = manifest.get('legacy_guard_runs_before_provider_imports') is True
    checks['manifest_no_requests_dependency'] = manifest.get('legacy_guard_blocks_without_requests_dependency') is True
    for key in ['manifest_legacy_guard_import_order_final', 'manifest_legacy_guard_before_imports', 'manifest_no_requests_dependency']:
        if not checks[key]:
            failures.append(key)

    scripts = [p for p in ROOT.rglob('generate_seedream_legacy_v11146.py') if '__pycache__' not in str(p)]
    checks['legacy_script_count'] = len(scripts)
    checks['legacy_absent_is_ok_for_no_skills'] = len(scripts) == 0
    legacy_results = [_check_legacy_file(p) for p in scripts]
    checks['legacy_results'] = legacy_results
    for r in legacy_results:
        if not r.get('guard_present'):
            failures.append(f'legacy_guard_missing:{r["path"]}')
        if not r.get('top_level_requests_import_removed'):
            failures.append(f'legacy_top_level_requests_import_still_present:{r["path"]}')
        if not r.get('callable_block_ok'):
            failures.append(f'legacy_callable_did_not_block:{r["path"]}')
        # subprocess may not be meaningful for non-CLI scripts; only fail if CLI guard is present but did not block.
        if r.get('cli_guard_present') and not r.get('subprocess_block_ok'):
            failures.append(f'legacy_cli_did_not_block:{r["path"]}')

    for k, v in checks.items():
        print(f'{k}={v}')
    print('failures=' + json.dumps(failures, ensure_ascii=False))
    print(f'overall={"passed" if not failures else "failed"}')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
