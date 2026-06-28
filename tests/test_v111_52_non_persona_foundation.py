from pathlib import Path
import importlib
import json

ROOT = Path(__file__).resolve().parents[1]


def test_no_skills_import_facade_without_physical_skills_dir():
    assert not (ROOT / "skills").exists()
    registry = importlib.import_module("skills.registry")
    runtime = importlib.import_module("skills.runtime")
    assert registry.get_skill_registry() is not None
    assert runtime.get_skill_router() is not None


def test_seedream_logical_skill_still_provider_backed():
    mod = importlib.import_module("skills.seedream_image_gen.scripts.generate_seedream")
    provider = importlib.import_module("memory_context.persona_runtime.providers.seedream_provider")
    assert mod.generate_image is provider.generate_image


def test_application_root_facade_and_message_entrypoint_exist():
    scheduler = importlib.import_module("application.task_service.scheduler")
    assert hasattr(scheduler, "SchedulerService")
    assert (ROOT / "scripts" / "message_server.py").exists()


def test_automation_examples_and_online_policy_are_normalized():
    cfg = json.loads((ROOT / "openclaw.json").read_text(encoding="utf-8"))
    assert (ROOT / "config" / "crontab.example").exists()
    assert (ROOT / "config" / "systemd.example").exists()
    assert cfg["ONLINE_MODE"] is True
    assert cfg["OFFLINE_MODE"] is False
    assert cfg["ZERO_EXTERNAL_MODE"] is False
    assert cfg["NO_EXTERNAL_API"] is False
    assert cfg["connectedRuntime"]["alwaysConnected"] is True
    assert cfg["connectedRuntime"]["noPerActionOnlineAuthorization"] is True
