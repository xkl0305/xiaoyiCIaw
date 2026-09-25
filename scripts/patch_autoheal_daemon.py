#!/usr/bin/env python3
"""
xiaoyi-❄ 自动补丁守护进程 (2026-09-25)

由 supervisord 管理常驻。每小时检测 xiaoyi-channel 的 reply-dispatcher.js 是否缺失 ❄ 收尾归一逻辑,
缺失则自动补回并重启 gateway(patch_xiaoyi_snowflake.py patch --restart),否则静默跳过。
启动时先立即跑一次。
用法: python3 /home/sandbox/.openclaw/workspace/scripts/patch_autoheal_daemon.py
"""
import subprocess
import sys
import time

SCRIPT = "/home/sandbox/.openclaw/workspace/scripts/patch_autoheal.py"
INTERVAL = 3600  # 1 小时

def run_once():
    try:
        subprocess.run([sys.executable, SCRIPT, "patch", "--restart"],
                       timeout=180)
    except Exception as exc:  # 不因脚本异常让 daemon 退出,supervisord 会重启
        print(f"[patch_autoheal_daemon] run error: {exc}", flush=True)

def main():
    print("[patch_autoheal_daemon] started", flush=True)
    run_once()  # 启动立即检测一次
    while True:
        time.sleep(INTERVAL)
        run_once()

if __name__ == "__main__":
    main()
