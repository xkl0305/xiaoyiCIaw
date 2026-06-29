"""
Crusheart Agent OS — 无损升级迁移引擎
功能：检测旧版本（v6 及之前）遗留文件/状态/配置，无损迁移至 v7 引擎架构

迁移项：
  1. engine_state.json 状态文件迁移（旧.engine_state.json → 新格式）
  2. 旧版 background_scheduler 持久化数据迁移至 background_executor 格式
  3. 旧版目录结构清理提醒
  4. cron 任务注册修复

使用方式：
  - 在插件升级后首次 bootstrap 时自动调用 migrate()
  - 引擎初始化时检查 .crusheart_version 文件判断是否首次运行
"""

import os
import sys
import json
import shutil
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

# v7 版本标记文件
VERSION_FILE = os.path.join(WORKSPACE, ".crusheart_version")

# 旧状态文件路径 → 新状态文件路径映射
STATE_FILE_MIGRATIONS = {
    # 无需实际移动的遗留文件（仅检测），None 表示仅检测不迁移
    os.path.join(WORKSPACE, ".quality_scores.json"): None,
    os.path.join(WORKSPACE, ".skill_auto_index.json"): None,
    os.path.join(WORKSPACE, ".task_scheduler.json"): None,
}

# 旧目录 → 新目录映射
DIR_MIGRATIONS = {
    os.path.join(WORKSPACE, "core", "autonomy"): os.path.join(WORKSPACE, "core", "engines", "hooks"),
    os.path.join(WORKSPACE, "core", "infrastructure"): os.path.join(WORKSPACE, "core", "engines", "tools"),
    os.path.join(WORKSPACE, "core", "knowledge"): os.path.join(WORKSPACE, "core", "engines", "memory"),
    os.path.join(WORKSPACE, "core", "orchestration"): os.path.join(WORKSPACE, "core", "engines", "workflow"),
}

# 不再使用的旧 .py 文件（仅提示删除）
DEPRECATED_FILES = [
    "core/engines/operations/background_scheduler.py",
    "core/engines/hooks/user_digital_twin.py",
    "core/engines/quality/evolution_tracker.py",
]

# 旧插件独占锁路径
EXCLUSIVE_LOCK_SOURCE = os.path.join(WORKSPACE, ".state", ".crusheart_exclusive_active")
EXCLUSIVE_LOCK_LEGACY = os.path.join(WORKSPACE, ".crusheart_active")


logger = logging.getLogger("compat_migration")


def _detect_old_version() -> Optional[str]:
    """检测旧版本号（从 VERSION_FILE 或遗留状态推断）"""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE) as f:
                data = json.load(f)
            return data.get("version")
        except Exception:
            return None

    # 无版本文件 → 判断是否存在旧版遗留状态
    if os.path.exists(os.path.join(WORKSPACE, "core", "autonomy")):
        return "6.x"  # 旧版目录结构还在
    if os.path.exists(EXCLUSIVE_LOCK_LEGACY):
        return "6.x"

    return None  # 全新安装


