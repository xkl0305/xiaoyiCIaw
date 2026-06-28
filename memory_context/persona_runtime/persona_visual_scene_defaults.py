from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'assets/persona/scene_defaults/scene_default_config.json'

def get_scene_default_image(semantic_scene: str = '', text: str = '') -> Dict[str, Any]:
    if not CONFIG.exists():
        return {'status': 'missing_config'}
    try:
        cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    except Exception as e:
        return {'status': 'bad_config', 'error': str(e)}
    if cfg.get('auto_image_send') is True:
        # V111.40 deliberately avoids automatic default-image spam.
        return {'status': 'blocked_auto_default_send', 'reason': 'auto_image_send_should_be_false'}
    scene = (cfg.get('scenes') or {}).get(semantic_scene) or {}
    images = scene.get('default_images') or []
    if not images:
        return {'status': 'no_default_for_scene', 'semantic_scene': semantic_scene}
    t = text or ''
    chosen = images[0]
    for img in images:
        words = img.get('trigger_words') or []
        if any(w and w in t for w in words):
            chosen = img
            break
    rel = chosen.get('file_path')
    if rel and (ROOT / rel).exists():
        return {'status': 'default_scene_available_manual_only', 'file_path': rel, 'abs_path': str(ROOT / rel), 'meta': chosen}
    return {'status': 'default_file_missing', 'file_path': rel}
