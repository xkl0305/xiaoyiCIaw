#!/usr/bin/env python3
"""
确保微信通道配置持久化写入 openclaw.json，防止 Gateway 重启后配置被覆盖。

问题背景：
- openclaw channels login 会修改 openclaw.json（添加 plugins.entries.openclaw-weixin 和 channels.openclaw-weixin）
- 但 Gateway 重启时会用自己的内存状态覆盖配置文件，可能"吃掉"这些新增条目
- 此脚本在重启 Gateway 前执行，确保配置已写入文件

用法：
  python3 ensure_weixin_config.py
"""
import json
import os
import shutil
from datetime import datetime, timezone

CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
BACKUP_PATH = CONFIG_PATH + ".weixin_bak"


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 未找到配置文件: {CONFIG_PATH}")
        return 1

    # 备份
    shutil.copy2(CONFIG_PATH, BACKUP_PATH)
    print(f"📦 已备份原配置: {BACKUP_PATH}")

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    changed = False

    # 1. 确保 plugins.entries.openclaw-weixin 存在
    weixin_entry = config.setdefault("plugins", {}).setdefault("entries", {}).get("openclaw-weixin")
    if weixin_entry is None:
        config["plugins"]["entries"]["openclaw-weixin"] = {"enabled": True}
        print("✅ 已添加 plugins.entries.openclaw-weixin: { enabled: true }")
        changed = True
    else:
        print(f"✔ plugins.entries.openclaw-weixin 已存在: {json.dumps(weixin_entry)}")

    # 2. 确保 channels.openclaw-weixin 存在
    weixin_channel = config.setdefault("channels", {}).get("openclaw-weixin")
    if weixin_channel is None:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        config["channels"]["openclaw-weixin"] = {"channelConfigUpdatedAt": now_iso}
        print(f"✅ 已添加 channels.openclaw-weixin: channelConfigUpdatedAt={now_iso}")
        changed = True
    else:
        print(f"✔ channels.openclaw-weixin 已存在: {json.dumps(weixin_channel)}")

    if not changed:
        print("✔ 微信配置已完整存在，无需修改，可以直接重启 Gateway。")
        return 0

    # 写回文件
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.write("\n")

    print(f"✅ 配置已写入: {CONFIG_PATH}")
    print("✅ 现在可以安全重启 Gateway 了。")
    return 0


if __name__ == "__main__":
    exit(main())
