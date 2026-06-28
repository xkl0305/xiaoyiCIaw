from pathlib import Path
import importlib
import json

ROOT = Path(__file__).resolve().parents[1]


def test_seedream_no_skills_direct_provider_registered():
    provider = importlib.import_module('memory_context.persona_runtime.providers.seedream_provider')
    assert hasattr(provider, 'generate_image')
    assert not (ROOT / 'skills').exists()


def test_manifest_uses_direct_provider_no_physical_skill():
    manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    direct = manifest.get('seedream_provider_direct', {})
    assert manifest.get('package_mode') == 'no_skills_direct_provider'
    assert direct.get('provider_backed') is True
    assert direct.get('physical_skill_required') is False
    assert 'skills/seedream-image-gen/SKILL.md' not in manifest.get('requires', [])


def test_skill_registry_marks_seedream_as_provider_backed_logical_capability():
    registry = json.loads((ROOT / 'infrastructure/inventory/skill_registry.json').read_text(encoding='utf-8'))
    skill = registry['skills']['seedream-image-gen']
    assert skill.get('provider_backed') is True
    assert skill.get('physical_skill_required') is False
    assert skill.get('entry_point') == 'memory_context.persona_runtime.providers.seedream_provider.generate_image'
