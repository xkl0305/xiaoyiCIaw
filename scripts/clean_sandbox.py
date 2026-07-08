#!/usr/bin/env python3
"""
clean_sandbox.py — 全系统沙箱周清理

安全清理（自动）:
  - /tmp 临时文件
  - npm-cache（workspace）
  - pip 缓存 (~/.cache/pip)
  - npm 全局缓存 (~/.npm/_cacache)
  - workspace 下所有 __pycache__

报告不删（需用户确认）:
  - 网关日志 (~/.openclaw/logs)
  - 模型路由日志 (~/.openclaw/model_router_logs)
  - 旧轨迹文件 (agents/main/sessions/*.trajectory.jsonl)
  - 旧会话文件 (agents/main/sessions/*.jsonl 非 trajectory)
  - 旧生成图片 (workspace/generated-images)
  - 旧生成视频 (workspace/generated-videos)
  - 旧报告 (workspace/reports)
  - plugins 下大缓存目录

保护目录:
  - assets/persona/outfits/（衣柜参考图）
"""
import os, shutil, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
HOME = Path(os.environ.get("HOME", "/home/sandbox"))
WORKSPACE = Path(os.environ.get("OPENCLAW_WORKSPACE", HOME / ".openclaw" / "workspace"))
NOW = datetime.now(BEIJING_TZ)
CUTOFF_TRAJECTORY = NOW.timestamp() - 7 * 86400  # 7天
CUTOFF_GENERATED = NOW.timestamp() - 3 * 86400   # 3天

auto_cleaned = []
reported = []
errors = []

_TRAJECTORY_MIN_MB = 1
_REPORT_MAX_ITEMS = 10

# ── 路径定义 ──
PATHS = {
    "tmp": Path("/tmp"),
    "npm_cache": HOME / ".openclaw" / "npm-cache",
    "pip_cache": HOME / ".cache" / "pip",
    "npm_global": HOME / ".npm" / "_cacache",
    "logs": HOME / ".openclaw" / "logs",
    "router_logs": HOME / ".openclaw" / "model_router_logs",
    "sessions": HOME / ".openclaw" / "agents" / "main" / "sessions",
    "gen_images": WORKSPACE / "generated-images",
    "gen_videos": WORKSPACE / "generated-videos",
    "reports": WORKSPACE / "reports",
    "outfits": WORKSPACE / "assets" / "persona" / "outfits",
    "plugins": WORKSPACE / "plugins",
}

# ── 安全清理（自动）──

def _safe_rmtree(p: Path, label: str):
    """安全删除整个目录"""
    if not p.exists():
        return
    size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if any(p.iterdir()) else 0
    shutil.rmtree(str(p), ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)
    size_kb = size // 1024
    auto_cleaned.append(f"✅ {label}: ~{size_kb}KB" if size_kb > 0 else f"✅ {label}: 0KB，已清空")

def clean_tmp():
    """✓ /tmp"""
    if not PATHS["tmp"].exists():
        return
    count = 0
    for f in PATHS["tmp"].iterdir():
        if f.is_dir():
            shutil.rmtree(str(f), ignore_errors=True)
        else:
            f.unlink(missing_ok=True)
        count += 1
    auto_cleaned.append(f"✅ /tmp: {count} 项")

def clean_pycache():
    """✓ workspace 下所有 __pycache__"""
    count = 0
    size = 0
    for root, dirs, _ in os.walk(str(WORKSPACE)):
        # 跳过 node_modules 和 .git
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".archive")]
        for d in dirs:
            if d == "__pycache__":
                full = os.path.join(root, d)
                try:
                    s = sum(os.path.getsize(os.path.join(full, f)) for f in os.listdir(full) if os.path.isfile(os.path.join(full, f)))
                    shutil.rmtree(full, ignore_errors=True)
                    count += 1
                    size += s
                except Exception:
                    pass
    if count > 0:
        auto_cleaned.append(f"✅ __pycache__: {count} 个目录, ~{size//1024}KB")

# ── 报告（需确认）──

