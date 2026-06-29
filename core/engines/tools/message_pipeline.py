"""
Crusheart Agent OS — 消息预处理流水线（兼容壳）
实际实现在 pipeline/orchestrator.py
保留此文件确保 import scripts.message_pipeline 兼容
"""

import sys, os

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)

from core.pipeline import run_pipeline

# 兼容旧引用
_instances = {}

def now_str():
    from datetime import datetime, timezone, timedelta
    BEIJING_TZ = timezone(timedelta(hours=8))
    return datetime.now(BEIJING_TZ).strftime("%H:%M:%S")

__all__ = ["run_pipeline", "_instances", "now_str"]

if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    import json
    user_msg = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    if not user_msg:
        result = {"error": "未提供用户消息"}
    else:
        result = run_pipeline(user_msg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
