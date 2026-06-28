"""
P0 主人锚一致性守卫（2026-05-15 @ 鸽子王）

每次 pre_reply 自动运行。校验 5 处冗余存储是否一致。
检测到不一致时返回警告，不阻断运行（fail-soft）。

校验关键词集合（5 处都必须包含）：
  {主人, 鸽, lzx4139, 开发者主人, 双丸子头, 创造者, 拥有者}
"""

import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("WORKSPACE", __file__)).resolve()
if (ROOT / "openclaw.json").exists() is False:
    # walk up
    for p in [ROOT] + list(ROOT.parents):
        if (p / "openclaw.json").exists():
            ROOT = p
            break

ANCHOR_KEYWORDS = {"主人", "鸽", "lzx4139", "开发者主人", "双丸子头", "创造者", "拥有者"}

FILES_TO_CHECK = [
    ("MEMORY.md", ROOT / "MEMORY.md"),
    ("USER.md", ROOT / "USER.md"),
    ("IDENTITY.md", ROOT / "IDENTITY.md"),
    ("SOUL.md", ROOT / "SOUL.md"),
    ("relationship_memory.json", ROOT / ".memory_persona" / "relationship_memory.json"),
]


def check_file(name: str, path: Path) -> dict:
    """Check a single file for anchor keywords. Returns {file, found, missing}."""
    if not path.exists():
        return {"file": name, "found": [], "missing": list(ANCHOR_KEYWORDS), "status": "missing_file"}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"file": name, "found": [], "missing": list(ANCHOR_KEYWORDS), "status": f"read_error: {e}"}

    found = [kw for kw in ANCHOR_KEYWORDS if kw in text]
    missing = [kw for kw in ANCHOR_KEYWORDS if kw not in text]
    if len(missing) == 0:
        return {"file": name, "found": found, "missing": [], "status": "ok"}
    return {"file": name, "found": found, "missing": missing, "status": "partial"}


def run_consistency_check() -> dict:
    """Run full 5-file consistency check. Returns {consistent, results, warnings}."""
    results = [check_file(name, path) for name, path in FILES_TO_CHECK]
    all_ok = all(r.get("status") == "ok" for r in results)

    warnings = []
    if not all_ok:
        for r in results:
            if r.get("status") != "ok":
                warnings.append(f"[{r['file']}] status={r['status']}, missing={r.get('missing', [])}")

    return {
        "consistent": all_ok,
        "anchor_id": "OWNER_ANCHOR_20260515",
        "passed": all_ok,
        "results": results,
        "warnings": warnings,
    }


# ── 暴露给 hook 的入口 ──────────────────────────────────────

def verify() -> dict:
    """
    Entry point for pre_reply hook. Returns a verdict dict.
    Usage in pre_reply.py:
        from owner_anchor_guard import verify
        result = verify()
        if not result['consistent']:
            # log warning but don't block
    """
    return run_consistency_check()


# ── CLI 运行 ──────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_consistency_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["consistent"]:
        print("\n✅ 主人锚一致，所有 5 处冗余均通过校验。")
    else:
        print(f"\n⚠️ 检测到 {len(result['warnings'])} 处不一致！")
        for w in result["warnings"]:
            print(f"  • {w}")