def _report_dir(p: Path, label: str, days: int = 30, min_mb: float = 0):
    """报告目录下旧文件"""
    if not p.exists():
        return
    items = []
    total_size = 0
    for f in sorted(p.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.stat().st_mtime < NOW.timestamp() - days * 86400:
            sz = f.stat().st_size
            if min_mb and sz < min_mb * 1024 * 1024:
                continue
            total_size += sz
            mtime = datetime.fromtimestamp(f.stat().st_mtime, BEIJING_TZ).strftime("%m-%d")
            items.append(f"  • {f.name} ({sz//1024}KB, {mtime})")
        elif f.is_dir() and f.stat().st_mtime < NOW.timestamp() - days * 86400:
            sz = sum(ff.stat().st_size for ff in f.rglob("*") if ff.is_file()) if any(f.iterdir()) else 0
            if min_mb and sz < min_mb * 1024 * 1024:
                continue
            total_size += sz
            mtime = datetime.fromtimestamp(f.stat().st_mtime, BEIJING_TZ).strftime("%m-%d")
            items.append(f"  • {f.name}/ ({sz//1024}KB, {mtime})")
    if items:
        total_mb = total_size / 1024 / 1024
        reported.append(f"📋 **{label}**（{days}天前）— {len(items)} 项, ~{total_mb:.1f}MB")
        for it in items[:_REPORT_MAX_ITEMS]:
            reported.append(it)
        if len(items) > _REPORT_MAX_ITEMS:
            reported.append(f"  …还有 {len(items)-_REPORT_MAX_ITEMS} 项未列出")

def report_logs():
    """报告的日志"""
    _report_dir(PATHS["logs"], "网关日志", days=7)
    _report_dir(PATHS["router_logs"], "模型路由日志", days=7)

def report_trajectories():
    """报告的旧轨迹文件"""
    cutoff = CUTOFF_TRAJECTORY
    items = []
    for f in sorted(PATHS["sessions"].glob("*.trajectory.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stat().st_mtime < cutoff and f.stat().st_size > _TRAJECTORY_MIN_MB * 1024 * 1024:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, BEIJING_TZ).strftime("%m-%d")
            items.append(f"  • {f.name} ({f.stat().st_size//1024//1024}MB, {mtime})")
    if items:
        reported.append(f"📋 **旧轨迹文件**（7天前, >{_TRAJECTORY_MIN_MB}MB）— {len(items)} 项")
        for it in items[:_REPORT_MAX_ITEMS]:
            reported.append(it)
        if len(items) > _REPORT_MAX_ITEMS:
            reported.append(f"  …还有 {len(items)-_REPORT_MAX_ITEMS} 项未列出")

def report_sessions():
    """报告的旧会话文件（非 trajectory）"""
    cutoff = CUTOFF_TRAJECTORY
    items = []
    for f in sorted(PATHS["sessions"].glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if ".trajectory" in f.name:
            continue
        if f.stat().st_mtime < cutoff and f.stat().st_size > 1024 * 1024:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, BEIJING_TZ).strftime("%m-%d")
            items.append(f"  • {f.name} ({f.stat().st_size//1024//1024}MB, {mtime})")
    if items:
        reported.append(f"📋 **旧会话文件**（7天前, >1MB）— {len(items)} 项")
        for it in items[:_REPORT_MAX_ITEMS]:
            reported.append(it)
        if len(items) > _REPORT_MAX_ITEMS:
            reported.append(f"  …还有 {len(items)-_REPORT_MAX_ITEMS} 项未列出")

def report_generated():
    """报告的旧生成文件"""
    for d, label in [(PATHS["gen_images"], "生成图片"), (PATHS["gen_videos"], "生成视频")]:
        if not d.exists():
            continue
        items = []
        total_size = 0
        for f in sorted(d.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.is_file() and f.stat().st_mtime < CUTOFF_GENERATED:
                total_size += f.stat().st_size
                mtime = datetime.fromtimestamp(f.stat().st_mtime, BEIJING_TZ).strftime("%m-%d")
                items.append(f"  • {f.name} ({f.stat().st_size//1024}KB, {mtime})")
        if items:
            total_mb = total_size / 1024 / 1024
            reported.append(f"📋 **旧{label}**（3天前）— {len(items)} 项, ~{total_mb:.1f}MB")
            for it in items[:_REPORT_MAX_ITEMS]:
                reported.append(it)
            if len(items) > _REPORT_MAX_ITEMS:
                reported.append(f"  …还有 {len(items)-_REPORT_MAX_ITEMS} 项未列出")

def report_reports():
    """报告的旧报告"""
    _report_dir(PATHS["reports"], "报告文件", days=14, min_mb=0.1)

def report_plugins_cache():
    """报告的 plugins 下大缓存"""
    if not PATHS["plugins"].exists():
        return
    items = []
    for d in PATHS["plugins"].iterdir():
        if not d.is_dir():
            continue
        # 检查是否有 node_modules 或 large cache
        for sub in ["node_modules", ".cache"]:
            p = d / sub
            if p.exists():
                sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if any(p.iterdir()) else 0
                if sz > 10 * 1024 * 1024:  # >10MB
                    items.append(f"  • {d.name}/{sub} ({sz//1024//1024}MB)")
    if items:
        reported.append(f"📋 **插件缓存**（>10MB）— {len(items)} 项")
        for it in items:
            reported.append(it)

def check_outfits():
    """保护确认"""
    p = PATHS["outfits"]
    if p.exists():
        files = list(p.iterdir())
        auto_cleaned.append(f"🛡️ assets/persona/outfits/: {len(files)} 个文件已保护")

# ── 主流程 ──

def main():
    # 安全清理（直接执行）
    clean_tmp()
    _safe_rmtree(PATHS["npm_cache"], "npm-cache")
    _safe_rmtree(PATHS["pip_cache"], "pip 缓存 (~/.cache/pip)")
    _safe_rmtree(PATHS["npm_global"], "npm 全局缓存 (~/.npm/_cacache)")
    clean_pycache()

    # 保护确认
    check_outfits()

    # 报告待确认
    report_logs()
    report_trajectories()
    report_sessions()
    report_generated()
    report_reports()
    report_plugins_cache()

    # ── 输出 ──
    now_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    print(f"🧹 **沙箱周清理 | {now_str}**")
    print()
    print("**已自动清理：**")
    for item in auto_cleaned:
        print(f"  {item}")
    print()
    if reported:
        print("**待确认清理：**")
        for item in reported:
            print(f"  {item}")
        print()

    # 磁盘状态
    result = subprocess.run(["df", "-h", str(HOME)], capture_output=True, text=True)
    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 5:
            print(f"💾 磁盘: {parts[4]} used ({parts[2]}/{parts[1]})")
            break
    print()
    print(f"_沙箱周清理完成 · 需确认项请回复 y 清理_")

if __name__ == "__main__":
    main()
