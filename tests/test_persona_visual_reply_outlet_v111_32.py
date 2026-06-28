from pathlib import Path


def test_reply_outlet_finalize_calls_hook():
    from infrastructure.persona_visual_reply_outlet import finalize_reply
    out = finalize_reply("我正躲在屏幕后面偷笑，偷偷看看你。", user_message="probe", source="pytest.v111_32", dry_run=True)
    assert out["status"] in {"ok", "skip"}
    assert Path(".openclaw/hook_state/reply_outlet_events.jsonl").exists()
    if out["status"] == "ok":
        assert "hook_result" in out


def test_sitecustomize_installs_global_hooks():
    import sitecustomize  # noqa: F401
    from infrastructure.persona_visual_reply_outlet import status
    st = status()
    assert st["status"] == "ok"
    assert Path(st["patch_state_file"]).exists()


def test_response_renderer_to_user_message_triggers_outlet():
    from execution.application.response_service.renderer import ResponseRenderer, RenderedResponse
    rr = ResponseRenderer()
    response = RenderedResponse(status="success", summary="我正躲在屏幕后面偷笑，偷偷看看你。", completed_items=[], incomplete_items=[], evidences=[], next_steps=[])
    text = rr.to_user_message(response)
    assert "偷偷" in text
    assert Path(".openclaw/hook_state/reply_outlet_events.jsonl").exists()
