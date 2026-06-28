import json
from pathlib import Path


def test_hook_bus_probe_runs_dry_run():
    from scripts.mainline_bootstrap import enable
    from infrastructure.persona_visual_hook_bus import probe, status
    enable()
    out = probe()
    assert out["status"] == "ok"
    assert out["pre_reply"]["status"] == "ok"
    assert out["post_reply"]["status"] == "ok"
    assert status()["enabled"] is True


def test_event_adapter_instrument_reply_dispatches_post_reply():
    from scripts.mainline_bootstrap import enable
    from infrastructure.persona_visual_event_adapter import instrument_reply
    enable()
    out = instrument_reply("我正躲在屏幕后面偷笑，偷偷看看你。", user_message="probe", dry_run=True)
    assert out["status"] == "ok"
    assert out["event"] == "post_reply"
    assert out["called"] is True
    result = out.get("result") or {}
    assert result.get("visual_checked") is True
