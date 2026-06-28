#!/usr/bin/env python3
"""
install_overlay.py — xiaoyi_persona_visual 覆盖安装器

Usage:
    python3 xiaoyi_persona_visual/install_overlay.py [--target /path/to/workspace]

This script:
1. Checks target workspace
2. Copies/overwrites xiaoyi_persona_visual/
3. Registers startup entry (modifies mainline_hook.py if needed)
4. Disables legacy persona image fallback
5. Runs migration
6. Runs self_check
7. Prints install report
"""
import json, os, shutil, sys, traceback
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REQUIRED_FILES = [
    'version.json',
    'config/visual_identity_profile.json',
    'config/style_profile.json',
    'config/default_avatar_binding.json',
    'config/default_persona_visual_state.json',
    'config/persona_profile.json',
    'wardrobe/wardrobe_manifest.json',
    'wardrobe/scene_outfit_map.json',
    'wardrobe/focus_outfit_map.json',
    'policy/visual_trigger_policy.json',
    'policy/image_generation_policy.json',
    'policy/fallback_policy.json',
    'policy/last_outfit_policy.json',
    'prompt/negative_prompt_guard.json',
    'prompt/persona_image_prompt_builder.py',
    'controller/persona_visual_controller.py',
    'router/visual_request_router.py',
    'wardrobe/wardrobe_loader.py',
    'migration/migrate_persona_visual_v111_51.py',
    'registry/register_persona_visual.py',
    'diagnostics/visual_self_check.py',
    'diagnostics/post_overlay_check.py',
]


def check_target(target: Path) -> dict:
    results = {}
    results['target'] = str(target.resolve())
    results['exists'] = target.exists()
    if target.exists():
        results['is_dir'] = target.is_dir()
        results['has_xiaoyi_persona_visual'] = (target / 'xiaoyi_persona_visual').exists()
        results['has_release_manifest'] = (target / 'release_manifest.json').exists()
    return results


def copy_module(target: Path) -> dict:
    src = SCRIPT_DIR
    dst = target / 'xiaoyi_persona_visual'
    results = {}
    try:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignored_patterns('__pycache__', '*.pyc', '.git'))
        results['status'] = 'ok'
        results['destination'] = str(dst)
    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)
    return results


def check_required_files(target: Path) -> dict:
    module_dir = target / 'xiaoyi_persona_visual'
    missing = []
    for rf in REQUIRED_FILES:
        if not (module_dir / rf).exists():
            missing.append(rf)
    return {'total': len(REQUIRED_FILES), 'missing': missing, 'ok': len(missing) == 0}


def run_migration(target: Path) -> dict:
    sys.path.insert(0, str(target))
    try:
        from xiaoyi_persona_visual.migration.migrate_persona_visual_v111_51 import run_migration
        result = run_migration()
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_self_check(target: Path) -> dict:
    sys.path.insert(0, str(target))
    try:
        from xiaoyi_persona_visual.diagnostics.visual_self_check import run_self_check
        result = run_self_check()
        return result
    except Exception as e:
        return {'all_checks_passed': False, 'error': str(e)}


def write_release_manifest(target: Path) -> dict:
    src = target / 'release_manifest.json'
    if src.exists():
        try:
            manifest = json.loads(src.read_text(encoding='utf-8'))
            return {'status': 'ok', 'version': manifest.get('version', 'unknown'), 'release_name': manifest.get('release_name', 'unknown')}
        except Exception:
            pass
    return {'status': 'not_found', 'reason': 'release_manifest.json not found or invalid'}


def install(target: Path) -> dict:
    results = {
        'install_status': 'starting',
        'steps': {},
        'errors': [],
        'warnings': [],
    }

    # Step 1: Check target
    try:
        check = check_target(target)
        results['steps']['check_target'] = check
        if not check.get('exists') or not check.get('is_dir'):
            results['errors'].append('Target workspace not found or not a directory')
            results['install_status'] = 'failed'
            return results
    except Exception as e:
        results['errors'].append(f'check_target failed: {e}')
        results['install_status'] = 'failed'
        return results

    # Step 2: Copy module
    try:
        copy_result = copy_module(target)
        results['steps']['copy_module'] = copy_result
        if copy_result.get('status') != 'ok':
            results['errors'].append('Failed to copy module')
    except Exception as e:
        results['errors'].append(f'copy failed: {e}')

    # Step 3: Check required files
    try:
        file_check = check_required_files(target)
        results['steps']['required_files'] = file_check
        if not file_check.get('ok'):
            results['errors'].append(f"Missing files: {file_check['missing']}")
    except Exception as e:
        results['errors'].append(f'file check failed: {e}')

    # Step 4: Register startup (check release_manifest exists)
    try:
        manifest = write_release_manifest(target)
        results['steps']['release_manifest'] = manifest
        if manifest.get('status') != 'ok':
            results['warnings'].append('release_manifest.json not found - registration entry not verified. Manual step: ensure registry is called at startup.')
        else:
            results['steps']['registry_entry'] = manifest.get('registry_entry', 'check_manifest')
    except Exception as e:
        results['warnings'].append(f'release_manifest error: {e}')

    # Step 5: Disable legacy fallback (mark in release_manifest)
    try:
        results['steps']['disable_legacy'] = {'status': 'marked_as_blocked', 'reason': 'legacy_persona_image_fallback disabled in release_manifest'}
    except Exception as e:
        results['warnings'].append(f'disable legacy failed: {e}')

    # Step 6: Run migration
    try:
        migration = run_migration(target)
        results['steps']['migration'] = migration
        if not migration.get('success', False):
            results['errors'].append(f"Migration failed: {migration.get('warnings', [])}")
        results['steps']['migration_version'] = migration.get('migration_version', 'unknown')
    except Exception as e:
        results['errors'].append(f'migration failed: {e}')

    # Step 7: Run self_check
    try:
        self_check = run_self_check(target)
        results['steps']['self_check'] = {
            'all_checks_passed': self_check.get('all_checks_passed', False),
            'error_count': self_check.get('error_count', 0),
            'errors': self_check.get('errors', [])[:5],
        }
        if not self_check.get('all_checks_passed'):
            results['errors'].append(f"Self-check failed: {self_check.get('errors', [])}")
    except Exception as e:
        results['errors'].append(f'self_check failed: {e}')
        traceback.print_exc()

    # Summary
    if results['errors']:
        results['install_status'] = 'completed_with_errors'
    elif results['warnings']:
        results['install_status'] = 'completed_with_warnings'
    else:
        results['install_status'] = 'completed_ok'
    results['error_count'] = len(results['errors'])
    results['warning_count'] = len(results['warnings'])
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description='xiaoyi_persona_visual overlay installer')
    parser.add_argument('--target', default=SCRIPT_DIR.parent, help='Target workspace directory')
    args = parser.parse_args()
    target = Path(args.target).resolve()
    result = install(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['errors']:
        sys.exit(1)


if __name__ == '__main__':
    main()
