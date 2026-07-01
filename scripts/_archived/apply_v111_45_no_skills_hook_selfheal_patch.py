#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION = 'V111.45_NO_SKILLS_HOOK_SELFHEAL'


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_runtime_garbage() -> None:
    for pat in ['**/__pycache__', '.pytest_cache', '.openclaw/hook_state', 'approvals', '.learnings']:
        for p in ROOT.glob(pat):
            if p.exists() and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
    for pat in ['**/*.pyc', '**/*.pyo', '**/*.jsonl']:
        for p in ROOT.glob(pat):
            try:
                p.unlink()
            except Exception:
                pass


def update_config() -> None:
    p = ROOT / 'openclaw.json'
    cfg = _json(p, {})
    pv = cfg.setdefault('personaVisual', {})
    pv.update({
        'version': VERSION,
        'autoGenerate': True,
        'generateOnlyOnPhase': 'post_reply',
        'preReplyMode': 'detect_only',
        'maxImagesPerTurn': 2,
        'allowSecondaryImageOnFocus': True,
        'secondaryImageOnlyWhenFocusRequested': True,
        'dedupeAfterFocusResolved': True,
        'fallbackToSceneDefault': False,
        'sceneDefaultFallback': 'manual_only_no_auto_send',
        'focusIntentMode': 'universal_safe_focus_v11144',
        'wardrobeStatePath': '.persona_visual/runtime_wardrobe_state.json',
        'hookSelfHeal': True,
        'renderPromptStyle': 'emotion_scene_blend_v111_45',
    })
    _save(p, cfg)


def sanitize_static_wardrobe() -> None:
    p = ROOT / 'assets/persona/outfits/outfit_config.json'
    cfg = _json(p, {})
    if not isinstance(cfg, dict):
        cfg = {}
    cfg['version'] = 'V111.45_STATIC_WARDROBE'
    cfg.pop('current_outfit', None)
    for k, v in (cfg.get('outfits') or {}).items():
        if isinstance(v, dict):
            v['manual_only'] = k in {'bikini', 'silver_bikini'} or bool(v.get('manual_only', False))
    _save(p, cfg)
    state = ROOT / '.persona_visual/runtime_wardrobe_state.json'
    if not state.exists():
        _save(state, {'version': VERSION, 'current_outfit': 'default', 'source': 'runtime_state'})


def enable_hooks() -> None:
    from scripts.mainline_bootstrap import enable
    enable()


def main() -> None:
    clean_runtime_garbage()
    update_config()
    sanitize_static_wardrobe()
    enable_hooks()
    print(json.dumps({'status': 'ok', 'version': VERSION, 'hook_self_heal': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
