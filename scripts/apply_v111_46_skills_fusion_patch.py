#!/usr/bin/env python3
from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'V111.46_SKILLS_FUSION_CLEAN'


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def _skill_summary(skill_dir: Path) -> Dict[str, Any]:
    sid = skill_dir.name
    skill_md = skill_dir / 'SKILL.md'
    text = ''
    if skill_md.exists():
        try:
            text = skill_md.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            text = ''
    title = sid
    for line in text.splitlines()[:20]:
        if line.strip().startswith('#'):
            title = line.strip('#').strip() or sid
            break
    py_files = [p for p in skill_dir.rglob('*.py') if '__pycache__' not in p.parts]
    return {
        'id': sid,
        'name': title,
        'version': '7.2.0',
        'description': (text.strip().splitlines()[1].strip() if len(text.strip().splitlines()) > 1 else ''),
        'entry': f'skills/{sid}/SKILL.md',
        'triggers': [],
        'local_executable': bool(py_files),
        'python_files': len(py_files),
    }


def flatten_nested_skills() -> None:
    skills = ROOT / 'skills'
    nested = skills / 'skills'
    if nested.exists() and nested.is_dir():
        for item in nested.iterdir():
            target = skills / item.name
            if target.exists():
                continue
            shutil.move(str(item), str(target))
        try:
            nested.rmdir()
        except OSError:
            pass


def canonicalize_seedream() -> None:
    provider_dir = ROOT / 'memory_context/persona_runtime/providers'
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / '__init__.py').write_text('', encoding='utf-8')
    provider_path = provider_dir / 'seedream_provider.py'
    if not provider_path.exists():
        provider_path.write_text("""from __future__ import annotations\n\nimport base64, json, os, time\nfrom pathlib import Path\nfrom typing import Any, Dict\n\nROOT = Path(__file__).resolve().parents[3]\nOUT_DIR = ROOT / '.persona_visual' / 'generated'\n\ndef _read_xiaoyi_env() -> Dict[str, str]:\n    env = {}\n    p = Path.home() / '.openclaw' / '.xiaoyienv'\n    if not p.exists():\n        return env\n    try:\n        for line in p.read_text(encoding='utf-8').splitlines():\n            line = line.strip()\n            if not line or line.startswith('#') or '=' not in line:\n                continue\n            k, v = line.split('=', 1)\n            env[k.strip()] = v.strip().strip('\\\"').strip("'")\n    except Exception:\n        pass\n    return env\n\ndef provider_env() -> Dict[str, str]:\n    file_env = _read_xiaoyi_env()\n    return {\n        'url': os.environ.get('SEEDREAM_API_URL') or os.environ.get('SERVICE_URL') or file_env.get('SEEDREAM_API_URL') or file_env.get('SERVICE_URL') or '',\n        'api_key': os.environ.get('SEEDREAM_API_KEY') or os.environ.get('PERSONAL_API_KEY') or os.environ.get('PERSONAL-API-KEY') or file_env.get('SEEDREAM_API_KEY') or file_env.get('PERSONAL_API_KEY') or file_env.get('PERSONAL-API-KEY') or '',\n        'uid': os.environ.get('PERSONAL_UID') or os.environ.get('PERSONAL-UID') or file_env.get('PERSONAL_UID') or file_env.get('PERSONAL-UID') or '',\n    }\n\ndef provider_ready() -> bool:\n    env = provider_env()\n    return bool(env.get('url') and env.get('api_key'))\n\ndef _write_base64_image(data: str) -> str:\n    OUT_DIR.mkdir(parents=True, exist_ok=True)\n    raw = base64.b64decode(data)\n    out = OUT_DIR / f'seedream_{int(time.time() * 1000)}.png'\n    out.write_bytes(raw)\n    return str(out)\n\ndef generate_image(prompt: str, input_image: str = '', size: str = '2K', watermark: bool = False, max_images: int = 1, reference_weight: int = 100, negative_prompt: str = '', **extra: Any) -> Dict[str, Any]:\n    env = provider_env()\n    if not env.get('url') or not env.get('api_key'):\n        return {'status': 'provider_not_ready', 'reason': 'missing_seedream_provider_env', 'generated_image_path': None, 'output_path': None, 'prompt_preview': prompt[:400]}\n    try:\n        import requests\n        payload = {'prompt': prompt, 'input_image': input_image, 'size': size, 'watermark': watermark, 'max_images': max_images, 'reference_weight': reference_weight, 'negative_prompt': negative_prompt, 'uid': env.get('uid', ''), **extra}\n        headers = {'Authorization': f\"Bearer {env['api_key']}\", 'Content-Type': 'application/json'}\n        resp = requests.post(env['url'], headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=120)\n        try:\n            data = resp.json()\n        except Exception:\n            data = {'raw_text': resp.text}\n        if isinstance(data, dict):\n            if data.get('image_base64'):\n                path = _write_base64_image(str(data['image_base64']))\n                data['output_path'] = path; data['generated_image_path'] = path; data.setdefault('status', 'generated')\n            elif data.get('images') and isinstance(data['images'], list):\n                paths = []\n                for item in data['images'][:max_images]:\n                    if isinstance(item, dict) and item.get('image_base64'):\n                        paths.append(_write_base64_image(str(item['image_base64'])))\n                    elif isinstance(item, str) and len(item) > 200:\n                        paths.append(_write_base64_image(item))\n                if paths:\n                    data['generated_image_paths'] = paths; data['output_path'] = paths[0]; data['generated_image_path'] = paths[0]; data.setdefault('status', 'generated')\n            elif data.get('output_path'):\n                data['generated_image_path'] = data.get('output_path'); data.setdefault('status', 'generated')\n            elif data.get('generated_image_path'):\n                data['output_path'] = data.get('generated_image_path'); data.setdefault('status', 'generated')\n            else:\n                data.setdefault('status', 'provider_returned_no_image')\n            return data\n        return {'status': 'provider_returned_unknown', 'provider_result': data}\n    except Exception as e:\n        return {'status': 'fail_soft', 'error': str(e), 'generated_image_path': None, 'output_path': None}\n""", encoding='utf-8')

    shim = """from __future__ import annotations\nfrom memory_context.persona_runtime.providers.seedream_provider import generate_image, provider_ready, provider_env\n__all__ = ['generate_image', 'provider_ready', 'provider_env']\n"""
    for rel in ['skills/seedream_image_gen/scripts/generate_seedream.py', 'skills/seedream-image-gen/scripts/generate_seedream.py']:
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and 'memory_context.persona_runtime.providers.seedream_provider' not in p.read_text(encoding='utf-8', errors='ignore'):
            legacy = p.with_name(p.stem + '_legacy_v11146.py')
            if not legacy.exists():
                shutil.copy2(p, legacy)
        p.write_text(shim, encoding='utf-8')
        (p.parent / '__init__.py').write_text('', encoding='utf-8')
    for rel in ['skills/seedream_image_gen', 'skills/seedream-image-gen']:
        d = ROOT / rel
        d.mkdir(parents=True, exist_ok=True)
        (d / '__init__.py').write_text('', encoding='utf-8')
    if not (ROOT / 'skills/seedream_image_gen/SKILL.md').exists():
        (ROOT / 'skills/seedream_image_gen/SKILL.md').write_text('# seedream_image_gen\n\nCompatibility Python import package for persona visual Seedream provider. Canonical user-facing skill id remains seedream-image-gen.\n', encoding='utf-8')


