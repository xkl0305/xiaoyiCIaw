#!/usr/bin/env python3
"""沙箱清理定时任务 — 自动清理安全无风险的内容，大文件列出待确认。"""

import os
import shutil
import subprocess
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

def auto_clean():
    """自动清理：/tmp 编译缓存 + __pycache__ + openclaw日志"""
    freed = 0
    items = []

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

def report():
    print("=" * 50)
    print("🦞 沙箱清理报告")
    print(f"⏱ {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    cleaned, freed = auto_clean()
    
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
    
    # 磁盘使用
    disk = shutil.disk_usage("/")
    used_pct = disk.used / disk.total * 100
    free_mb = (disk.total - disk.used) / 1024**2
    total_mb = disk.total / 1024**2
    status = "✅ 充裕" if used_pct < 50 else ("⚠️ 紧张" if used_pct < 80 else "🚨 告警")
    print(f"\n💾 磁盘使用：")
    print(f"| {'总量':<12} | {'已用':<12} | {'剩余':<12} | {'使用率':<8} | {'状态':<10} |")
    print(f"|{'-'*14}|{'-'*14}|{'-'*14}|{'-'*10}|{'-'*12}|")
    print(f"| {total_mb:<10.0f}MB | {disk.used/1024**2:<10.0f}MB | {free_mb:<10.0f}MB | {used_pct:<6.1f}% | {status:<10} |")
    
    print("=" * 50)

if __name__ == "__main__":
    report()