def _write_version(version: str = "7.0.0"):
    """写入当前版本标记"""
    data = {
        "version": version,
        "updated_at": datetime.now(BEIJING_TZ).isoformat(),
        "migration_history": _load_migration_history(),
    }
    os.makedirs(os.path.dirname(VERSION_FILE) or ".", exist_ok=True)
    with open(VERSION_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_migration_history() -> list:
    """加载已有迁移历史"""
    if not os.path.exists(VERSION_FILE):
        return []
    try:
        with open(VERSION_FILE) as f:
            data = json.load(f)
        return data.get("migration_history", [])
    except Exception:
        return []


def _add_history(entry: dict):
    """添加迁移记录"""
    history = _load_migration_history()
    history.append(entry)
    return history


def migrate():
    """
    执行无损升级迁移。

    Returns:
        {
            "status": "ok" | "already_7" | "fresh_install" | "partial",
            "old_version": str | None,
            "migrations_done": [str, ...],
            "warnings": [str, ...],
            "errors": [str, ...],
        }
    """
    old_ver = _detect_old_version()
    migrations_done = []
    warnings = []
    errors = []

    # ── 情况1: 全新安装 ──
    if old_ver is None:
        _write_version()
        return {
            "status": "fresh_install",
            "old_version": None,
            "migrations_done": [],
            "warnings": [],
            "errors": [],
        }

    # ── 情况2: 已升级到 v7 ──
    if old_ver and old_ver.startswith("7."):
        # 确保版本文件已更新（可能来自旧 v7 变体）
        _write_version("7.0.0")
        return {
            "status": "already_7",
            "old_version": old_ver,
            "migrations_done": [],
            "warnings": [],
            "errors": [],
        }

    # ── 情况3: 从旧版升级 ──
    print(f"  🔄 Compat Migration: 检测到旧版本 {old_ver}，正在执行无损升级…")

    # 3.1 处理旧独占锁（v6 及之前可能残留的锁文件）
    for lock_path in [EXCLUSIVE_LOCK_LEGACY, EXCLUSIVE_LOCK_SOURCE]:
        if os.path.exists(lock_path):
            try:
                with open(lock_path) as f:
                    old_lock = json.load(f)
                # 仅当锁文件超过24小时视为残留，自动清理
                lock_time_str = old_lock.get("locked_at", "")
                if lock_time_str:
                    try:
                        lock_time = datetime.fromisoformat(lock_time_str)
                        age_hours = (datetime.now(BEIJING_TZ) - lock_time).total_seconds() / 3600
                        if age_hours > 24:
                            os.remove(lock_path)
                            migrations_done.append(f"清理过期独占锁: {os.path.basename(lock_path)}")
                    except ValueError:
                        pass
            except Exception:
                pass

    # 3.2 检测旧版 background_scheduler 持久化数据
    old_bg_state = os.path.join(WORKSPACE, ".background_tasks_state.json")
    new_bg_state = os.path.join(WORKSPACE, ".background_tasks.json")
    if os.path.exists(old_bg_state) and not os.path.exists(new_bg_state):
        try:
            shutil.copy2(old_bg_state, new_bg_state)
            migrations_done.append("迁移 background_scheduler 状态 → .background_tasks.json")
        except Exception as e:
            warnings.append(f"background_scheduler 状态迁移失败: {e}")

    # 3.3 检测旧版引擎状态文件格式是否需要升级
    engine_state_path = os.path.join(WORKSPACE, ".state", ".engine_state.json")
    if os.path.exists(engine_state_path):
        try:
            with open(engine_state_path) as f:
                state = json.load(f)
            # 旧版 engines.json 可能缺少 compat 等 v7 新增字段
            engines = state.get("engines", [])
            engine_names = {e.get("name") for e in engines}
            # v7 新增引擎
            v7_engines = [
                "compat_registry", "evolution_tracker", "masa_engine",
                "self_evolution_v3", "session_state", "judge_engine",
                "insights_engine", "enhancement_engine", "device_reconciler",
                "tool_gateway", "trace_timeline", "circuit_breaker",
                "failover_engine", "background_executor", "daemon_bridge",
            ]
            missing_v7 = [e for e in v7_engines if e not in engine_names]
            if missing_v7:
                # 不自动写入——等待 init_engines.py --bootstrap 重建
                warnings.append(f"引擎状态中缺少 v7 新增引擎: {', '.join(missing_v7)}（等待 init_engines.py 重建）")
        except Exception as e:
            warnings.append(f"引擎状态文件读取失败: {e}")

    # 3.4 检测旧目录结构
    old_dirs_found = []
    for old_dir in DIR_MIGRATIONS:
        if os.path.isdir(old_dir):
            old_dirs_found.append(os.path.basename(old_dir))
    if old_dirs_found:
        warnings.append(
            f"检测到旧版根目录: {', '.join(old_dirs_found)}/（内容已整合至 core/engines/ 下，"
            "如果确认无外部引用可以手动删除）"
        )

    # 3.5 检测已废弃但可能残留的文件
    deprecated_found = []
    for dep_file in DEPRECATED_FILES:
        full_path = os.path.join(WORKSPACE, dep_file)
        if os.path.exists(full_path):
            deprecated_found.append(dep_file)
    if deprecated_found:
        warnings.append(
            f"检测到已废弃的旧版文件: {', '.join(deprecated_found)}（可安全删除）"
        )

    # 3.6 检测旧版 cron 任务是否需要修复注册
    _fix_cron_registrations()

    # ── 完成 ──
    history_entry = {
        "action": f"upgrade_v7_from_{old_ver}",
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        "migrations_done": list(migrations_done),
        "warnings": list(warnings),
    }
    history = _add_history(history_entry)
    _write_version()

    status = "ok" if not errors else "partial"
    if not migrations_done and not warnings and not errors:
        status = "already_7"

    result = {
        "status": status,
        "old_version": old_ver,
        "migrations_done": migrations_done,
        "warnings": warnings,
        "errors": errors,
    }

    if migrations_done:
        print(f"  ✅ 完成 {len(migrations_done)} 项数据迁移")
    if warnings:
        for w in warnings:
            print(f"  ⚠️  {w}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")

    return result


def _fix_cron_registrations():
    """修复旧版 cron 任务注册（如果 cron 列表中缺少 v7 必备任务）"""
    try:
        import subprocess
        result = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr

        # 检查必备任务是否存在
        required = {
            "健康巡检": {"cron": "0 0 * * *", "message": "系统健康巡检"},
            "引擎初始化": {"cron": "0 5 * * *", "message": "Crusheart 引擎重初始化"},
            "每日记忆维护": {"cron": "0 23 * * *", "message": "每日记忆维护"},
        }
        found_tasks = output.lower()

        for name, cfg in required.items():
            if name not in found_tasks and cfg["cron"] not in found_tasks:
                # 不自动添加，仅记录提示
                logger.warning(f"检测到缺少定时任务: {name}（{cfg['cron']}），请手动添加")
    except Exception:
        pass


def check_upgrade_safety() -> dict:
    """
    检查升级安全性（供升级前调用）
    Returns:
        {
            "safe": True/False,
            "blocking_issues": [],
            "non_blocking_warnings": [],
            "estimated_downtime_seconds": int,
        }
    """
    issues = []
    warnings_list = []

    # 检查是否有正在运行的后台任务
    bg_task_file = os.path.join(WORKSPACE, ".background_tasks.json")
    if os.path.exists(bg_task_file):
        try:
            with open(bg_task_file) as f:
                tasks = json.load(f)
            active_tasks = [
                tid for tid, task in tasks.items()
                if isinstance(task, dict) and task.get("status") in ("running", "pending")
            ]
            if active_tasks:
                warnings_list.append(f"存在 {len(active_tasks)} 个活跃后台任务，升级后可能中断")
        except Exception:
            pass

    # 检查工作区磁盘空间
    try:
        result = __import__("subprocess", fromlist=["run"]).run(
            ["df", "-m", WORKSPACE],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[-1].split()
            if len(parts) >= 4:
                available_mb = int(parts[3])
                if available_mb < 500:
                    issues.append(f"磁盘空间不足: 仅剩 {available_mb}MB（需要 ≥500MB）")
    except Exception:
        pass

    return {
        "safe": len(issues) == 0,
        "blocking_issues": issues,
        "non_blocking_warnings": warnings_list,
        "estimated_downtime_seconds": 5 if not issues else 999,
    }


def get_migration_log() -> list:
    """获取迁移日志"""
    return _load_migration_history()


def get_current_version() -> str:
    """获取当前记录的版本号"""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE) as f:
                data = json.load(f)
            return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"


# ── 简易 CLI ──

if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    import sys as _sys

    if len(_sys.argv) > 1 and _sys.argv[1] == "migrate":
        result = migrate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif len(_sys.argv) > 1 and _sys.argv[1] == "check":
        result = check_upgrade_safety()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif len(_sys.argv) > 1 and _sys.argv[1] == "version":
        print(get_current_version())
    elif len(_sys.argv) > 1 and _sys.argv[1] == "log":
        log = get_migration_log()
        print(json.dumps(log, indent=2, ensure_ascii=False))
    else:
        print("用法:")
        print("  python3 -m core.engines.compat.compat_migration migrate   # 执行升级迁移")
        print("  python3 -m core.engines.compat.compat_migration check     # 升级前安全检查")
        print("  python3 -m core.engines.compat.compat_migration version   # 查看当前版本")
        print("  python3 -m core.engines.compat.compat_migration log       # 查看迁移历史")
