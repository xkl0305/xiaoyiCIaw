#!/usr/bin/env python3
"""V111.21 persona visual runtime/state sanitizer.

Keeps V111.20 active runtime, but removes confusing runtime residue:
- stale one-time token ledgers/state
- old visual generation ledger entries with superseded long appearance prompts
- active pycache/pyc
- old generated persona images from active generated-images area
- superseded persona visual reports from active reports/current to vintage area
"""
from __future__ import annotations
import json, shutil, time
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
STAMP = time.strftime('V111_21_%Y%m%d_%H%M%S')
ARCHIVE = ROOT / 'archive' / 'persona_visual_runtime_state_sanitized' / STAMP
ARCHIVE.mkdir(parents=True, exist_ok=True)

def rel(p: Path) -> str:
    try: return p.relative_to(ROOT).as_posix()
    except Exception: return str(p)

def move_to_archive(p: Path) -> str | None:
    if not p.exists(): return None
    dst = ARCHIVE / rel(p)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        if dst.exists(): shutil.rmtree(dst, ignore_errors=True)
        shutil.move(str(p), str(dst))
    else:
        if dst.exists(): dst.unlink()
        shutil.move(str(p), str(dst))
    return rel(p)

def remove_path(p: Path) -> str | None:
    if not p.exists(): return None
    if p.is_dir(): shutil.rmtree(p, ignore_errors=True)
    else: p.unlink(missing_ok=True)
    return rel(p)

def write_json(p: Path, data: Any):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def main() -> int:
    archived=[]; deleted=[]; reset=[]

    # Active runtime output/state: archive first, then recreate clean dirs.
    for p in [ROOT/'.visual_persona_state', ROOT/'.persona_visual']:
        x = move_to_archive(p)
        if x: archived.append(x)
        p.mkdir(parents=True, exist_ok=True)
        (p/'.gitkeep').write_text('', encoding='utf-8')
        reset.append(rel(p))

    # Active generated outputs: keep code package clean; old images are archived.
    gen = ROOT/'generated-images'
    if gen.exists():
        x = move_to_archive(gen)
        if x: archived.append(x)
    (ROOT/'generated-images'/'persona_visual').mkdir(parents=True, exist_ok=True)
    (ROOT/'generated-images'/'persona_visual'/'.gitkeep').write_text('', encoding='utf-8')
    reset.append('generated-images/persona_visual')

    # Remove all python caches in package.
    for p in list(ROOT.rglob('__pycache__')):
        x = remove_path(p)
        if x: deleted.append(x)
    for p in list(ROOT.rglob('*.pyc')):
        x = remove_path(p)
        if x: deleted.append(x)

    # Move superseded persona visual reports out of active reports/current and reports root.
    vintage = ROOT/'reports'/'vintage'/'persona_visual_superseded' / STAMP
    vintage.mkdir(parents=True, exist_ok=True)
    keep_prefixes = {'V111_20_', 'V111_21_'}
    patterns = ['*PERSONA_VISUAL*', '*persona_visual*', '*SCENE_IMAGE*', '*SEEDREAM*', '*MOOD_SIGNAL*']
    moved_reports=[]
    for base in [ROOT/'reports', ROOT/'reports'/'current']:
        if not base.exists(): continue
        for pattern in patterns:
            for p in list(base.glob(pattern)):
                if p.is_dir(): continue
                name = p.name
                if any(name.startswith(k) for k in keep_prefixes):
                    continue
                # Do not repeatedly move files already inside vintage.
                if 'vintage' in p.parts:
                    continue
                dst = vintage / rel(p)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dst))
                moved_reports.append(rel(p))

    # Ensure seed binding remains explicit.
    cfg = ROOT/'openclaw.json'
    if cfg.exists():
        try:
            data=json.loads(cfg.read_text(encoding='utf-8'))
        except Exception:
            data={}
        pv=data.setdefault('personaVisual', {})
        pv.update({
            'seedAvatarPath': 'assets/persona/seed_avatar.jpg',
            'canonicalSeedPath': 'assets/persona/seed_avatar.jpg',
            'avatarSeedBinding': 'direct_avatar_equals_seed',
            'identitySource': 'seed_avatar_image_only',
            'identityTextPromptMode': 'seed_lock_only',
            'seedReferenceRequired': True,
            'seedReferenceWeight': 100,
            'dailyAutoGenerateLimit': 100,
            'cooldownTurns': 0,
            'activeRuntime': 'memory_context.persona_runtime',
            'legacyRuntimePolicy': 'shim_only',
        })
        write_json(cfg, data)

    report={
        'version':'V111.21',
        'status':'applied',
        'purpose':'sanitize_persona_visual_runtime_state_after_V111_20',
        'archived': archived,
        'deleted_cache_count': len(deleted),
        'reset_active_dirs': reset,
        'moved_superseded_reports': moved_reports,
        'archive_root': rel(ARCHIVE),
        'seed_avatar_path':'assets/persona/seed_avatar.jpg',
        'active_runtime':'memory_context.persona_runtime',
        'notes':[
            'Runtime token files are not shipped in active state.',
            'Old generated images are not left in active generated-images.',
            'Old persona visual reports are not left as active reports.',
            'Seed avatar remains the only identity source.'
        ]
    }
    write_json(ROOT/'reports'/'V111_21_PERSONA_VISUAL_RUNTIME_SANITIZE_APPLY.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
