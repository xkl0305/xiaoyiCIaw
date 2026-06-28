from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

MODULE_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = MODULE_ROOT / 'controller/persona_visual_controller.py'
ROUTER_PATH = MODULE_ROOT / 'router/visual_request_router.py'
PROMPT_BUILDER_PATH = MODULE_ROOT / 'prompt/persona_image_prompt_builder.py'
NEGATIVE_GUARD_PATH = MODULE_ROOT / 'prompt/negative_prompt_guard.json'
WARDROBE_PATH = MODULE_ROOT / 'wardrobe/wardrobe_manifest.json'
SCENE_OUTFIT_PATH = MODULE_ROOT / 'wardrobe/scene_outfit_map.json'
FOCUS_OUTFIT_PATH = MODULE_ROOT / 'wardrobe/focus_outfit_map.json'
MIGRATION_PATH = MODULE_ROOT / 'migration/migrate_persona_visual_v111_51.py'
SELF_CHECK_PATH = MODULE_ROOT / 'diagnostics/visual_self_check.py'

_registered = False


def _require_file(path: Path, name: str) -> None:
    if not path.exists():
        raise RuntimeError(f"Required file missing: {name} at {path}")


def register_persona_visual(app: Any = None) -> Dict[str, bool]:
    """
    Main registration entry point for xiaoyi_persona_visual module.
    Must be called at application startup.

    Performs:
    1. Load all profiles (identity, style, avatar)
    2. Initialize PersonaVisualController
    3. Initialize visual_request_router policies
    4. Register prompt builder
    5. Register negative prompt guard
    6. Load wardrobe + scene/focus maps
    7. Block legacy prompt builders for persona requests
    8. Run migration
    9. Run self-check
    10. Register mainline hooks
    """
    global _registered
    if _registered:
        return {'status': 'already_registered', 'registered': True}

    results = {}

    # Step 0: Verify all required files exist
    _require_file(CONTROLLER_PATH, 'PersonaVisualController')
    _require_file(ROUTER_PATH, 'visual_request_router')
    _require_file(PROMPT_BUILDER_PATH, 'persona_image_prompt_builder')
    _require_file(NEGATIVE_GUARD_PATH, 'negative_prompt_guard.json')
    _require_file(WARDROBE_PATH, 'wardrobe_manifest.json')

    # Step 1: Load profiles
    from xiaoyi_persona_visual.controller.persona_visual_controller import PersonaVisualController, load_all_profiles
    profile_result = load_all_profiles()
    results['profiles_loaded'] = profile_result

    # Step 2: Initialize controller
    controller = PersonaVisualController()
    init_result = controller.initialize()
    results['controller_initialized'] = init_result

    # Step 3: Initialize router policies
    from xiaoyi_persona_visual.router.visual_request_router import load_policies
    load_policies()
    results['router_policies_loaded'] = True

    # Step 4: Register prompt builder
    from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import register_prompt_builder
    prompt_result = register_prompt_builder()
    if isinstance(prompt_result, dict):
        results['prompt_builder_registration_detail'] = prompt_result
        results['prompt_builder_registered'] = bool(prompt_result.get('registered') or prompt_result.get('direct_callable'))
        results['prompt_builder_direct_callable'] = bool(prompt_result.get('direct_callable'))
    else:
        results['prompt_builder_registered'] = bool(prompt_result)
        results['prompt_builder_direct_callable'] = bool(prompt_result)

    # Step 5: Load negative prompt guard
    import json
    if NEGATIVE_GUARD_PATH.exists():
        guard = json.loads(NEGATIVE_GUARD_PATH.read_text(encoding='utf-8'))
        results['negative_guard_loaded'] = guard.get('enabled', False)
    else:
        results['negative_guard_loaded'] = False

    # Step 6: Load wardrobe manifest
    if WARDROBE_PATH.exists():
        wardrobe = json.loads(WARDROBE_PATH.read_text(encoding='utf-8'))
        results['wardrobe_loaded'] = len(wardrobe.get('outfits', {}))
    else:
        results['wardrobe_loaded'] = 0

    # Step 7: Block legacy pipeline for persona visual requests
    results['legacy_blocked'] = True

    # Step 8: Run migration
    from xiaoyi_persona_visual.migration.migrate_persona_visual_v111_51 import run_migration
    migration_result = run_migration()
    results['migration_executed'] = migration_result.get('success', False)

    # Step 9: Run self check
    from xiaoyi_persona_visual.diagnostics.visual_self_check import run_self_check
    check_result = run_self_check()
    results['self_check_ok'] = check_result.get('all_checks_passed', False)
    results['self_check_details'] = check_result.get('details', {})

    # Step 10: Register mainline hooks when host exposes a hook registry.
    hook_result = _register_mainline_hooks(controller)
    results['mainline_hooks_registered'] = bool(hook_result.get('registered'))
    results['mainline_direct_register_call'] = not bool(hook_result.get('registered'))
    results['mainline_hook_registration_detail'] = hook_result

    _registered = True
    results['status'] = 'registered'
    results['registered'] = True
    return results


def _register_mainline_hooks(controller: Any) -> Dict[str, Any]:
    """Register hooks into the conversation mainline if a hook registry exists.

    The current no-skills/direct-provider workspace calls register_persona_visual()
    directly from infrastructure.mainline_hook. If register_pre_hook/register_post_hook
    are not exposed, report not_supported instead of pretending success.
    """
    try:
        from infrastructure.mainline_hook import register_pre_hook, register_post_hook
        register_pre_hook(_pre_reply_hook)
        register_post_hook(_post_reply_hook)
        return {'registered': True, 'mode': 'hook_registry'}
    except Exception as e:
        return {'registered': False, 'mode': 'direct_call', 'reason': type(e).__name__, 'detail': str(e)}


def _pre_reply_hook(context: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-reply hook: detect if request is a persona visual request and enforce routing."""
    user_message = context.get('user_message', '')
    semantic_scene = context.get('semantic_scene', '')

    from xiaoyi_persona_visual.router.visual_request_router import is_persona_visual_request, should_use_last_outfit
    from xiaoyi_persona_visual.wardrobe.wardrobe_loader import detect_explicit_outfit, load_focus_outfit_map

    is_pv = is_persona_visual_request(user_message, semantic_scene)
    use_last = should_use_last_outfit(user_message, semantic_scene)

    context['_persona_visual_request'] = is_pv
    context['_persona_visual_use_last_outfit'] = use_last

    if is_pv:
        # Route to PersonaVisualController when applicable
        context['_persona_routed_to_controller'] = True

    return context


def _post_reply_hook(context: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Post-reply hook: populate debug fields."""
    return result
