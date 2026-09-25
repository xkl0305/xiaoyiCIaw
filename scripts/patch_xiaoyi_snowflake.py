#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xiaoyi-channel ❄️ 收尾代码级兜底 · 自动补丁脚本
功能：检测 reply-dispatcher.js 是否缺失 ❄ 归一逻辑，缺失则自动重打补丁（备份+插桩+语法检查）。
用途：xiaoyi-channel 插件每次更新/重装会用官方 dist 覆盖，冲掉手动加在 final 帧发送处的
      ❄ 收尾归一代码。本脚本让"老要补"变"自动补"。
用法：
  python3 patch_xiaoyi_snowflake.py check       # 仅检测是否已补，不修改
  python3 patch_xiaoyi_snowflake.py patch       # 缺失则补丁；已补则跳过
  python3 patch_xiaoyi_snowflake.py patch --restart   # 补丁成功后重启 gateway（仅确实重打时重启）
退出码：0=已补/无需动作, 1=补丁完成, 2=缺失但补丁失败/结构变化, 3=文件不存在
"""
import os
import subprocess
import sys
import time

TARGET = "/home/sandbox/.openclaw/extensions/xiaoyi-channel/dist/src/dispatch/reply-dispatcher.js"
BACKUP_DIR = "/home/sandbox/.openclaw/extensions/xiaoyi-channel/dist/src/dispatch"

# 目标归一逻辑的完整行（❄️ = U+2744 + U+FE0F，与端侧文本一致，正则才能匹配）
MARKER = 'const normalizedFinalText = fullFinalText.replace(/\\s*\u2744\ufe0f\\s*$/, "\u2744\ufe0f");'

# 插入锚点：`if (fullFinalText) {` 独行
IF_ANCHOR = "                        if (fullFinalText) {"
# 插入内容：注释 + 归一定义（❄️ 用转义表示，避免源码 emoji 显示歧义）
INSERT_BLOCK = (
    "                        if (fullFinalText) {\n"
    "                            // \U0001F9A7 \u2744\ufe0f \u6536\u5c3e\u4ee3\u7801\u7ea7\u5957\u5e95\uff1a\u53d1\u9001 final \u5e27\u524d\u628a\u672b\u5c3e\u6362\u884c/\u7a7a\u683c\u6536\u7d27\u4e3a\u7d27\u8d34\u7684 \u2744\ufe0f\uff082026-09-25 \u81ea\u52a8\u8865\u4e01\uff09\n"
    "                            const normalizedFinalText = fullFinalText.replace(/\\s*\u2744\ufe0f\\s*$/, \"\u2744\ufe0f\");\n"
)

# final 帧发送参数：text: fullFinalText, → text: normalizedFinalText,
OLD_TEXT = "text: fullFinalText,"
NEW_TEXT = "text: normalizedFinalText,"


def has_patch(content):
    return MARKER in content


def apply_patch(content):
    if IF_ANCHOR not in content:
        return None, "找不到插入锚点 `if (fullFinalText) {`，结构可能已变"
    if OLD_TEXT not in content:
        return None, "找不到 `text: fullFinalText,`，结构可能已变"
    patched = content.replace(IF_ANCHOR, INSERT_BLOCK, 1)
    patched = patched.replace(OLD_TEXT, NEW_TEXT, 1)
    return patched, None


def main():
    mode = "check"
    do_restart = "--restart" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        mode = args[0]

    if not os.path.exists(TARGET):
        print(f"[\U0001F6A8] 目标文件不存在: {TARGET}")
        return 3

    with open(TARGET, encoding="utf-8") as f:
        content = f.read()

    if has_patch(content):
        print("[\u2705] reply-dispatcher.js 已含 ❄️ 归一逻辑，无需补丁")
        return 0

    if mode == "check":
        print("[\u26A0\ufe0f] 检测到缺失：❄️ 归一逻辑不在当前文件（插件可能被更新冲掉）")
        print("    运行 `patch_xiaoyi_snowflake.py patch` 自动补回")
        return 2

    # patch 模式
    patched, err = apply_patch(content)
    if err:
        print(f"[\U0001F6AB] {err}")
        return 2

    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = os.path.join(BACKUP_DIR, f"reply-dispatcher.js.bak-autopatch-{ts}")
    with open(bak, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[\U0001F4BE] 已备份: {bak}")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(patched)

    r = subprocess.run(["node", "--check", TARGET], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[\U0001F6AB] node --check 失败，回滚补丁:\n{r.stderr}")
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(content)
        return 2

    print("[\u2705] 补丁已生效，node --check 通过")

    if do_restart:
        rr = subprocess.run(
            ["python3", "-m", "supervisor.supervisorctl", "-c", "/home/sandbox/supervisord.conf", "restart", "openclaw-gateway"],
            capture_output=True, text=True,
        )
        print("[\u21BA\ufe0f] gateway 重启结果:", rr.stdout.strip() or rr.stderr.strip())
    return 1


if __name__ == "__main__":
    sys.exit(main())
