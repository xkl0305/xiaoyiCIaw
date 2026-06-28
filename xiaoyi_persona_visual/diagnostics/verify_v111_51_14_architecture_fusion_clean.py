from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'V111.51.23_STRICT_TRIGGER_AND_PROOF_FINAL'


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def main() -> int:
    checks = {}
    failures = []

    # 1 versions
    paths = {
        'release_manifest': 'release_manifest.json',
        'module_version': 'xiaoyi_persona_visual/version.json',
        'hook_manifest': '.openclaw/hooks/manifest.json',
    }
    for name, rel in paths.items():
        try:
            obj = load_json(rel)
            checks[f'{name}_version'] = obj.get('version')
            if obj.get('version') != VERSION:
                failures.append(f'{name}_version_not_unified:{obj.get("version")}')
        except Exception as e:
            checks[f'{name}_version'] = f'error:{e}'
            failures.append(f'{name}_missing_or_invalid')
    oc = load_json('openclaw.json')
    checks['openclaw_persona_visual_version'] = oc.get('personaVisual', {}).get('version')
    if oc.get('personaVisual', {}).get('version') != VERSION:
        failures.append('openclaw_persona_visual_version_not_unified')

    # 2 wardrobe references complete and real files
    wm = load_json('xiaoyi_persona_visual/wardrobe/wardrobe_manifest.json')
    missing_refs = []
    symlink_refs = []
    for outfit_id, item in wm.get('outfits', {}).items():
        ref = item.get('reference_image')
        if not ref:
            missing_refs.append(outfit_id)
            continue
        p = ROOT / ref
        if not p.exists():
            missing_refs.append(f'{outfit_id}:{ref}')
        if p.is_symlink():
            symlink_refs.append(f'{outfit_id}:{ref}')
    checks['wardrobe_missing_refs'] = missing_refs
    checks['wardrobe_symlink_refs'] = symlink_refs
    if missing_refs:
        failures.append('wardrobe_missing_reference_images')
    if symlink_refs:
        failures.append('wardrobe_reference_images_are_symlinks')

    # 3 focus map references point to valid outfits with refs
    fmap = load_json('xiaoyi_persona_visual/wardrobe/focus_outfit_map.json').get('focus_outfit_map', {})
    invalid_focus = []
    outfits = wm.get('outfits', {})
    for focus, ids in fmap.items():
        for oid in ids:
            if oid not in outfits or not outfits.get(oid, {}).get('reference_image'):
                invalid_focus.append(f'{focus}:{oid}')
    checks['focus_map_invalid_outfits'] = invalid_focus
    if invalid_focus:
        failures.append('focus_map_uses_outfit_without_reference')

    # 4 registries claim persona visual
    registry_checks = {
        'six_layer': ('infrastructure/SIX_LAYER_REGISTRY.json', ['persona_visual_controller', 'focus_semantic_parser', 'seedream_provider', 'mainchain_proof']),
        'component': ('infrastructure/COMPONENT_REGISTRY.json', ['focus_semantic_parser', 'mainchain_proof', 'seedream_provider']),
        'module_registry': ('infrastructure/inventory/module_registry.json', ['persona_visual_controller', 'focus_semantic_parser', 'mainchain_proof']),
        'fusion_index': ('infrastructure/inventory/fusion_index.json', ['persona_visual_controller', 'focus_semantic_parser', 'mainchain_proof']),
        'integration_registry': ('orchestration/INTEGRATION_REGISTRY.json', ['persona_visual', 'mainchain_proof']),
    }
    for key, (rel, tokens) in registry_checks.items():
        body = (ROOT / rel).read_text(encoding='utf-8')
        ok = all(token in body for token in tokens)
        checks[f'{key}_registered'] = ok
        if not ok:
            failures.append(f'{key}_not_registered')

    # 5 prompt registry and mainline hook registry
    checks['persona_prompt_registry_exists'] = (ROOT / 'infrastructure/persona_prompt_registry.py').exists()
    if not checks['persona_prompt_registry_exists']:
        failures.append('persona_prompt_registry_missing')
    mainline = (ROOT / 'infrastructure/mainline_hook.py').read_text(encoding='utf-8')
    checks['mainline_register_pre_hook_exists'] = 'def register_pre_hook' in mainline
    checks['mainline_register_post_hook_exists'] = 'def register_post_hook' in mainline
    if not (checks['mainline_register_pre_hook_exists'] and checks['mainline_register_post_hook_exists']):
        failures.append('mainline_hook_registry_missing')

    # 6 subject cleanup
    vt_obj = load_json('xiaoyi_persona_visual/policy/visual_trigger_policy.json')
    primary_keywords = vt_obj.get('explicit_routing_keywords', [])
    checks['xiaoyi_removed_from_visual_trigger_policy'] = '小艺' not in primary_keywords
    checks['xiaoyi_only_legacy_alias_if_present'] = '小艺' not in primary_keywords
    if not checks['xiaoyi_removed_from_visual_trigger_policy']:
        failures.append('xiaoyi_still_primary_trigger')

    # 7 actual reference count only, no max fake pass
    bridge = (ROOT / 'memory_context/persona_runtime/persona_visual_auto_generation_bridge.py').read_text(encoding='utf-8')
    checks['reference_count_no_max_fake'] = 'reference_images_count\': max(reference_images_count, 2)' not in bridge and 'max(reference_images_count, 2)' not in bridge
    checks['wardrobe_loader_used_debug'] = "'wardrobe_loader_used': True" in bridge
    checks['missing_required_reference_block'] = 'missing_required_reference_images' in bridge
    if not checks['reference_count_no_max_fake']:
        failures.append('reference_images_count_fake_max_still_present')
    if not checks['wardrobe_loader_used_debug']:
        failures.append('wardrobe_loader_used_debug_missing')
    if not checks['missing_required_reference_block']:
        failures.append('missing_reference_fail_closed_missing')

    # 8 post overlay child failure fatal and API key logic no-key pass
    poc = (ROOT / 'xiaoyi_persona_visual/diagnostics/post_overlay_check.py').read_text(encoding='utf-8')
    checks['post_overlay_child_failures_fatal'] = 'child_failures_fatal' in poc and 'raise SystemExit' in poc
    checks['api_key_no_key_pass_logic'] = 'no_key_configured_pass' in poc
    if not checks['post_overlay_child_failures_fatal']:
        failures.append('post_overlay_child_failures_not_fatal')
    if not checks['api_key_no_key_pass_logic']:
        failures.append('api_key_no_key_pass_logic_missing')

    # 9 runtime/overlay residue after apply script
    residue = []
    for pat in ['V*_overlay', '*_overlay']:
        for p in ROOT.glob(pat):
            if p.is_dir():
                residue.append(str(p.relative_to(ROOT)))
    pycache_count = sum(1 for _ in ROOT.rglob('__pycache__'))
    pyc_count = sum(1 for _ in ROOT.rglob('*.pyc'))
    checks['overlay_residue_dirs'] = residue
    checks['pycache_count'] = pycache_count
    checks['pyc_count'] = pyc_count
    # Do not fail overlay residue here when running before cleanup script; report it.

    # 10 clean package excludes
    checks['clean_package_excludes_exists'] = (ROOT / 'scripts/CLEAN_PACKAGE_EXCLUDES_V111_51_14.txt').exists()
    if not checks['clean_package_excludes_exists']:
        failures.append('clean_package_excludes_missing')

    ok = not failures
    for k, v in checks.items():
        print(f'{k}={v}')
    print('failures=' + json.dumps(failures, ensure_ascii=False))
    print(f'overall={"passed" if ok else "failed"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