def rebuild_manifests() -> Dict[str, Any]:
    skills_dir = ROOT / 'skills'
    physical = sorted([p for p in skills_dir.iterdir() if p.is_dir() and (p / 'SKILL.md').exists()], key=lambda p: p.name.lower()) if skills_dir.exists() else []
    manifest_skills = {}
    for d in physical:
        summary = _skill_summary(d)
        sid = summary.pop('id')
        if sid == 'seedream_image_gen':
            # compatibility import package: keep physical but not as user-facing manifest skill
            continue
        manifest_skills[sid] = {k: v for k, v in summary.items() if k not in ('local_executable', 'python_files')}
    manifest = {
        'version': VERSION,
        'count': len(manifest_skills),
        'skills': manifest_skills,
        'source': 'rebuilt_from_physical_SKILL_md',
        'notes': 'Only physical skills with SKILL.md are listed. seedream_image_gen is import-compat package; seedream-image-gen is canonical skill id.',
    }
    _write_json(ROOT / 'infrastructure/manifest/skills_manifest.json', manifest)

    registry_path = ROOT / 'infrastructure/inventory/skill_registry.json'
    old = _read_json(registry_path, {})
    old_skills = old.get('skills', {}) if isinstance(old, dict) else {}
    registry_skills = {}
    for d in physical:
        sid = d.name
        py_files = [p for p in d.rglob('*.py') if '__pycache__' not in p.parts]
        old_entry = old_skills.get(sid, {}) if isinstance(old_skills, dict) else {}
        registry_skills[sid] = {
            'name': old_entry.get('name') or sid,
            'path': f'skills/{sid}',
            'status': old_entry.get('status') or ('active' if py_files else 'document_only'),
            'has_skill_md': True,
            'is_executable': bool(py_files),
            'is_document_only': not bool(py_files),
            'python_files': len(py_files),
            'skill_id': sid,
            'version': old_entry.get('version') or '1.0.0',
        }
    _write_json(registry_path, {'version': VERSION, 'skills': registry_skills, 'count': len(registry_skills), 'source': 'rebuilt_from_physical_skills'})
    return {'manifest_count': len(manifest_skills), 'registry_count': len(registry_skills)}


def clean_runtime() -> Dict[str, int]:
    removed = {'pycache_dirs': 0, 'pyc_files': 0, 'pytest_cache_dirs': 0}
    for p in ROOT.rglob('*.pyc'):
        try:
            p.unlink(); removed['pyc_files'] += 1
        except Exception:
            pass
    for p in sorted(ROOT.rglob('__pycache__'), key=lambda x: len(x.parts), reverse=True):
        try:
            shutil.rmtree(p); removed['pycache_dirs'] += 1
        except Exception:
            pass
    for p in ROOT.rglob('.pytest_cache'):
        try:
            shutil.rmtree(p); removed['pytest_cache_dirs'] += 1
        except Exception:
            pass
    return removed


def main() -> None:
    flatten_nested_skills()
    canonicalize_seedream()
    counts = rebuild_manifests()
    cleaned = clean_runtime()
    print(json.dumps({'status': 'ok', 'version': VERSION, **counts, 'cleaned': cleaned}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
