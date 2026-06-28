from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.9_LOCAL_CAPABILITY_CLEAN_CLOSE_FINAL'


def load_json(rel: str) -> dict:
    p = ROOT / rel
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def main() -> int:
    checks = {}
    openclaw = load_json('openclaw.json')
    version = load_json('xiaoyi_persona_visual/version.json')
    release = load_json('release_manifest.json')
    hook = load_json('.openclaw/hooks/manifest.json')

    def _compatible(v: str) -> bool:
        return v == VERSION or str(v).startswith('V111.52.10') or str(v).startswith('V111.52.11')
    checks['version_aligned'] = (
        _compatible(version.get('version')) and
        _compatible(release.get('version')) and
        _compatible(hook.get('version')) and
        _compatible(openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION'))
    )
    checks['strict_local_profile'] = (
        openclaw.get('ALLOW_NETWORK') is False and
        openclaw.get('NO_EXTERNAL_API') is True and
        openclaw.get('OFFLINE_MODE') is True and
        openclaw.get('ONLINE_MODE') is False and
        openclaw.get('ZERO_EXTERNAL_MODE') is True and
        openclaw.get('NO_REAL_PAYMENT') is True and
        openclaw.get('NO_REAL_SEND') is True
    )
    checks['release_manifest_post_overlay_compatible'] = (
        release.get('seedream_provider_direct', {}).get('physical_skill_required') is False and
        release.get('package_mode') == 'strict_local_no_skills_physical_skill_not_required'
    )
    checks['release_manifest_strict_local'] = (
        release.get('default_runtime_profile') == 'strict_local_enterprise' and
        release.get('online_mode') is False and
        release.get('no_external_api') is True and
        release.get('runtime_state_packaged') is False and
        release.get('overlay_payload_packaged_in_workspace') is False
    )
    checks['local_capability_runtime_fusion_still_enabled'] = (
        openclaw.get('LOCAL_CAPABILITY_RUNTIME_FUSION') is True and
        version.get('features', {}).get('local_capability_runtime_fusion') is True and
        release.get('local_capability_runtime_fusion') is True
    )
    forbidden_dirs = [p.name for p in ROOT.iterdir() if p.is_dir() and (p.name.startswith('_overlay') or p.name.startswith('overlay_payload'))]
    checks['no_overlay_or_work_dirs'] = not forbidden_dirs
    runtime_dirs = [rel for rel in ['.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state', '.lazy_state', '.context_state', 'logs', 'generated-images'] if (ROOT / rel).exists()]
    checks['no_runtime_state_dirs'] = not runtime_dirs
    try:
        from infrastructure.packaging.source_runtime_boundary import package_clean_check
        clean = package_clean_check(ROOT)
    except Exception as exc:
        clean = {'clean': False, 'error': str(exc)}
    checks['package_clean_check_full'] = clean.get('clean') is True
    checks['source_runtime_boundary_detects_overlay'] = True
    try:
        from infrastructure.packaging.source_runtime_boundary import is_forbidden_source_residue, is_runtime_path
        checks['source_runtime_boundary_detects_overlay'] = (
            is_forbidden_source_residue('_overlay9/a.txt') and
            is_forbidden_source_residue('overlay_payload_v111_52_8/a.txt') and
            is_runtime_path('logs/x.log') and
            is_runtime_path('.v98_state/mainline_hook_heartbeat.jsonl')
        )
    except Exception:
        checks['source_runtime_boundary_detects_overlay'] = False

    overall = all(checks.values())
    print(json.dumps({
        'overall': 'passed' if overall else 'failed',
        'version': VERSION,
        'checks': checks,
        'package_clean_summary': {
            'runtime_file_count': clean.get('runtime_file_count'),
            'forbidden_residue_count': clean.get('forbidden_residue_count'),
            'secret_literal_count': clean.get('secret_literal_count'),
            'sample_runtime_files': clean.get('runtime_files_detected', [])[:20],
            'sample_forbidden_residue': clean.get('forbidden_residue_detected', [])[:20],
            'sample_secret_literals': clean.get('secret_literals_detected', [])[:20],
            'error': clean.get('error'),
        },
        'forbidden_dirs': forbidden_dirs[:20],
        'runtime_dirs': runtime_dirs,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
