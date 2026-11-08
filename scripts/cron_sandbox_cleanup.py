#!/usr/bin/env python3
"""沙箱清理定时任务 — 自动清理安全无风险的内容，大文件列出待确认。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
HOME = os.path.expanduser("~")

def size_str(path):
    try:
        s = os.path.getsize(path)
        if s < 1024: return f"{s}B"
        if s < 1024**2: return f"{s/1024:.1f}KB"
        return f"{s/1024**2:.1f}MB"
    except: return "?"

def dir_size(path):
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try: total += os.path.getsize(fp)
                except: pass
    except: pass
    return total

def auto_clean(dry_run=False):
    """自动清理：/tmp 编译缓存 + __pycache__ + openclaw日志 + 正式文件旧备份 + /tmp验证截图 + 脚本/配置类bak + /tmp任务产物(超7天)。
    dry_run=True 时仅预览待删清单，不执行任何实际删除。"""
    freed = 0
    items = []
    if dry_run:
        prev_items, prev_freed = clean_workspace_backups(True)
        misc_items, misc_freed = clean_misc_baks(True)
        shot_items, shot_freed = clean_tmp_screenshots(True)
        task_items, task_freed = clean_task_artifacts(True)
        return prev_items + misc_items + shot_items + task_items, prev_freed + misc_freed + shot_freed + task_freed

    # 1. /tmp 编译缓存
    for p in ["/tmp/node-compile-cache", "/tmp/openclaw-compile-cache"]:
        if os.path.isdir(p):
            s = dir_size(p)
            shutil.rmtree(p, ignore_errors=True)
            freed += s
            items.append(f"🧹 {p} — 已清理 ({size_str(p) if s else '0B'}→0)")

    # 2. /tmp/openclaw 日志（保留最近2个日志文件）
    log_dir = "/tmp/openclaw"
    if os.path.isdir(log_dir):
        logs = sorted(
            [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith(".log")],
            key=os.path.getmtime
        )
        old_logs = logs[:-2] if len(logs) > 2 else []
        for f in old_logs:
            s = os.path.getsize(f)
            os.remove(f)
            freed += s
            items.append(f"🧹 {f} — 旧日志已清理 ({size_str(f)})")
    
    # 3. /tmp/logs
    if os.path.isdir("/tmp/logs"):
        s = dir_size("/tmp/logs")
        for f in os.listdir("/tmp/logs"):
            fp = os.path.join("/tmp/logs", f)
            try:
                if os.path.isfile(fp): os.remove(fp)
                elif os.path.isdir(fp): shutil.rmtree(fp, ignore_errors=True)
            except: pass
        freed += s
        items.append(f"🧹 /tmp/logs — 已清理 ({size_str('/tmp/logs') if s else '0B'}→0)")

    # 4. workspace __pycache__
    for root, dirs, _ in os.walk(WORKSPACE):
        for d in list(dirs):
            if d == "__pycache__":
                p = os.path.join(root, d)
                s = dir_size(p)
                shutil.rmtree(p, ignore_errors=True)
                freed += s
                items.append(f"🧹 {p} — __pycache__ 已清理 ({size_str(p) if s else '0B'}→0)")

    # 5. workspace 正式文件旧备份（每组保留 BACKUP_KEEP 个，其余删除）
    bak_items, bak_freed = clean_workspace_backups(dry_run)
    items.extend(bak_items)
    freed += bak_freed

    # 6. /tmp 验证截图（超过 SCREENSHOT_MAX_AGE_DAYS 天的 png）
    shot_items, shot_freed = clean_tmp_screenshots(dry_run)
    items.extend(shot_items)
    freed += shot_freed

    # 7. workspace 脚本/配置类 bak（每系列保留最新 MISC_BAK_KEEP 个）
    misc_items, misc_freed = clean_misc_baks(dry_run)
    items.extend(misc_items)
    freed += misc_freed

    # 8. /tmp 任务产物（超 TASK_ARTIFACT_MAX_AGE_DAYS 天：xiaoyi_ppt会话/调研目录/根下html）
    task_items, task_freed = clean_task_artifacts(dry_run)
    items.extend(task_items)
    freed += task_freed

    return items, freed

# 正式文件备份清理：每组保留最新 BACKUP_KEEP 个，其余淘汰
PROTECTED_BACKUP_MARKERS = [
    "AGENTS.md.bak-", "SOUL.md.bak-", "MEMORY.md.bak-",
    "USER.md.bak-", "IDENTITY.md.bak-", "TOOLS.md.bak-",
]
BACKUP_KEEP = 2

def clean_workspace_backups(dry_run=False):
    """清理正式文件旧备份：每组保留 BACKUP_KEEP 个。dry_run=True 只列出待删，不实删。"""
    freed = 0
    items = []
    removed = 0
    try:
        entries = os.listdir(WORKSPACE)
    except Exception:
        return items, freed
    for marker in PROTECTED_BACKUP_MARKERS:
        files = sorted(
            [os.path.join(WORKSPACE, f) for f in entries if f.startswith(marker)],
            key=os.path.getmtime,
        )
        if len(files) <= BACKUP_KEEP:
            continue
        for f in files[:-BACKUP_KEEP]:
            try:
                s = os.path.getsize(f)
                if not dry_run:
                    os.remove(f)
                freed += s
                removed += 1
                items.append(f"🧹 {os.path.basename(f)} — {'待删' if dry_run else '已清'} ({size_str(f)})")
            except Exception:
                continue
    if removed:
        tag = "待删" if dry_run else "已清理"
        items.insert(0, f"🧹 workspace正式文件旧备份 — {tag} {removed}个/释放 {freed/1024:.1f}KB (每组保留{BACKUP_KEEP}个)")
    return items, freed


# /tmp 验证截图：超过该天数的 png 自动淘汰
SCREENSHOT_MAX_AGE_DAYS = 2

def clean_tmp_screenshots(dry_run=False):
    """清理 /tmp 下超过 SCREENSHOT_MAX_AGE_DAYS 天的 png 验证截图。"""
    import time
    freed = 0
    items = []
    removed = 0
    cutoff = time.time() - SCREENSHOT_MAX_AGE_DAYS * 86400
    if not os.path.isdir("/tmp"):
        return items, freed
    for f in os.listdir("/tmp"):
        if not f.endswith(".png"):
            continue
        fp = os.path.join("/tmp", f)
        try:
            if not os.path.isfile(fp) or os.path.getmtime(fp) > cutoff:
                continue
            s = os.path.getsize(fp)
            if not dry_run:
                os.remove(fp)
            freed += s
            removed += 1
            items.append(f"🧹 /tmp/{f} — {'待删' if dry_run else '已清'} ({size_str(fp)})")
        except Exception:
            continue
    if removed:
        tag = "待删" if dry_run else "已清理"
        items.insert(0, f"🧹 /tmp验证截图 — {tag} {removed}个/释放 {freed/1024:.1f}KB (超{SCREENSHOT_MAX_AGE_DAYS}天)")
    return items, freed


# /tmp 任务产物：超过该天数未动的自动淘汰（2026-11-06 俞哥确认纳入沙箱清理）
TASK_ARTIFACT_MAX_AGE_DAYS = 7
# 已知任务产物目录（PPT会话/调研快照等）
TASK_ARTIFACT_DIRS = ["/tmp/xiaoyi_ppt", "/tmp/mao", "/tmp/ppt_check", "/tmp/ppt_fix", "/tmp/ppt_fix2", "/tmp/ppt_check3", "/tmp/ppt_check_png", "/tmp/vec_redraw", "/tmp/faw_q3", "/tmp/q3_report", "/tmp/qqbot_audit", "/tmp/ai_trend", "/tmp/wsp_deps"]

def clean_task_artifacts(dry_run=False):
    """清理 /tmp 任务产物：xiaoyi_ppt 会话目录、调研目录、/tmp 根下超龄 html、/tmp 下超龄 Office 成品与媒体文件、workspace/tmp 超龄文件。
    按 mtime 年龄 > TASK_ARTIFACT_MAX_AGE_DAYS 天才清；dry_run=True 只列出待删，不实删。"""
    import time
    import glob as _glob
    freed = 0
    items = []
    removed = 0
    cutoff = time.time() - TASK_ARTIFACT_MAX_AGE_DAYS * 86400

    def _expired(p):
        try:
            return os.path.getmtime(p) < cutoff
        except Exception:
            return False

    # 1) 任务产物目录下的子项（会话目录/调研文件），超龄整删
    for d in TASK_ARTIFACT_DIRS:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            fp = os.path.join(d, name)
            if not _expired(fp):
                continue
            try:
                s = dir_size(fp) if os.path.isdir(fp) else (os.path.getsize(fp) if os.path.isfile(fp) else 0)
                if not dry_run:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                    elif os.path.isfile(fp):
                        os.remove(fp)
                freed += s
                removed += 1
                items.append(f"🧹 {fp} — {'待删' if dry_run else '已清'} ({size_str(fp) if s else '0B'}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天)")
            except Exception:
                continue

    # 2) /tmp 根下超龄 html（调研/搜索缓存）
    if os.path.isdir("/tmp"):
        for f in os.listdir("/tmp"):
            if not f.endswith(".html"):
                continue
            fp = os.path.join("/tmp", f)
            try:
                if not os.path.isfile(fp) or not _expired(fp):
                    continue
                s = os.path.getsize(fp)
                if not dry_run:
                    os.remove(fp)
                freed += s
                removed += 1
                items.append(f"🧹 /tmp/{f} — {'待删' if dry_run else '已清'} ({size_str(fp)}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天)")
            except Exception:
                continue

    # 3) /tmp 下超龄 Office 成品与媒体文件（不限目录；TASK_ARTIFACT_DIRS 下的走目录级规则避免双计）
    artifact_exts = (".xlsx", ".docx", ".pptx", ".jpg", ".jpeg", ".png", ".webp", ".gif",
                     ".mp4", ".m4a", ".mp3", ".wav", ".mov",
                     ".pdf", ".tgz", ".zip", ".txt")
    # 运行时目录保护：仅真正运行中的环境目录，删了会挂
    PROTECTED_DIRS = ("/tmp/openclaw", "/tmp/systemd-")
    for root, dirs, fs in os.walk("/tmp"):
        # 跳过运行时/依赖保护目录
        if any(root == p or root.startswith(p.rstrip('/') + os.sep) or root.startswith(p) for p in PROTECTED_DIRS):
            dirs[:] = []
            continue
        # 跳过已由目录级规则覆盖的任务产物目录
        if any(root == d or root.startswith(d + os.sep) for d in TASK_ARTIFACT_DIRS):
            dirs[:] = []
            continue
        # 跳过已由编译缓存规则覆盖的目录（避免文件级重复计）
        if any(root == cp or root.startswith(cp + os.sep) for cp in _glob.glob("/tmp/pip-*") + _glob.glob("/tmp/.org.chromium.Chromium.*") + ["/tmp/jiti"]):
            dirs[:] = []
            continue
        for f in fs:
            if not f.lower().endswith(artifact_exts):
                continue
            fp = os.path.join(root, f)
            try:
                if not os.path.isfile(fp) or not _expired(fp):
                    continue
                s = os.path.getsize(fp)
                if not dry_run:
                    os.remove(fp)
                freed += s
                removed += 1
                items.append(f"🧹 {fp} — {'待删' if dry_run else '已清'} ({size_str(fp)}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天Office/媒体成品)")
            except Exception:
                continue

    # 5) 编译/构建缓存清理：pip-*/jiti/.org.chromium.*/v8-compile-cache/tsx-*/esbuild-*/playwright-*/puppeteer-*/npm-*（超龄整删）
    cache_patterns = ["/tmp/pip-*", "/tmp/jiti", "/tmp/.org.chromium.Chromium.*",
                      "/tmp/v8-compile-cache*", "/tmp/tsx-*", "/tmp/esbuild-*",
                      "/tmp/playwright-*", "/tmp/puppeteer-*", "/tmp/npm-*"]
    for pat in cache_patterns:
        for fp in _glob.glob(pat):
            if not _expired(fp):
                continue
            try:
                sz = dir_size(fp) if os.path.isdir(fp) else os.path.getsize(fp)
                if not dry_run:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                    else:
                        os.remove(fp)
                freed += sz
                removed += 1
                items.append(f"🧹 {fp} — {'待删' if dry_run else '已清'} ({size_str(fp) if sz else '0B'}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天编译缓存)")
            except Exception:
                continue

    # 6) /tmp 根下超龄日志文件（*.log）
    if os.path.isdir("/tmp"):
        for f in os.listdir("/tmp"):
            if not f.endswith(".log"):
                continue
            fp = os.path.join("/tmp", f)
            try:
                if not os.path.isfile(fp) or not _expired(fp):
                    continue
                sz = os.path.getsize(fp)
                if not dry_run:
                    os.remove(fp)
                freed += sz
                removed += 1
                items.append(f"🧹 /tmp/{f} — {'待删' if dry_run else '已清'} ({size_str(fp)}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天日志)")
            except Exception:
                continue

    # 7) /tmp 根下超龄任务脚本与结果文件（.json/.py/.sh/.mjs，仅根目录不递归）+ 无扩展名测试文件名单
    root_script_exts = (".json", ".py", ".sh", ".mjs")
    misc_test_names = ("rci_ensure_marker", "rci_inject_marker", "4000", "5000", "wtest")
    if os.path.isdir("/tmp"):
        for f in os.listdir("/tmp"):
            fp = os.path.join("/tmp", f)
            is_target = (f.lower().endswith(root_script_exts) or f in misc_test_names)
            if not is_target:
                continue
            try:
                if not os.path.isfile(fp) or not _expired(fp):
                    continue
                sz = os.path.getsize(fp)
                if not dry_run:
                    os.remove(fp)
                freed += sz
                removed += 1
                items.append(f"🧹 /tmp/{f} — {'待删' if dry_run else '已清'} ({size_str(fp)}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天根目录脚本/结果)")
            except Exception:
                continue

    # 4) workspace/tmp/ 下超龄文件（任务脚本产物，如 .bas VBA 导出）
    ws_tmp = os.path.join(WORKSPACE, "tmp")
    if os.path.isdir(ws_tmp):
        for name in os.listdir(ws_tmp):
            fp = os.path.join(ws_tmp, name)
            if not _expired(fp):
                continue
            try:
                s = dir_size(fp) if os.path.isdir(fp) else (os.path.getsize(fp) if os.path.isfile(fp) else 0)
                if not dry_run:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                    elif os.path.isfile(fp):
                        os.remove(fp)
                freed += s
                removed += 1
                items.append(f"🧹 {fp} — {'待删' if dry_run else '已清'} ({size_str(fp) if s else '0B'}, 超{TASK_ARTIFACT_MAX_AGE_DAYS}天workspace/tmp)")
            except Exception:
                continue

    if removed:
        tag = "待删" if dry_run else "已清理"
        items.insert(0, f"🧹 /tmp任务产物 — {tag} {removed}项/释放 {freed/1024:.1f}KB (超{TASK_ARTIFACT_MAX_AGE_DAYS}天: xiaoyi_ppt会话/调研目录/根下html/Office与媒体成品/workspace-tmp)")
    return items, freed


# 脚本/配置类 bak：每系列保留最新 MISC_BAK_KEEP 个
MISC_BAK_KEEP = 2

def clean_misc_baks(dry_run=False):
    """清理 workspace 内脚本/配置类 .bak 备份（六大 md 除外，由 clean_workspace_backups 处理）。
    按原文件系列分组，每组保留最新 MISC_BAK_KEEP 个，其余淘汰。"""
    import re as _re
    from collections import defaultdict
    freed = 0
    items = []
    removed = 0
    groups = defaultdict(list)
    for root, dirs, fs in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for f in fs:
            m = _re.match(r"^(.+?)\.bak(?:[-._].*)?$", f)
            if not m:
                continue
            base = f
            # 六大 md 备份已由 clean_workspace_backups 处理，跳过避免双计
            if any(base.startswith(mk) for mk in PROTECTED_BACKUP_MARKERS):
                continue
            p = os.path.join(root, f)
            orig = os.path.join(root, m.group(1))
            try:
                groups[orig].append((os.path.getmtime(p), p))
            except Exception:
                continue
    for orig, lst in groups.items():
        if len(lst) <= MISC_BAK_KEEP:
            continue
        lst.sort(reverse=True)  # 最新在前
        for _, p in lst[MISC_BAK_KEEP:]:
            try:
                s = os.path.getsize(p)
                if not dry_run:
                    os.remove(p)
                freed += s
                removed += 1
                rel = os.path.relpath(p, WORKSPACE)
                items.append(f"🧹 {rel} — {'待删' if dry_run else '已清'} ({size_str(p)})")
            except Exception:
                continue
    if removed:
        tag = "待删" if dry_run else "已清理"
        items.insert(0, f"🧹 脚本/配置类bak — {tag} {removed}个/释放 {freed/1024:.1f}KB (每系列保留{MISC_BAK_KEEP}个)")
    return items, freed


def list_large_pending():
    """列出需要用户确认的大文件"""
    pending = []
    
    # generated-images
    img_dir = os.path.join(WORKSPACE, "generated-images")
    if os.path.isdir(img_dir):
        total = dir_size(img_dir)
        files = sorted(os.listdir(img_dir))
        pending.append({
            "path": "generated-images/",
            "size": size_str(img_dir) if total else "0B",
            "files": len(files),
            "note": "AI出图缓存"
        })

    # assets
    assets_dir = os.path.join(WORKSPACE, "assets")
    if os.path.isdir(assets_dir):
        total = dir_size(assets_dir)
        pending.append({
            "path": "assets/",
            "size": size_str(assets_dir) if total else "0B",
            "files": "?",
            "note": "资产文件"
        })

    # openclaw.json.bak
    bak_files = sorted([f for f in os.listdir(HOME) if f.startswith("openclaw.json.bak")])
    if bak_files:
        total = sum(os.path.getsize(os.path.join(HOME, f)) for f in bak_files)
        pending.append({
            "path": f"~/openclaw.json.bak.* ({len(bak_files)}个)",
            "size": size_str(bak_files[0]) * len(bak_files) if False else f"{total/1024:.1f}KB",
            "files": len(bak_files),
            "note": "配置备份"
        })

    # input_ref.jpg
    ref_path = os.path.join(WORKSPACE, "input_ref.jpg")
    if os.path.isfile(ref_path):
        pending.append({
            "path": "input_ref.jpg",
            "size": size_str(ref_path),
            "files": 1,
            "note": "参考输入图"
        })

    return pending

def report(dry_run=False):
    print("=" * 50)
    head = "❄️ 沙箱清理报告 (dry-run 预览)" if dry_run else "❄️ 沙箱清理报告"
    print(head)
    print(f"⏱ {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    cleaned, freed = auto_clean(dry_run)
    
    if cleaned:
        print(f"\n✅ 自动清理完成 — 释放 {freed/1024:.1f}KB")
        print()
        print(f"| {'清理项':<50} | {'状态':<20} |")
        print(f"|{'-'*52}|{'-'*22}|")
        for item in cleaned:
            # 提取路径和操作描述
            parts = item.split(" — ")
            if len(parts) == 2:
                path_part = parts[0].replace("🧹 ", "")
                desc = parts[1]
                print(f"| {path_part:<50} | {desc:<20} |")
    else:
        print("\n✅ 无需清理")
    
    pending = list_large_pending()
    if pending:
        print(f"\n📋 待确认大文件 ({len(pending)}项)：")
        print()
        print(f"| {'目录/文件':<45} | {'大小':<10} | {'文件数':<8} | {'说明':<20} |")
        print(f"|{'-'*47}|{'-'*12}|{'-'*10}|{'-'*22}|")
        for p in pending:
            print(f"| {p['path']:<45} | {p['size']:<10} | {str(p['files']):<8} | {p['note']:<20} |")
        print()
        print("💡 如需清理请告知，我会先询问确认")
    
    # 磁盘使用 — 同时显示两个分区
    def _disk_info(mount):
        d = shutil.disk_usage(mount)
        pct = d.used / d.total * 100
        st = "✅ 充裕" if pct < 50 else ("⚠️ 紧张" if pct < 80 else "🚨 告警")
        return d, pct, st

    print(f"\n💾 磁盘使用：")
    print(f"| {'分区':<20} | {'总量':<10} | {'已用':<10} | {'剩余':<10} | {'使用率':<8} | {'状态':<10} |")
    print(f"|{'-'*22}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*10}|{'-'*12}|")
    for mnt, label in [("/", "系统根 (overlay)"), ("/home/sandbox", "工作数据盘")]:
        try:
            d, pct, st = _disk_info(mnt)
            print(f"| {label:<20} | {d.total/1024**3:<8.1f}GB  | {d.used/1024**3:<8.1f}GB  | {(d.total-d.used)/1024**3:<8.1f}GB  | {pct:<6.1f}% | {st:<10} |")
        except:
            pass
    
    print("=" * 50)

if __name__ == "__main__":
    report(dry_run="--dry-run" in sys.argv)
