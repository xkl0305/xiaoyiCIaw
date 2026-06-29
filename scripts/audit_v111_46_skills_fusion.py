#!/usr/bin/env python3
from __future__ import annotations
import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'V111.46_SKILLS_FUSION_CLEAN'


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        return {'__error__': str(e)}


def _missing_entries():
    out = {}
    for rel in ['infrastructure/inventory/skill_registry.json', 'infrastructure/manifest/skills_manifest.json']:
        obj = _read_json(ROOT / rel)
        skills = obj.get('skills', {}) if isinstance(obj, dict) else {}
        missing = []
        for sid, e in skills.items():
            if not isinstance(e, dict):
                continue
            path = e.get('path')
            entry = e.get('entry')
            if path and not (ROOT / path).exists():
                missing.append({'id': sid, 'path': path})
            if entry and not (ROOT / entry).exists():
                missing.append({'id': sid, 'entry': entry})
        out[rel] = {'count': len(skills), 'missing': missing[:20], 'missing_count': len(missing)}
    return out


def _seedream_status():
    status = {}
    for mod in [
        'memory_context.persona_runtime.providers.seedream_provider',
        'skills.seedream_image_gen.scripts.generate_seedream',
    ]:
        try:
            m = importlib.import_module(mod)
            status[mod] = {'ok': True, 'file': getattr(m, '__file__', ''), 'has_generate_image': hasattr(m, 'generate_image')}
        except Exception as e:
            status[mod] = {'ok': False, 'error': str(e)}
    hyphen = ROOT / 'skills/seedream-image-gen/scripts/generate_seedream.py'
    status['skills/seedream-image-gen/scripts/generate_seedream.py'] = {
        'exists': hyphen.exists(),
        'uses_provider_shim': hyphen.exists() and 'memory_context.persona_runtime.providers.seedream_provider' in hyphen.read_text(encoding='utf-8', errors='ignore'),
    }
    return status


def main():
    miss = _missing_entries()
    seed = _seedream_status()
    bad = []
    for rel, item in miss.items():
        if item['missing_count']:
            bad.append(f'{rel}:missing={item["missing_count"]}')
    for k, v in seed.items():
        if isinstance(v, dict) and (v.get('ok') is False or v.get('uses_provider_shim') is False):
            bad.append(f'seedream:{k}')
    result = {
        'status': 'ok' if not bad else 'fail',
        'version': VERSION,
        'skills_dir_exists': (ROOT / 'skills').is_dir(),
        'physical_skill_dirs': len([p for p in (ROOT / 'skills').iterdir() if p.is_dir()]) if (ROOT / 'skills').is_dir() else 0,
        'registry_checks': miss,
        'seedream_status': seed,
        'bad': bad,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if bad:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
