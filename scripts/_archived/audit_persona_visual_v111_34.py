from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from memory_context.persona_runtime.persona_visual_intent_predictor import predict_visual_intent
cases = {
    "sneaky": "偷偷看看你",
    "happy": "开心",
    "angry": "生气",
    "sad": "委屈难过",
    "wardrobe": "打开衣柜换睡衣",
    "tired": "累趴了",
}
res = {k: predict_visual_intent(v) for k, v in cases.items()}
ok = all(v.get("auto_generation_candidate") for v in res.values())
out = {"status": "ok" if ok else "warn", "cases": res}
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports/V111_34_MERGED_AUDIT.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
(ROOT / "reports/V111_34_MERGED_AUDIT.txt").write_text(
    "status: " + out["status"] + "\n" + json.dumps(res, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(json.dumps(out, ensure_ascii=False, indent=2))
