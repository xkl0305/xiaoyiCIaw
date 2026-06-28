from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

MODULE_ROOT = Path(__file__).resolve().parents[1]


def _check_file(rel_path: str) -> Dict[str, Any]:
    fp = MODULE_ROOT / rel_path
    return {'name': rel_path, 'exists': fp.exists(), 'path': str(fp)}


def run_self_check() -> Dict[str, Any]:
    """Run comprehensive self-check for xiaoyi_persona_visual module.

    Checks:
    - Required files exist
    - Required config files parseable
    - Wardrobe manifest valid
    - Identity profile valid
    - Style profile valid
    - Policy files parseable
    - Controller importable
    - Router importable
    - Prompt builder importable
    - Registry importable
    """
    results = {'all_checks_passed': True, 'details': {}}
    errors = []

    # 1. Required files
    required_files = [
        'version.json',
        'config/persona_profile.json',
        'config/visual_identity_profile.json',
        'config/style_profile.json',
        'config/default_avatar_binding.json',
        'config/default_persona_visual_state.json',
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
    ]

    file_results = [_check_file(f) for f in required_files]
    missing_files = [f['name'] for f in file_results if not f['exists']]
    results['details']['required_files'] = {
        'status': 'ok' if not missing_files else 'fail',
        'total': len(required_files),
        'missing': missing_files,
    }
    if missing_files:
        errors.append(f'missing {len(missing_files)} required files')

    # 2. Config file parseability
    config_files = [
        'version.json', 'config/visual_identity_profile.json',
        'config/style_profile.json', 'config/default_avatar_binding.json',
        'wardrobe/wardrobe_manifest.json', 'wardrobe/scene_outfit_map.json',
        'wardrobe/focus_outfit_map.json',
    ]
    parse_errors = []
    for cf in config_files:
        fp = MODULE_ROOT / cf
        if fp.exists():
            try:
                json.loads(fp.read_text(encoding='utf-8'))
            except Exception as e:
                parse_errors.append(f'{cf}: {e}')
    results['details']['config_parsing'] = {
        'status': 'ok' if not parse_errors else 'fail',
        'errors': parse_errors,
    }
    if parse_errors:
        errors.extend(parse_errors)

    # 3. Policy file parseability
    policy_files = [
        'policy/visual_trigger_policy.json', 'policy/image_generation_policy.json',
        'policy/fallback_policy.json', 'policy/last_outfit_policy.json',
        'prompt/negative_prompt_guard.json',
    ]
    policy_errors = []
    for pf in policy_files:
        fp = MODULE_ROOT / pf
        if fp.exists():
            try:
                json.loads(fp.read_text(encoding='utf-8'))
            except Exception as e:
                policy_errors.append(f'{pf}: {e}')
    results['details']['policy_parsing'] = {
        'status': 'ok' if not policy_errors else 'fail',
        'errors': policy_errors,
    }
    if policy_errors:
        errors.extend(policy_errors)

    # 4. Identity profile check
    id_path = MODULE_ROOT / 'config/visual_identity_profile.json'
    if id_path.exists():
        try:
            idp = json.loads(id_path.read_text(encoding='utf-8'))
            identity_checks = {
                'character_id_set': bool(idp.get('character_id')),
                'identity_lock': bool(idp.get('identity_lock')),
                'gender_lock_female': idp.get('gender_lock') == 'female',
                'allow_gender_swap_false': idp.get('allow_gender_swap') is False,
                'negative_prompts_count': len(idp.get('required_negative_prompt', [])),
            }
            results['details']['identity_profile'] = identity_checks
            if not all(identity_checks.values()):
                errors.append('identity profile checks failed')
        except Exception as e:
            errors.append(f'identity profile error: {e}')

    # 5. Style profile check
    style_path = MODULE_ROOT / 'config/style_profile.json'
    if style_path.exists():
        try:
            sp = json.loads(style_path.read_text(encoding='utf-8'))
            style_checks = {
                'style_lock': bool(sp.get('style_lock')),
                'style_mode_fixed': sp.get('style_mode') == 'fixed',
                'default_style': sp.get('default_style') == 'anime_illustration',
            }
            results['details']['style_profile'] = style_checks
            if not all(style_checks.values()):
                errors.append('style profile checks failed')
        except Exception as e:
            errors.append(f'style profile error: {e}')

    # 6. Module importability checks
    import_checks = {}
    for mod_name, import_path in [
        ('controller', 'xiaoyi_persona_visual.controller.persona_visual_controller'),
        ('router', 'xiaoyi_persona_visual.router.visual_request_router'),
        ('prompt_builder', 'xiaoyi_persona_visual.prompt.persona_image_prompt_builder'),
        ('wardrobe_loader', 'xiaoyi_persona_visual.wardrobe.wardrobe_loader'),
        ('migration', 'xiaoyi_persona_visual.migration.migrate_persona_visual_v111_51'),
        ('registry', 'xiaoyi_persona_visual.registry.register_persona_visual'),
        ('self_check', 'xiaoyi_persona_visual.diagnostics.visual_self_check'),
    ]:
        try:
            import importlib
            mod = importlib.import_module(import_path)
            import_checks[mod_name] = {'importable': True}
        except Exception as e:
            import_checks[mod_name] = {'importable': False, 'error': str(e)}
            errors.append(f'{mod_name} import failed: {e}')
    results['details']['importability'] = import_checks

    # 7. Final summary
    results['all_checks_passed'] = len(errors) == 0
    results['error_count'] = len(errors)
    results['errors'] = errors[:10]
    return results
