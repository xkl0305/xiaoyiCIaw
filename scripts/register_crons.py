#!/usr/bin/env python3
"""
register_crons.py — 注册所有定时任务 v6.6.1

替代 register_crons.sh，纯 Python 实现，依赖 read_config.py 读取渠道配置。

v6.6.1: 使用 --message 替代 --system-event，
cron 到点发送消息到指定 channel，确保用户能收到推送。
channel 自动检测，不硬编码。

注册 2 个 --message 定时任务：
  [1/2] 01:00 统一维护（crusheart-daily-maintenance，含版本检查）
  [2/2] 05:00 引擎初始化（crusheart-engine-init）

用法：
  python3 scripts/register_crons.py              # 正常注册
  python3 scripts/register_crons.py --dry-run    # 模拟运行，不实际注册
  python3 scripts/register_crons.py --cleanup    # 仅清理旧任务
"""

import json
import os
import re
import subprocess
import sys
from typing import List, Optional

BEIJING_TZ = "Asia/Shanghai"
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


def log(msg: str):
    print(msg)


def get_channel() -> Optional[str]:
    """检测渠道名，优先级：read_config.py > .crusheart-channels.json > openclaw.json"""
    # 1. read_config.py (首选)
    rc_path = os.path.join(WORKSPACE, "scripts", "read_config.py")
    if os.path.exists(rc_path):
        try:
            r = subprocess.run(
                [sys.executable, rc_path, "--channel-names", "--json"],
                cwd=WORKSPACE, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                names = json.loads(r.stdout)
                if names:
                    return names[0]
        except Exception:
            pass

    # 2. .crusheart-channels.json
    cj_path = os.path.join(WORKSPACE, ".crusheart-channels.json")
    if os.path.exists(cj_path):
        try:
            with open(cj_path, encoding="utf-8") as f:
                data = json.load(f)
            channels = data.get("channels", [])
            if channels:
                return channels[0]
        except Exception:
            pass

    # 3. openclaw.json 直接扫
    config_dir = os.environ.get("OPENCLAW_CONFIG_DIR") or os.path.expanduser("~/.openclaw")
    cf_path = os.path.join(config_dir, "openclaw.json")
    if os.path.exists(cf_path):
        try:
            with open(cf_path, encoding="utf-8") as f:
                data = json.load(f)
            channels = data.get("channels", {})
            for k, v in channels.items():
                if isinstance(v, dict) and v.get("enabled", False):
                    return k
            if channels:
                return list(channels.keys())[0]
        except Exception:
            pass

    return None


def get_old_cron_ids() -> List[str]:
    """获取本插件注册的旧定时任务 ID 列表
    
    逐行匹配，只收集关键词所在行的 ID，避免误删其他插件/用户的 cron。
    """
    try:
        r = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return []
        output = r.stdout + r.stderr

        # 匹配模式：crusheart/统一维护/引擎初始化/版本检查/记忆维护/引擎重初始化
        pattern = re.compile(
            r'(crusheart|统一维护|引擎初始化|版本检查|记忆维护|引擎重初始化)',
            re.IGNORECASE
        )
        ids = []
        for line in output.splitlines():
            if pattern.search(line):
                found = re.findall(r'id="([^"]+)"', line)
                ids.extend(found)
        return ids
    except Exception:
        return []


def cleanup_old_crons(dry_run: bool = False) -> int:
    """清理旧任务，返回清理数量"""
    ids = get_old_cron_ids()
    if not ids:
        log("  没有找到旧定时任务")
        return 0

    log(f"  找到 {len(ids)} 个旧任务，正在清理...")
    for cid in ids:
        if dry_run:
            log(f"    [DRY] 删除: {cid}")
        else:
            subprocess.run(
                ["openclaw", "cron", "rm", cid],
                capture_output=True, timeout=10
            )
    return len(ids)


def add_cron(name: str, cron_expr: str, channel: str,
             dry_run: bool = False,
             message: str = "🔔 定时任务触发",
             session_key: Optional[str] = None) -> bool:
    """注册单个定时任务（v6.6.1: 统一 --message 模式）"""
    cmd = [
        "openclaw", "cron", "add",
        "--cron", cron_expr,
        "--name", name,
        "--channel", channel,
        "--expect-final",
        "--exact",
    ]
    cmd += ["--message", message, "--session", "isolated"]
    if session_key:
        cmd += ["--session-key", session_key]
    if dry_run:
        log(f"    [DRY] openclaw cron add --name {name} --cron {cron_expr} --channel {channel}")
        return True

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            log(f"    ✅ {name}")
            return True
        else:
            log(f"    ❌ {name}: {r.stderr.strip()[:100]}")
            return False
    except Exception as e:
        log(f"    ❌ {name}: {str(e)[:100]}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    only_cleanup = "--cleanup" in sys.argv

    log("🕐 注册定时任务...")

    # 检测渠道
    channel = get_channel()
    if not channel:
        log("  ❌ 无法自动检测渠道名，请检查 openclaw.json 中 channels 配置")
        log("     或手动设置环境变量: export CRUSHEART_CHANNEL=your_channel_name")
        sys.exit(1)
    log(f"  默认 Channel: {channel}")

    # 检测 openclaw cron 可用性
    try:
        r = subprocess.run(["openclaw", "cron", "list"], capture_output=True, timeout=10)
        if r.returncode != 0:
            log("  ⚠️  openclaw cron 不可用，请确保 Gateway 正在运行")
            sys.exit(1)
    except FileNotFoundError:
        log("  ⚠️  openclaw 命令未找到，请确保 OpenClaw 已安装")
        sys.exit(1)

    # 清理旧任务
    log("  查找本插件注册的旧定时任务...")
    cleanup_old_crons(dry_run)

    if only_cleanup:
        log("")
        log("✅ 清理完成")
        return

    # 注册新任务
    log("")
    log("  注册 [1/2]: 01:00 统一维护")
    add_cron(
        name="crusheart-daily-maintenance",
        cron_expr="0 1 * * *",
        channel=channel,
        dry_run=dry_run,
        message="🦞 每日统一维护开始，后台自动执行中（crusheart-daily-maintenance）",
        session_key="cron:daily:maint",
    )

    log("  注册 [2/2]: 05:00 引擎初始化（带会话管理）")
    add_cron(
        name="crusheart-engine-init",
        cron_expr="0 5 * * *",
        channel=channel,
        dry_run=dry_run,
        message="🦞 执行引擎初始化与版本检查（crusheart-engine-init）",
        session_key="cron:engine-init:morning",
    )

    log("")
    log("✅ 定时任务注册完成（共 2 个）")
    log("")
    log("📌 使用 --message 模式，cron 触发后自动推送消息到指定 channel")


if __name__ == "__main__":
    main()
