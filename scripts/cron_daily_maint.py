#!/usr/bin/env python3
"""
cron_daily_maint.py — 每日维护 cron 包装器 v5
直接输出 daily_maintenance.py --report 完整内容，不做任何截断或摘要。
"""
import os, sys, subprocess

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

r = subprocess.run(
    [sys.executable, os.path.join(WORKSPACE, "scripts/_archived/daily_maintenance.py"), "--report"],
    capture_output=True, text=True, timeout=180
)
print(r.stdout.strip())
if r.stderr.strip():
    # 只保留非 jieba 预留给输出
    filtered = [l for l in r.stderr.split("\n") if "jieba" not in l and "DEBUG:" not in l]
    if filtered:
        print("--- stderr ---")
        print("\n".join(filtered).strip())
