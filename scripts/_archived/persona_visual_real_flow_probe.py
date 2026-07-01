#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from infrastructure.persona_visual_reply_outlet import finalize_reply, status as outlet_status
from infrastructure.persona_visual_hook_bus import status as bus_status

msg = "我正躲在屏幕后面偷笑，偷偷看看你。"
out = finalize_reply(msg, user_message="probe", source="real_flow_probe", phase="post_reply", dry_run=True)
print(json.dumps({"status":"ok", "reply_outlet_result": out, "reply_outlet_status": outlet_status(), "hook_bus_status": bus_status()}, ensure_ascii=False, indent=2))
