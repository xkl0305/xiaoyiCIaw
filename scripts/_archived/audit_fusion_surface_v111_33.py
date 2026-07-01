from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
checks = {
    "sitecustomize": (ROOT / "sitecustomize.py").exists(),
    "root_openclaw": (ROOT / "openclaw.json").exists(),
    "hook_bus": (ROOT / "infrastructure/hook_bus.py").exists(),
    "reply_outlet": (ROOT / "infrastructure/persona_visual_reply_outlet.py").exists(),
    "hooks": (ROOT / ".openclaw/hooks/pre_reply.py").exists() and (ROOT / ".openclaw/hooks/post_reply.py").exists(),
}
out = {"status": "ok" if all(checks.values()) else "warn", "checks": checks}
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports/V111_33_INTEGRATION_AUDIT.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
(ROOT / "reports/V111_33_INTEGRATION_AUDIT.txt").write_text(
    "status: " + out["status"] + "\n" + json.dumps(checks, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(json.dumps(out, ensure_ascii=False, indent=2))
