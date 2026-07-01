#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, time, filecmp, importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAMP = time.strftime('V111_22_%Y%m%d_%H%M%S')
ARCHIVE = ROOT / 'archive' / 'v11122_total_overlay' / STAMP
ARCHIVE.mkdir(parents=True, exist_ok=True)

def rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except Exception:
        return str(p)

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def move_to_archive(p: Path) -> str | None:
    if not p.exists():
        return None
    dst = ARCHIVE / rel(p)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.move(str(p), str(dst))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        shutil.move(str(p), str(dst))
    return rel(p)

def dirs_equivalent(parent_dir: Path, nested_dir: Path) -> bool:
    parent_files = sorted([p.name for p in parent_dir.glob('*.py') if p.name != '__init__.py'])
    nested_files = sorted([p.name for p in nested_dir.glob('*.py') if p.name != '__init__.py'])
    if parent_files != nested_files:
        return False
    for name in parent_files:
        if (parent_dir/name).read_text(encoding='utf-8') != (nested_dir/name).read_text(encoding='utf-8'):
            return False
    return True

def maybe_run_v11121_sanitize() -> dict[str, Any]:
    script = ROOT / 'scripts' / 'v111_21_persona_visual_runtime_sanitize_apply.py'
    if not script.exists():
        return {'status': 'missing'}
    spec = importlib.util.spec_from_file_location('v11121_sanitize_apply', str(script))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    rc = mod.main() if hasattr(mod, 'main') else 0
    return {'status': 'ok' if rc == 0 else 'failed', 'rc': rc}

def ensure_openclaw_persona_visual() -> dict[str, Any]:
    p = ROOT / 'openclaw.json'
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    pv = data.setdefault('personaVisual', {})
    pv.update({
        'enabled': True,
        'predictiveSuggestion': True,
        'autoGenerate': True,
        'autoGenerateRequiresBudget': True,
        'generationConsentMode': 'auto_with_budget',
        'userStandingConsent': True,
        'confidenceThreshold': 0.82,
        'strongThreshold': 0.82,
        'midHighThreshold': 0.65,
        'midLowThreshold': 0.50,
        'recordOnlyThreshold': 0.30,
        'dailyAutoGenerateLimit': 100,
        'cooldownTurns': 0,
        'externalProvider': 'seedream',
        'sceneTriggerMode': 'semantic_scene',
        'seedAvatarPath': 'assets/persona/seed_avatar.jpg',
        'canonicalSeedPath': 'assets/persona/seed_avatar.jpg',
        'avatarSeedBinding': 'direct_avatar_equals_seed',
        'identitySource': 'seed_avatar_image_only',
        'identityTextPromptMode': 'seed_lock_only',
        'seedReferenceRequired': True,
        'seedReferenceWeight': 100,
        'activeRuntime': 'memory_context.persona_runtime',
        'legacyRuntimePolicy': 'shim_only',
    })
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return pv

def main() -> int:
    archived = []
    checks = []

    v11121 = maybe_run_v11121_sanitize()

    duplicate_pairs = [
        (ROOT/'core/agent_kernel/autonomy', ROOT/'core/agent_kernel/autonomy/autonomy'),
        (ROOT/'core/agent_kernel/personal_agent', ROOT/'core/agent_kernel/personal_agent/personal_agent'),
    ]
    for parent_dir, nested_dir in duplicate_pairs:
        if nested_dir.exists():
            ok = dirs_equivalent(parent_dir, nested_dir)
            checks.append({'pair': f'{rel(parent_dir)} <= {rel(nested_dir)}', 'equivalent': ok})
            if ok:
                moved = move_to_archive(nested_dir)
                if moved:
                    archived.append(moved)

    for rel_dir in [
        'governance/evidence_gate/approvals/legacy_conflicts',
        'governance/evidence_gate/audit/legacy_conflicts',
        'orchestration/skill_runtime/router/legacy_conflicts',
        'orchestration/skill_runtime/router/routing/legacy_conflicts',
    ]:
        p = ROOT / rel_dir
        if p.exists():
            moved = move_to_archive(p)
            if moved:
                archived.append(moved)

    pv = ensure_openclaw_persona_visual()

    report = {
        'version': 'V111.22',
        'status': 'applied',
        'applied_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'v11121_sanitize': v11121,
        'duplicate_pair_checks': checks,
        'archived_paths': archived,
        'persona_visual': {
            'scene_trigger_mode': pv.get('sceneTriggerMode'),
            'dailyAutoGenerateLimit': pv.get('dailyAutoGenerateLimit'),
            'cooldownTurns': pv.get('cooldownTurns'),
            'seedAvatarPath': pv.get('seedAvatarPath'),
            'identitySource': pv.get('identitySource'),
        },
        'new_fusion_docs': [
            'governance/fused_modules/doc_fusion_persona_visual_semantic_autotrigger_v20260506.json',
            'governance/fused_modules/doc_fusion_agent_kernel_duplicate_package_cleanup_v20260506.json',
        ],
        'notes': [
            '人格视觉自动触发主链保留为语义场景/心情触发，不依赖显式“出图”关键词。',
            '头像 assets/persona/seed_avatar.jpg 仍是唯一人格视觉种子图。',
            'nested duplicate packages 已归档，不直接删除。',
            'unused legacy_conflicts 目录已归档，减少活动架构噪音。',
        ],
        'archive_root': rel(ARCHIVE),
    }
    write_json(ROOT/'reports'/'V111_22_TOTAL_OVERLAY_APPLY.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
