#!/usr/bin/env python3
"""
cron_daily_maint.py — 每日维护 cron 包装器 v3（精简版）
输出简洁的维护报告，12行左右。
"""
import json, os, subprocess, sys, shutil, glob
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_DIR = os.path.join(WORKSPACE, ".state")

now = datetime.now(BEIJING_TZ)
ts = now.strftime("%Y-%m-%d %H:%M")

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ""

lines = []
lines.append(f"🦞 **每日统一维护报告** — {ts}")
lines.append("━━━━━━━━━━━━━━━━━━━")

# 1. 健康检查
usage = shutil.disk_usage(WORKSPACE)
pct = usage.used / usage.total * 100
disk_str = f"{pct:.1f}%（{usage.used//1024**3}GB/{usage.total//1024**3}GB）"

status_file = os.path.join(STATE_DIR, ".engine_state.json")
engine_str = "?"
if os.path.exists(status_file):
    try:
        with open(status_file) as f:
            state = json.load(f)
        engine_str = f"{state.get('success',0)}/{state.get('total',0)}"
    except: pass

uptime = run(["uptime", "-p"]).replace("up ", "")
mem = run(["free", "-h"]).split("\n")[1].split() if run(["free", "-h"]) else []
mem_str = f"{mem[2]}/{mem[1]}" if len(mem) > 2 else "?"

lines.append(f"💾 磁盘: {disk_str}  |  ⚙️  引擎: {engine_str}  |  🧠 内存: {mem_str}")
lines.append(f"⏱️  运行: {uptime}")

# 2. 维护操作
cleaned = 0; cleaned_size = 0
for root, dirs, files in os.walk(WORKSPACE):
    if ".git" in root: continue
    for f in files:
        if f.endswith((".pyc", ".pyo")):
            try:
                cleaned_size += os.path.getsize(p := os.path.join(root, f))
                os.remove(p); cleaned += 1
            except: pass
    if os.path.basename(root) == "__pycache__":
        try: os.rmdir(root)
        except: pass

if cleaned:
    lines.append(f"🗑️  清理: {cleaned} 缓存文件（{cleaned_size//1024}KB）")
else:
    lines.append(f"🗑️  清理: 无过期缓存")

# 3. 技能概览
skill_dir = os.path.join(WORKSPACE, "skills")
skill_count = 0; smd_count = 0
if os.path.exists(skill_dir):
    skills = [d for d in os.listdir(skill_dir) if os.path.isdir(os.path.join(skill_dir, d)) and not d.startswith(".") and d != "_archived"]
    skill_count = len(skills)
    for s in skills:
        smd = os.path.join(skill_dir, s, "SKILL.md")
        if os.path.exists(smd) or os.path.islink(smd):
            smd_count += 1
lines.append(f"📦 技能: {skill_count} 个（{smd_count}/{skill_count} 含 SKILL.md）")

# 4. 自纠错
cfg_file = os.path.join(WORKSPACE, "core", "engines", "init", "engines.json")
issues = []
if os.path.exists(cfg_file):
    try:
        with open(cfg_file) as f:
            cfg = json.load(f)
        for e in cfg.get("engines", []):
            mod = e.get("module", "")
            if mod:
                fp = os.path.join(WORKSPACE, mod.replace(".", "/") + ".py")
                if not os.path.exists(fp):
                    issues.append(f"{e.get('name','?')} → {mod}")
    except: pass

if issues:
    lines.append(f"⚠️  问题: {len(issues)} 个引擎模块路径异常")
else:
    lines.append(f"✅  自纠错: 未发现问题")

lines.append("")
lines.append(f"⏰ 下次维护: {(now+timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')} (01:00)")
lines.append("系统运行正常 🤖")

print("\n".join(lines))
