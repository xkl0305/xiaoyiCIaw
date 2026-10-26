#!/usr/bin/env python3
"""
skill_sync_heal.py — 技能目录 git 对账自愈 v1.0 (2026-10-25)

背景: 2026-10-25 02:15 沙箱环境重建, init 恢复流程只带回恢复源清单内的技能,
git 仓库跟踪的 7 个技能目录(xiaoyi-docx/xiaoyi-pdf/excel-analysis/
xiaoyi-file-upload/webapp-testing/openclaw-skills-agent-builder-1.0.3/
calcom-cal.com-web-design-guidelines-1.0.2)工作区丢失。

机制: 以 git HEAD 为技能唯一准绳 —
  - git 跟踪、工作区缺失(整目录或单文件 D 状态) → 自动 git restore 补回
  - 工作区有、git 未跟踪 → 仅报告(未提交新技能), 不自动 add
  - 想正式删除某技能 → 必须 git rm + commit, 否则本脚本会拉回
边界: 只处理 skills/ 目录, 其他路径的异常状态不碰。
挂载: scripts/cron_daily_maint.py 每日 05:00 调用; 也可手动运行。

参数:
  --quiet  安静模式(供 cron 场景): 技能目录一致且未发生自愈时完全静默
           (仅写日志), 避免每日维护报告重复刷"✅ 一致"行; 只有真实自愈/
           仍缺失/git 失败等异常才输出。不带该参数时行为不变(手动诊断用)。
"""
import os
import subprocess
import sys
import datetime

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
SKILLS_DIR = os.path.join(WORKSPACE, "skills")
LOG_FILE = os.path.join(WORKSPACE, "logs", "skill_sync_heal.log")


def run_git(args):
    r = subprocess.run(["git", "-C", WORKSPACE] + args, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def git_tracked_skill_dirs():
    """git HEAD 跟踪的顶层技能目录(去掉 skills/ 前缀)"""
    code, out, _ = run_git(["ls-tree", "-d", "--name-only", "HEAD", "skills/"])
    if code != 0:
        return None
    return {line[len("skills/"):] for line in out.split("\n") if line.startswith("skills/")}


def workspace_skill_dirs():
    """工作区实际存在的顶层技能目录"""
    result = set()
    for name in os.listdir(SKILLS_DIR):
        full = os.path.join(SKILLS_DIR, name)
        if os.path.isdir(full) and not name.startswith(".") and name != "__pycache__":
            result.add(name)
    return result


def deleted_paths_in_skills():
    """git status 中 skills/ 下处于删除(D)状态的文件路径"""
    code, out, _ = run_git(["status", "--porcelain", "--", "skills/"])
    if code != 0:
        return []
    deleted = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        # 兼容不同 git 版本的 porcelain 格式("D path" / " D path" / " D  path"):
        # 按首个空白切分, 状态段含 D 即视为删除; rename(R) 天然不含 D 会被跳过
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[1].strip().strip('"')
        if "D" in status and path and "->" not in path:
            deleted.append(path)
    return deleted


def log(msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    quiet = "--quiet" in argv

    tracked = git_tracked_skill_dirs()
    if tracked is None:
        print("[skill-sync-heal] ❌ git ls-tree 失败, 跳过自愈")
        log("git ls-tree failed, skipped")
        return 1

    workspace = workspace_skill_dirs()
    missing_dirs = sorted(tracked - workspace)
    untracked_dirs = sorted(workspace - tracked)
    deleted_files = deleted_paths_in_skills()

    restored = []
    # 1) 整目录缺失 → restore 目录
    if missing_dirs:
        targets = [f"skills/{d}" for d in missing_dirs]
        code, _, err = run_git(["restore", "--source=HEAD", "--worktree", "--"] + targets)
        if code == 0:
            restored.extend(missing_dirs)
            log(f"restored missing dirs: {', '.join(missing_dirs)}")
        else:
            print(f"[skill-sync-heal] ❌ 目录恢复失败: {err}")
            log(f"restore dirs FAILED: {err}")

    # 2) 目录在但部分文件 D 状态 → restore 文件
    if deleted_files:
        code, _, err = run_git(["restore", "--source=HEAD", "--worktree", "--"] + deleted_files)
        if code == 0:
            restored.extend(deleted_files)
            log(f"restored deleted files: {len(deleted_files)} files")
        else:
            print(f"[skill-sync-heal] ❌ 文件恢复失败: {err}")
            log(f"restore files FAILED: {err}")

    # 3) 复核
    final_tracked = git_tracked_skill_dirs() or set()
    final_workspace = workspace_skill_dirs()
    still_missing = sorted(final_tracked - final_workspace)
    ok = not still_missing

    n_t, n_w = len(final_tracked), len(final_workspace)
    # quiet(cron)模式: 一致且未发生自愈时完全静默, 只写日志, 避免重复刷行。
    if restored:
        print(f"[skill-sync-heal] 🔧 已自动恢复 {len(restored)} 项: {', '.join(restored[:10])}"
              + (" ..." if len(restored) > 10 else ""))
    if untracked_dirs and not quiet:
        print(f"[skill-sync-heal] ℹ️ 未提交新技能 {len(untracked_dirs)} 个(仅提示, 不自动add): "
              f"{', '.join(untracked_dirs[:10])}" + (" ..." if len(untracked_dirs) > 10 else ""))
    if ok:
        if not quiet:
            print(f"[skill-sync-heal] ✅ git跟踪 {n_t} | 工作区 {n_w} | 技能目录一致")
        log(f"consistent: tracked={n_t} workspace={n_w}")
    else:
        print(f"[skill-sync-heal] ⚠️ 仍有缺失 {len(still_missing)} 个: {', '.join(still_missing)}")
        log(f"STILL MISSING: {', '.join(still_missing)}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
