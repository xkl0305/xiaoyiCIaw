from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _cleanup_runtime_after_check() -> None:
    """Keep diagnostic runs from polluting source packages."""
    import shutil
    runtime_dirs = [
        '.openclaw/state', '.openclaw/hook_state', '.v98_state', '.v107_state',
        '.lazy_state', '.context_state', 'logs', 'generated-images', '.pytest_cache',
        '.persona_visual/generated',
    ]
    runtime_files = [
        '.persona_visual/visual_request_ledger.jsonl',
        '.persona_visual/runtime_wardrobe_state.json',
    ]
    for rel in runtime_dirs:
        p = ROOT / rel
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    for rel in runtime_files:
        p = ROOT / rel
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    for p in list(ROOT.rglob('*')):
        if p.is_dir() and p.name == '__pycache__':
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file() and (p.suffix in {'.pyc', '.pyo', '.jsonl', '.log', '.sqlite', '.sqlite3', '.db'} or p.name == '.DS_Store'):
            try:
                p.unlink()
            except Exception:
                pass


def _load_post_reply():
    path = ROOT / '.openclaw/hooks/post_reply.py'
    spec = importlib.util.spec_from_file_location('openclaw_post_reply_hook', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _summarize_generation(res: Dict[str, Any]) -> Dict[str, Any]:
    gen = res.get('generation', res if isinstance(res, dict) else {}) or {}
    prompt = gen.get('prompt') or ''
    return {
        'status': res.get('status'),
        'generation_status': res.get('generation_status') or gen.get('status'),
        'register_persona_visual_called': res.get('register_persona_visual_called'),
        'pipeline_entry': res.get('pipeline_entry') or gen.get('pipeline_entry'),
        'persona_visual_controller_used': gen.get('persona_visual_controller_used'),
        'prompt_builder_used': res.get('prompt_builder_used') or gen.get('prompt_builder_used'),
        'negative_prompt_guard_used': res.get('negative_prompt_guard_used') or gen.get('negative_prompt_guard_used'),
        'minimal_negative_guard_used': gen.get('minimal_negative_guard_used'),
        'identity_lock': gen.get('identity_lock'),
        'style_lock': gen.get('style_lock'),
        'scene_type': gen.get('scene_type'),
        'scene_confidence': gen.get('scene_confidence'),
        'focus_target': gen.get('focus_target'),
        'secondary_generation_allowed': gen.get('secondary_generation_allowed'),
        'focus_only_generation_mode': gen.get('focus_only_generation_mode'),
        'choice_source': gen.get('choice_source'),
        'outfit_source': gen.get('outfit_source'),
        'outfit_id': gen.get('outfit_id'),
        'runtime_current_used': gen.get('runtime_current_used'),
        'fallback_used': gen.get('fallback_used'),
        'fallback_reason': gen.get('fallback_reason'),
        'generation_allowed': res.get('generation_allowed') if res.get('generation_allowed') is not None else gen.get('generation_allowed'),
        'seedream_provider_ready': gen.get('seedream_provider_ready'),
        'seedream_api_url_present': gen.get('seedream_api_url_present'),
        'seedream_api_key_present': gen.get('seedream_api_key_present'),
        'provider_input_image_exists': gen.get('provider_input_image_exists'),
        'provider_input_image_path': gen.get('provider_input_image_path'),
        'visual_request_detected': gen.get('visual_request_detected'),
        'persona_visual_request': gen.get('persona_visual_request'),
        'pipeline_forced': gen.get('pipeline_forced'),
        'wardrobe_loader_used': gen.get('wardrobe_loader_used'),
        'avatar_reference_present': gen.get('avatar_reference_present'),
        'outfit_reference_present': gen.get('outfit_reference_present'),
        'reference_images_count': gen.get('reference_images_count'),
        'reference_images_count_actual': gen.get('reference_images_count_actual'),
        'outfit_ref_path': gen.get('outfit_ref_path') or gen.get('outfit_reference_path'),
        'generation_mode': gen.get('generation_mode'),
        'provider': gen.get('provider'),
        'blocked': gen.get('blocked'),
        'blocked_reason': gen.get('blocked_reason'),
        'required_entry': gen.get('required_entry'),
        'prompt_total_length': gen.get('prompt_total_length') or len(prompt),
        'prompt_chinese_length': gen.get('prompt_chinese_length'),
        'prompt_effective_chinese_length': gen.get('prompt_effective_chinese_length'),
        'prompt_template_type': gen.get('prompt_template_type'),
        'prompt_has_duplicate_phrase': gen.get('prompt_has_duplicate_phrase'),
        'prompt_density_score': gen.get('prompt_density_score'),
        'prompt_autowrite_enhanced': gen.get('prompt_autowrite_enhanced'),
        'prompt_min_chinese_required': gen.get('prompt_min_chinese_required'),
        'prompt_preview': prompt[:260],
    }


def _run_post_reply(text: str, dry_run: bool = True) -> Dict[str, Any]:
    mod = _load_post_reply()
    return mod.run(user_message=text, assistant_message=text, reply_text=text, dry_run=dry_run, request_id='post_overlay_check_' + uuid.uuid4().hex)


@contextmanager
def _temporarily_hide(rel_path: str):
    p = ROOT / rel_path
    if not p.exists():
        yield False
        return
    tmp = p.with_suffix(p.suffix + '.hidden_for_check')
    if tmp.exists():
        tmp.unlink()
    p.rename(tmp)
    try:
        yield True
    finally:
        if tmp.exists():
            tmp.rename(p)


def _assert_prompt_quality(label: str, summary: Dict[str, Any], failures: list[str]) -> None:
    if summary.get('prompt_autowrite_enhanced') is not True:
        failures.append(f'{label}_prompt_autowrite_not_enhanced')
    if int(summary.get('prompt_effective_chinese_length') or 0) < 100:
        failures.append(f"{label}_effective_chinese_too_short:{summary.get('prompt_effective_chinese_length')}")
    if summary.get('prompt_has_duplicate_phrase') is True:
        failures.append(f'{label}_prompt_has_duplicate_phrase')
    if not summary.get('prompt_template_type'):
        failures.append(f'{label}_prompt_template_type_missing')


def verify_real_pipeline() -> Dict[str, Any]:
    """
    Attempt to call mainline_hook.run('看看你的样子') and check the result
    for pipeline_entry, prompt_builder_used, and other key fields.
    Fail-soft: returns an error dict on failure without raising.
    """
    try:
        from infrastructure.mainline_hook import run as mainline_run
        result = mainline_run(message='看看你的样子', mode='post_reply')
        return {
            'verify_status': 'ok',
            'pipeline_entry': result.get('visual_prediction_summary', {}).get('pipeline_entry')
                            or result.get('persona_visual_render_plan', {}).get('pipeline_entry'),
            'prompt_builder_used': result.get('persona_visual_render_plan', {}).get('prompt_builder_used'),
            'register_persona_visual_called': result.get('register_persona_visual_called'),
            'persona_visual_trigger_source': result.get('persona_visual_trigger_source'),
            'persona_visual_generation_status': result.get('persona_visual_generation_status'),
            'persona_visual_generation_delegate': result.get('persona_visual_generation_delegate'),
            'has_visual_prediction_summary': bool(result.get('visual_prediction_summary')),
            'has_render_plan': bool(result.get('persona_visual_render_plan')),
            'full_result_keys': list(result.keys()),
        }
    except Exception as e:
        import traceback
        return {
            'verify_status': 'fail_soft',
            'error': str(e),
            'traceback': traceback.format_exc(),
        }


def run_post_overlay_check() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    failures: list[str] = []

    from xiaoyi_persona_visual.registry.register_persona_visual import register_persona_visual
    reg = register_persona_visual(app=None)
    checks['registration'] = reg
    if not reg.get('registered'):
        failures.append('register_persona_visual_not_registered')
    if not (reg.get('prompt_builder_registered') or reg.get('prompt_builder_direct_callable')):
        failures.append('prompt_builder_not_callable')

    skills_dir = ROOT / 'skills'
    checks['no_skills_package'] = not skills_dir.exists()
    manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    checks['manifest_package_mode'] = manifest.get('package_mode')
    checks['physical_skill_required'] = manifest.get('seedream_provider_direct', {}).get('physical_skill_required')
    if checks['physical_skill_required'] is not False:
        failures.append('manifest_still_requires_physical_skill')

    try:
        from infrastructure.mainline_hook import run as mainline_run
        ml = mainline_run(message='看看你的样子', mode='post_reply')
        # Extract pipeline entry from visual_prediction_summary or visual context
        pipeline_entry = None
        if isinstance(ml.get('visual_prediction_summary'), dict):
            pipeline_entry = ml['visual_prediction_summary'].get('pipeline_entry')
        gen = ml.get('persona_visual_render_plan') or {}
        if gen and not pipeline_entry:
            pipeline_entry = gen.get('pipeline_entry')
        checks['mainline'] = {
            'register_persona_visual_called': ml.get('register_persona_visual_called'),
            'pipeline_entry': pipeline_entry,
            'visual_auto_generation_allowed': ml.get('visual_auto_generation_allowed'),
            'visual_suggestion_available': ml.get('visual_suggestion_available'),
            'warnings': ml.get('warnings', []),
        }
        if ml.get('register_persona_visual_called') is not True:
            failures.append('mainline_did_not_call_register_persona_visual')
        if pipeline_entry not in ('PersonaVisualController', None):
            failures.append(f'mainline_pipeline_entry_unexpected:{pipeline_entry}')
    except Exception as e:
        checks['mainline'] = {'error': str(e)}
        failures.append('mainline_run_failed')

    cases = {
        'appearance': _summarize_generation(_run_post_reply('看看你的样子', dry_run=True)),
        'legs': _summarize_generation(_run_post_reply('看看腿', dry_run=True)),
        'window_scene': _summarize_generation(_run_post_reply('鸽子王站在窗边，回头看我', dry_run=True)),
        'same_outfit_post_reply': _summarize_generation(_run_post_reply('还是刚才那身', dry_run=True)),
    }
    checks['post_reply_cases'] = cases

    app = cases['appearance']
    required = {
        'pipeline_entry': 'PersonaVisualController',
        'prompt_builder_used': 'persona_image_prompt_builder',
        'negative_prompt_guard_used': True,
        'identity_lock': True,
        'style_lock': True,
        'scene_type': 'display_appearance_scene',
    }
    for k, v in required.items():
        if app.get(k) != v:
            failures.append(f'appearance_{k}_unexpected:{app.get(k)}')
    if app.get('focus_target') not in ('', None) or app.get('secondary_generation_allowed'):
        failures.append('appearance_misclassified_as_focus')
    for label in ('appearance', 'legs', 'window_scene'):
        _assert_prompt_quality(label, cases[label], failures)

    # Strict wardrobe continuity check independent of post_reply auto-generation threshold.
    from xiaoyi_persona_visual.wardrobe.wardrobe_loader import save_current_outfit, choose_outfit
    save_current_outfit('stardust_dream')
    same_direct = choose_outfit(text='还是刚才那身')
    checks['same_outfit_direct'] = {
        'last_outfit_continuity': same_direct.get('last_outfit_continuity'),
        'runtime_current_used': same_direct.get('runtime_current_used'),
        'choice_source': same_direct.get('choice_source'),
        'outfit_id': same_direct.get('outfit_id'),
        'outfit_source': same_direct.get('outfit_source'),
    }
    if checks['same_outfit_direct'] != {
        'last_outfit_continuity': True,
        'runtime_current_used': True,
        'choice_source': 'last_outfit_continuity',
        'outfit_id': 'stardust_dream',
        'outfit_source': 'last_outfit',
    }:
        failures.append('same_outfit_direct_continuity_failed')

    with _temporarily_hide('xiaoyi_persona_visual/prompt/negative_prompt_guard.json'):
        neg_case = _summarize_generation(_run_post_reply('看看你的样子', dry_run=True))
    checks['missing_negative_guard'] = neg_case
    if not (neg_case.get('minimal_negative_guard_used') or neg_case.get('negative_prompt_guard_used')):
        failures.append('missing_negative_guard_not_safe')

    for name, rel in {
        'missing_identity': 'xiaoyi_persona_visual/config/visual_identity_profile.json',
        'missing_style': 'xiaoyi_persona_visual/config/style_profile.json',
        'missing_wardrobe': 'xiaoyi_persona_visual/wardrobe/wardrobe_manifest.json',
        'missing_scene_map': 'xiaoyi_persona_visual/wardrobe/scene_outfit_map.json',
        'missing_focus_map': 'xiaoyi_persona_visual/wardrobe/focus_outfit_map.json',
    }.items():
        with _temporarily_hide(rel):
            summary = _summarize_generation(_run_post_reply('看看腿' if 'focus' in name else '看看你的样子', dry_run=True))
        checks[name] = summary
        if summary.get('prompt_builder_used') not in ('persona_image_prompt_builder', None):
            failures.append(f'{name}_wrong_prompt_builder')
        if summary.get('generation_allowed') is False:
            continue
        if not summary.get('fallback_used') and name not in {'missing_focus'}:
            failures.append(f'{name}_did_not_mark_fallback')

    return {
        'post_overlay_status': 'passed' if not failures else 'failed',
        'all_checks_passed': not failures,
        'failures': failures,
        'checks': checks,
    }


# ── V111.51.5 / V111.52 Final Verification ──


def _run_legacy_script(prompt: str) -> str:
    """Run legacy script if present; no-skills packages treat missing legacy entry as blocked."""
    import subprocess
    script_path = ROOT / 'skills/seedream-image-gen/scripts/generate_seedream_legacy_v11146.py'
    script_dir_path = ROOT / 'skills/seedream-image-gen/scripts'
    if not script_path.exists() or not script_dir_path.exists():
        return 'status=blocked\nblocked_reason=persona_visual_request_must_use_main_pipeline\nlegacy_entry_absent_in_no_skills_package=true'
    result = subprocess.run(
        ['python3', str(script_path), '--prompt', prompt],
        capture_output=True, text=True, timeout=30,
        cwd=str(script_dir_path),
    )
    return result.stdout + result.stderr


def _make_mock_provider_call(prompt: str, with_context: bool = False) -> Dict[str, Any]:
    """Simulate a direct seedream_provider.generate_image call with/without persona_visual_context."""
    from memory_context.persona_runtime.providers.seedream_provider import generate_image
    kwargs: Dict[str, Any] = {
        'prompt': prompt,
        'input_image': str(ROOT / 'assets/persona/seed_avatar.jpg'),
    }
    if with_context:
        kwargs['persona_visual_context'] = {
            'persona_visual_request': True,
            'pipeline_forced': True,
            'persona_visual_controller_used': True,
            'wardrobe_loader_used': True,
            'prompt_builder_used': 'persona_image_prompt_builder',
            'avatar_reference_present': True,
            'outfit_reference_present': True,
            'reference_images_count': 2,
            'generation_mode': 'image_to_image',
        }
        # With valid PVC, also pass reference_images (avatar + outfit)
        kwargs['reference_images'] = [
            str(ROOT / 'assets/persona/seed_avatar.jpg'),
            str(ROOT / 'assets/persona/outfits/moonfeather_robe_reference.jpg'),
        ]
    return generate_image(**kwargs)


def run_v111_51_5_verification() -> Dict[str, Any]:
    """Run V111.51.5 specific verification checks."""
    v111_checks: Dict[str, Any] = {}
    v111_failures: list[str] = []

    # === Test 1: Manual provider call WITHOUT persona_visual_context ===
    manual_no_ctx = _make_mock_provider_call('摸摸头，鸽子王...')
    v111_checks['manual_provider_momotou_no_ctx'] = {
        'status': manual_no_ctx.get('status'),
        'blocked': manual_no_ctx.get('blocked'),
        'blocked_reason': manual_no_ctx.get('blocked_reason'),
    }
    if not manual_no_ctx.get('blocked') or manual_no_ctx.get('blocked_reason') != 'persona_visual_request_must_use_main_pipeline':
        v111_failures.append(f'manual_provider_no_ctx_not_blocked:{manual_no_ctx.get("status")}')

    # === Test 2: Manual provider call WITH persona_visual_context ===
    manual_with_ctx = _make_mock_provider_call('摸摸头，鸽子王...', with_context=True)
    v111_checks['manual_provider_momotou_with_ctx'] = {
        'blocked': manual_with_ctx.get('blocked'),
        'status': manual_with_ctx.get('status'),
    }
    # V111.51.20+: field-complete manual PVC must still be blocked unless it carries a valid mainchain_proof.
    if not manual_with_ctx.get('blocked'):
        v111_failures.append('manual_provider_with_ctx_not_blocked_without_mainchain_proof')
    elif manual_with_ctx.get('blocked_reason') not in {'manual_pvc_provider_call_blocked', 'invalid_mainchain_proof'}:
        v111_failures.append(f'manual_provider_with_ctx_wrong_block_reason:{manual_with_ctx.get("blocked_reason")}')

    # === Test 3: Legacy script "看看腿" blocked ===
    legacy_out = _run_legacy_script('看看腿')
    v111_checks['legacy_kan_tui'] = {'output_preview': legacy_out[:500]}
    if 'persona_visual_request_must_use_main_pipeline' not in legacy_out and '拒绝' not in legacy_out:
        v111_failures.append('legacy_script_did_not_block')

    # === Test 4: Post_reply "摸摸头" ===
    momotou_case = _summarize_generation(_run_post_reply('摸摸头', dry_run=True))
    v111_checks['post_reply_momotou'] = momotou_case
    if momotou_case.get('pipeline_entry') != 'PersonaVisualController':
        v111_failures.append(f'momotou_pipeline_entry:{momotou_case.get("pipeline_entry")}')
    if not momotou_case.get('avatar_reference_present'):
        v111_failures.append('momotou_no_avatar_reference')
    if not momotou_case.get('outfit_reference_present'):
        v111_failures.append('momotou_no_outfit_reference')
    if int(momotou_case.get('reference_images_count') or 0) < 2:
        v111_failures.append(f'momotou_ref_count_lt_2:{momotou_case.get("reference_images_count")}')

    # === Test 5: Post_reply "看看腿" ===
    legs_case = _summarize_generation(_run_post_reply('看看腿', dry_run=True))
    v111_checks['post_reply_legs'] = legs_case
    expected_focus = legs_case.get('focus_target', '')
    if not expected_focus:
        v111_failures.append('legs_focus_target_empty')
    if not legs_case.get('outfit_ref_path') and not legs_case.get('outfit_reference_present'):
        v111_failures.append('legs_no_outfit_reference')
    if legs_case.get('prompt_builder_used') != 'persona_image_prompt_builder':
        v111_failures.append(f'legs_wrong_prompt_builder:{legs_case.get("prompt_builder_used")}')

    # === Test 6: prompt_builder_used ===
    cases_v111 = {
        'appearance': v111_checks.get('post_reply_cases', {}).get('appearance', {}),
        'legs': v111_checks.get('post_reply_cases', {}).get('legs', legs_case),
        'window_scene': v111_checks.get('post_reply_cases', {}).get('window_scene', {}),
        'momotou': momotou_case,
    }
    for label, c in cases_v111.items():
        if c.get('prompt_builder_used') not in ('persona_image_prompt_builder', None):
            v111_failures.append(f'{label}_prompt_builder_not_persona_image:{c.get("prompt_builder_used")}')

    # === Test 7: Negative prompt guard ===
    for label, c in [('appearance', cases_v111.get('appearance', {})), ('momotou', momotou_case)]:
        if c and c.get('negative_prompt_guard_used') is not True:
            v111_failures.append(f'{label}_negative_prompt_guard_not_used')

    # === Test 8: API key masking ===
    from memory_context.persona_runtime.providers.seedream_provider import provider_env
    env = provider_env()
    debug = env.get('_debug', {})
    masked = debug.get('seedream_api_key_masked', '')
    v111_checks['api_key_masked'] = {
        'seedream_api_key_masked': masked,
        'has_masked_key': bool(masked),
        'contains_full_key': bool(masked) and masked.count('*') >= 4,
    }
    # No key configured is valid in no-skills/offline verification; if a key exists, it must be masked.
    if debug.get('seedream_api_key_present'):
        if not masked or '****' not in masked:
            v111_failures.append('api_key_not_masked')
    else:
        v111_checks['api_key_masked']['no_key_configured_pass'] = True
    # No full API key in debug output
    full_api_key = env.get('api_key', '')
    if full_api_key and ('seedream-api' in str(debug) and full_api_key in str(debug)):
        v111_failures.append('full_api_key_exposed_in_debug')

    # === Test 9: Normal 山水图 still works ===
    from memory_context.persona_runtime.providers.seedream_provider import generate_image
    normal_case = generate_image(prompt='生成一张山水图，水墨风格')
    v111_checks['normal_landscape'] = {
        'blocked': normal_case.get('blocked'),
        'status': normal_case.get('status'),
    }
    # Non-persona requests should NOT be blocked by the persona gate
    # (might still be provider_not_ready, but NOT persona_visual blocked)
    if normal_case.get('blocked_reason') == 'persona_visual_request_must_use_main_pipeline':
        v111_failures.append('normal_landscape_falsely_blocked')
    # Should be allowed to proceed (may still be provider_not_ready)
    if normal_case.get('status') == 'blocked':
        v111_failures.append('normal_landscape_falsely_blocked')

    return {
        'v111_51_5_verification_status': 'passed' if not v111_failures else 'failed',
        'all_v111_checks_passed': not v111_failures,
        'v111_failures': v111_failures,
        'v111_checks': v111_checks,
    }


if __name__ == '__main__':
    result = {}
    try:
        result = run_post_overlay_check()
        v111 = run_v111_51_5_verification()
        result['v111_51_5'] = v111
        child_failures = []
        if not result.get('all_checks_passed'):
            child_failures.extend(result.get('failures', []))
        if not v111.get('all_v111_checks_passed'):
            child_failures.extend(v111.get('v111_failures', []))
        if child_failures:
            result['post_overlay_status'] = 'failed'
            result['all_checks_passed'] = False
            result['child_failures_fatal'] = True
            result['failures'] = list(dict.fromkeys(result.get('failures', []) + child_failures))
        else:
            result['post_overlay_status'] = 'passed'
            result['all_checks_passed'] = True
            result['child_failures_fatal'] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        _cleanup_runtime_after_check()
    raise SystemExit(0 if result.get('all_checks_passed') else 1)
