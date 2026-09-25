#!/usr/bin/env python3
"""
通用自动补丁器 (2026-09-25 通用化 · 支持 restore 型)

配置驱动: 读取同目录 patch_autoheal_config.json 中的 targets 列表。
两种目标类型(配置 type 字段):
  - "patch"   : 往目标文件插桩(insertPoint 后插入 insert + replacements)
  - "restore" : 目标文件缺失/核心逻辑被冲时, 从 backupPath 整体恢复
统一流程: 存在性检查 → marker 检测 → 缺失则 备份→(插桩|整体恢复)→语法检查→失败回滚。

命令:
  check         仅检测各目标状态(缺失则退出码 2)
  patch         对缺失目标执行补丁/恢复
  --restart     处理成功且 restartOnPatch 时执行 restartCmd(如重启 gateway)

退出码: 0=全部已补/无动作, 1=有目标已处理, 2=缺失(check)/有失败回滚, 3=配置读取失败
"""
import json
import os
import shutil
import subprocess
import sys
import time

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patch_autoheal_config.json")


def log(msg):
    print(msg, flush=True)


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def syntax_check(t):
    """按 type 做语法检查。js→node --check。未知类型视为通过。"""
    if t.get("type") in ("js", "patch", "restore") and os.path.exists(t.get("path", "")):
        r = subprocess.run(["node", "--check", t["path"]],
                           capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:300]
    return True, ""


def backup(path, tag="bak-autoheal"):
    bak = f"{path}.{tag}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, bak)
    return bak


def restore_target(t, do_restart, name):
    """整体恢复目标文件(从 backupPath)。"""
    path, bk = t["path"], t.get("backupPath")
    if not os.path.exists(bk):
        return "rollback", f"[{name}] 备份不存在，无法恢复: {bk}"
    try:                      # 先保留损坏文件便于排查
        backup(path, tag="bak-corrupt")
    except FileNotFoundError:
        pass
    shutil.copy2(bk, path)
    ok, err = syntax_check(t)
    if not ok:
        try:
            shutil.copy2(bk, path)  # 再留一份未验证版本? 不, 回滚为当前已恢复内容
        except FileNotFoundError:
            pass
        return "rollback", f"[{name}] 恢复后语法检查失败: {err}"
    if do_restart and t.get("restartOnPatch"):
        subprocess.run(t["restartCmd"], timeout=120)
        return "patched", f"[{name}] 已从备份整体恢复并执行重启"
    return "patched", f"[{name}] 已从备份整体恢复"


def process_target(t, do_restart, mode):
    path = t["path"]
    name = t.get("name", path)
    rtype = t.get("type", "patch")

    if not os.path.exists(path):
        if rtype == "restore":
            if mode == "check":
                return "need", f"[{name}] 文件缺失(待恢复)"
            return restore_target(t, do_restart, name)
        return "missing", f"[{name}] 文件不存在: {path}"

    with open(path, encoding="utf-8") as f:
        c = f.read()
    if t["marker"] in c:
        return "ok", f"[{name}] 已含核心逻辑，无需处理"
    if mode == "check":
        return "need", f"[{name}] 缺失核心逻辑"

    if rtype == "restore":
        return restore_target(t, do_restart, name)

    # ---- patch 型: 插桩 ----
    bak = backup(path)
    try:
        ip = t.get("insertPoint")
        if ip:
            if ip not in c:
                raise RuntimeError(f"未找到插入锚点: {ip}")
            c = c.replace(ip, ip + "\n" + t.get("insert", ""), 1)
        for r in t.get("replacements", []):
            if r["from"] not in c:
                raise RuntimeError(f"未找到替换目标: {r['from']}")
            c = c.replace(r["from"], r["to"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(c)
        ok, err = syntax_check(t)
        if not ok:
            shutil.copy2(bak, path)
            return "rollback", f"[{name}] 语法检查失败已回滚: {err}"
        if do_restart and t.get("restartOnPatch"):
            subprocess.run(t["restartCmd"], timeout=120)
            return "patched", f"[{name}] 已补丁并执行重启"
        return "patched", f"[{name}] 已补丁"
    except Exception as exc:
        shutil.copy2(bak, path)
        return "rollback", f"[{name}] 失败已回滚: {exc}"


def main():
    args = sys.argv[1:]
    mode = "check" if "check" in args else "patch"
    do_restart = "--restart" in args

    try:
        cfg = load_config()
    except Exception as exc:
        log(f"[patch_autoheal] 配置读取失败: {exc}")
        return 3

    results = [process_target(t, do_restart, mode) for t in cfg["targets"]]
    statuses = [s for s, _ in results]
    for _, msg in results:
        log(msg)

    if mode == "check":
        return 2 if "need" in statuses else 0
    if "rollback" in statuses:
        return 2
    return 1 if "patched" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
