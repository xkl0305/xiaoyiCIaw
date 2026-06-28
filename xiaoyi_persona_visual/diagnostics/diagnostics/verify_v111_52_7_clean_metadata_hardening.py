from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.52.7_PLUS_CLEAN_METADATA_HARDENING_COMPATIBLE'


def load_json(rel: str) -> dict:
    p = ROOT / rel
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def main() -> int:
    checks = {}
    openclaw = load_json('openclaw.json')
    version = load_json('xiaoyi_persona_visual/version.json')
    release = load_json('release_manifest.json')
    hook = load_json('.openclaw/hooks/manifest.json')

    current_version = version.get('version')
    checks['version_aligned'] = (
        isinstance(current_version, str) and current_version.startswith('V111.52.') and
        release.get('version') == current_version and
        hook.get('version') == current_version and
        openclaw.get('PERSONAL_OS_ENTERPRISE_VERSION') == current_version
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
    checks['release_manifest_strict_local'] = (
        release.get('default_runtime_profile') == 'strict_local_enterprise' and
        release.get('online_mode') is False and
        release.get('no_external_api') is True and
        release.get('runtime_state_packaged') is False and
        release.get('overlay_payload_packaged_in_workspace') is False
    )
    checks['connected_runtime_is_local_private_only'] = (
        openclaw.get('connectedRuntime', {}).get('scope') == 'local_private_only' and
        openclaw.get('connectedRuntime', {}).get('alwaysConnected') is True and
        openclaw.get('connectedRuntime', {}).get('meaning') == 'local_private_runtime_always_connected_no_external_egress'
    )
    mode_policy = openclaw.get('modePolicy', {})
    checks['mode_policy_no_external_online_wording'] = (
        mode_policy.get('productRuntimeMode') == 'local_private_connected_runtime' and
        mode_policy.get('testAndPackageMode') == 'strict_local_no_external_side_effects'
    )

    profiles = {
        'always_connected_enterprise.toml': 'profile_name = "always_connected_enterprise"',
        'offline_enterprise.toml': 'profile_name = "offline_enterprise"',
        'strict_local_enterprise.toml': 'profile_name = "strict_local_enterprise"',
    }
    checks['profile_names_aligned'] = all(
        (ROOT / 'profiles' / name).exists() and expected in (ROOT / 'profiles' / name).read_text(encoding='utf-8')
        for name, expected in profiles.items()
    )

    overlay_dirs = [p for p in ROOT.glob('overlay_payload*') if p.exists()]
    checks['no_overlay_payload_residue'] = not overlay_dirs

    runtime_forbidden = []
    for rel in ['.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state', '.lazy_state', '.context_state', 'logs', 'generated-images']:
        if (ROOT / rel).exists():
            runtime_forbidden.append(rel)
    checks['no_runtime_state_dirs'] = not runtime_forbidden

    try:
        from infrastructure.packaging.source_runtime_boundary import package_clean_check
        clean = package_clean_check(ROOT)
    except Exception as exc:
        clean = {'clean': False, 'error': str(exc)}
    checks['package_clean_check_full'] = clean.get('clean') is True

    overall = all(checks.values())
    print(json.dumps({
        'overall': 'passed' if overall else 'failed',
        'version': VERSION,
        'checks': checks,
        'package_clean_summary': {
            'runtime_file_count': clean.get('runtime_file_count'),
            'forbidden_residue_count': clean.get('forbidden_residue_count'),
            'secret_literal_count': clean.get('secret_literal_count'),
            'sample_runtime_files': clean.get('runtime_files_detected', [])[:10],
            'sample_forbidden_residue': clean.get('forbidden_residue_detected', [])[:10],
            'sample_secret_literals': clean.get('secret_literals_detected', [])[:10],
            'error': clean.get('error'),
        },
        'overlay_dirs': [str(p.relative_to(ROOT)) for p in overlay_dirs[:20]],
        'runtime_forbidden': runtime_forbidden,
    }, ensure_ascii=False, indent=2))
    return 0 if overall else 1


if __name__ == '__main__':
    raise SystemExit(main())
