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
    """自动清理：/tmp 编译缓存 + __pycache__ + openclaw日志 + 正式文件旧备份。
    dry_run=True 时仅预览正式文件旧备份的待删清单，不执行任何实际删除。"""
    freed = 0
    items = []
    if dry_run:
        return clean_workspace_backups(True)

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
    head = "🦞 沙箱清理报告 (dry-run 预览)" if dry_run else "🦞 沙箱清理报告"
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
