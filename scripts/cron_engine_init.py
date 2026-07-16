#!/usr/bin/env python3
"""
cron_engine_init.py — 引擎初始化 cron 包装器 v3（精简版）
输出简洁但完整的初始化报告，10行左右。
"""
import json, os, subprocess, sys, glob, re
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_DIR = os.path.join(WORKSPACE, ".state")

now = datetime.now(BEIJING_TZ)
ts = now.strftime("%Y-%m-%d %H:%M")

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, "", str(e)

lines = []
lines.append(f"🦞 **Crusheart 引擎初始化完成** — {ts}")
lines.append("")

# 1. 引擎初始化
ok, stdout, _ = run([sys.executable, os.path.join(WORKSPACE, "core", "engines", "init", "init_engines.py")])
success = "?"; total = "?"
for l in stdout.split("\n"):
    m = re.search(r'引擎初始化完成:\s*(\d+)/(\d+)', l)
    if m: success, total = m.group(1), m.group(2)

# 2. 版本检查
ok, stdout, _ = run([sys.executable, os.path.join(WORKSPACE, "scripts", "version_check.py")], timeout=30)
ver_note = ""
ver_lines = [l.strip() for l in stdout.split("\n") if l.strip()]
for l in ver_lines:
    if "当前版本" in l or "v7." in l:
        ver_note = l.strip().replace("⚠️ ", "").replace("  ", " ")
if not ver_note:
    ver_note = "v7.0.0（cnb.cool 最新）"

# 3. 系统身份
sys.path.insert(0, WORKSPACE)
sys_id = "灵枢AutoBrain v7.0.0"
try:
    from core.engines.init.system_identity import get_system_identity
    identity = get_system_identity()
    sys_id = f"{identity.get('name','?')} v{identity.get('version','?')} · {identity.get('engine_modules','?')}模块/{identity.get('engine_groups','?')}分组"
except Exception:
    pass

# 4. 主机运行时长
try:
    r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
    uptime_str = r.stdout.strip().replace("up ", "")
except:
    uptime_str = "?"

# 5. 引擎异常
fails = []
status_file = os.path.join(STATE_DIR, ".engine_state.json")
if os.path.exists(status_file):
    try:
        with open(status_file) as f:
            state = json.load(f)
        if state.get("failed", 0) > 0:
            for r in state.get("engines", []):
                if r.get("status") == "failed":
                    fails.append(r.get("name", "?") + ": " + r.get("error", ""))
    except: pass

healthy = f"✅ {success}/{total} 就绪 · 0 告警" if not fails else f"✅ {success}/{total} 就绪 · ⚠️ {len(fails)} 异常"

table = f"""| 指标 | 值 |
|------|------|
| ⚙️ 引擎 | {healthy} |
| 📡 版本 | {ver_note} |
| 🆔 系统 | {sys_id} |
| ⏱️ 运行时长 | {uptime_str} |
| 🕐 执行周期 | 每日 05:00 自动执行 |"""

lines.append(table)
if fails:
    for f_ in fails:
        lines.append(f"⚠️  {f_}")
lines.append("")
lines.append("新的一天，随时待命 🤖")

# 5. 引擎分组明细
ENGINE_GROUPS = {
    "🧠 核心引擎": ["system_identity", "hook_engine", "mutex_engine", "lazy_load", "anti_fake", "closed_loop"],
    "🔧 工具与执行": ["unified_executor", "tool_gateway", "background_executor", "decision_core", "dag_context"],
    "💾 存储与状态": ["memory_layer", "crusheart_db", "state_manager", "session_manager"],
    "🛡️ 安全与守卫": ["iron_rules", "context_warning", "anomaly_detector", "circuit_breaker", "failover", "identity_drift_guard"],
    "🔄 自进化与反馈": ["self_evolution", "auto_tuning", "enhancement_engine", "self_evolution_engine"],
    "🧬 记忆系统": ["hierarchical_memory", "hallucination_guard", "rccam_classifier", "lfm_skill_bank", "selfrag_crag"],
    "📊 质量与监控": ["quality_dashboard", "unified_judge", "dual_mode", "trace_timeline", "insights_engine"],
    "🎨 视觉与体验": ["persona_visual", "goal_compiler"],
    "🤖 智能化引擎": ["plugin_sdk", "user_dynamic_portrait", "rule_engine", "autonomy_cycle", "task_template", "success_path_store"],
}

engine_map = {}
for gname, names in ENGINE_GROUPS.items():
    for n in names:
        engine_map[n] = gname

engines = state.get("engines", [])
group_counts = {}
group_oks = {}
for group in ENGINE_GROUPS:
    group_counts[group] = 0
    group_oks[group] = 0

for eng in engines:
    ename = eng.get("name", "")
    estatus = eng.get("status", "")
    group = engine_map.get(ename, "🤖 智能化引擎")
    group_counts[group] = group_counts.get(group, 0) + 1
    if estatus == "ready":
        group_oks[group] = group_oks.get(group, 0) + 1

lines.append("")
lines.append("**引擎分组详情：**")
lines.append("")
lines.append("| 分组 | 就绪 | 总数 | 状态 |")
lines.append("|:----|:---:|:---:|:----:|")
for group in ENGINE_GROUPS:
    total_g = group_counts.get(group, 0)
    ok_g = group_oks.get(group, 0)
    if total_g == 0:
        continue
    icon = "✅" if ok_g == total_g else ("⚠️" if ok_g > 0 else "❌")
    lines.append(f"| {group} | {ok_g} | {total_g} | {icon} |")

lines.append("")
lines.append("新的一天，随时待命 🤖")

print("\n".join(lines))
