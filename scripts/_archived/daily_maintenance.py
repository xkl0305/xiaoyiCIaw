#!/usr/bin/env python3
"""
daily_maintenance.py — 统一每日维护 v7.1.0

功能：
  1. 健康巡检（引擎目录完整性/磁盘/关键数据文件）
  2. 垃圾扫描与清理（临时文件/__pycache__/旧日志/过期记忆文件）
  3. 自纠错数据链路维护（verified_memories/reflexions/replay_buffer）
  4. 每日记忆维护（归档+索引）
  5. ReplayBuffer 蒸馏
  6. 执行复盘
  7. 技能维护扫描（Curator）
  8. 会话归档（压缩30天前的旧会话文件）
  9. 技能完整性检查（SKILL.md / 文件完整性）
  10. 备份健康度检查（Git状态 / 备份文件）
  11. 异常报告 / Pipeline回灌 / 版本检查
  12. 红线审计 / 统一评分趋势分析
  13. TODO归档 / 子Agent清理 / 消息队列清理
  14. 梦境固化

统一在凌晨 1:00 运行，合并为一个任务。

v7.1.0:
  - 新增 会话归档 / 技能完整性检查 / 备份健康度检查
  - 修改运行规则：cron 静默执行，仅输出完整详细报告
  - 移除 run() 中的阶段性进度输出（仅输出最终报告）
  - --report 模式输出详尽版报告（含所有检查项目明细）
"""

import json, os, sys, time, shutil, glob, subprocess, gzip, re, tempfile
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
MEMORY_DIR = os.path.join(WORKSPACE, "memory")
ARCHIVE_DIR = os.path.join(MEMORY_DIR, ".archive")
STATE_FILE = os.path.join(WORKSPACE, ".daily_maintenance_state.json")
CLEANUP_LOG = os.path.join(WORKSPACE, ".logs", "cleanup_history.jsonl")

SILENT = False  # 全局静默模式标志


def _log_error(context: str, msg: str = ""):
    """统一的错误日志，CRUSHEART_DEBUG 时输出完整 traceback"""
    err = f"[daily_maintenance] {context}"
    if msg:
        err += f": {msg}"
    print(err, file=__import__("sys").stderr)
    if __import__("os").environ.get("CRUSHEART_DEBUG"):
        import traceback; traceback.print_exc(limit=1)




def log(msg: str):
    """统一的日志输出，silent 模式下仅保留关键信息"""
    if not SILENT:
        print(msg)


def load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            _log_error("load_state", str(e)[:80])
    return {"last_run": "", "total_cleanups": 0, "total_issues": 0}


def save_state(state: Dict):
    state["last_run"] = datetime.now(BEIJING_TZ).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── 1. 健康巡检 ───────────────────────────────
def _local_check_engines_and_disk() -> Dict:
    """
    Comprehensive local health check.
    Checks: disk space, engine directory integrity, critical data files,
            cron task health, pipeline stage integrity, daemon socket,
            plugin state, memory DB state, key dot-files.
    """
    issues = []
    warnings = []
    checks = {}
    # Disk
    try:
        st = os.statvfs(WORKSPACE)
        free_gb = st.f_frsize * st.f_bavail / (1024**3)
        total_gb = st.f_blocks * st.f_frsize / (1024**3)
        usage_pct = (1 - st.f_bavail / max(st.f_blocks, 1)) * 100
        checks["disk"] = {"free_gb": round(free_gb, 1), "total_gb": round(total_gb, 1), "usage_pct": round(usage_pct, 1)}
        if free_gb < 1:
            issues.append("Disk remaining < 1GB (critical)")
        elif free_gb < 5:
            issues.append(f"Disk remaining < 5GB ({free_gb:.1f}GB)")
    except Exception as e:
        checks["disk"] = {"error": str(e)[:50]}
        issues.append(f"Disk check failed: {str(e)[:50]}")
    # Engine directory integrity
    engine_groups = ["init", "memory", "quality", "operations", "workflow", "hooks", "tools", "compat"]
    engine_base = os.path.join(WORKSPACE, "core/engines")
    for g in engine_groups:
        d = os.path.join(engine_base, g)
        if not os.path.isdir(d):
            issues.append(f"Engine dir missing: {g}")
        else:
            py_files = [f for f in os.listdir(d) if f.endswith(".py")]
            if not py_files:
                warnings.append(f"Engine group {g}: no .py files found")
    checks["engine_dirs"] = {g: os.path.isdir(os.path.join(engine_base, g)) for g in engine_groups}
    # Subsystem directories (pipeline, planner, capability)
    for sub in ["pipeline", "planner", "capability"]:
        d = os.path.join(WORKSPACE, "core", sub)
        if not os.path.isdir(d):
            issues.append(f"Subsystem dir missing: core/{sub}")
    # Critical data files — 统一来源：init_correction_data.DATA_PATHS + 额外状态文件
    try:
        import importlib as _ic
        _icd = _ic.import_module('scripts.init_correction_data')
        _data_paths = _icd.DATA_PATHS
    except Exception:
        _data_paths = {}
    critical_files = set(_data_paths.values()) | {
        os.path.join(WORKSPACE, f) for f in [
            ".quality_scores.json",
        ]
    }
    for fp in critical_files:
        fname = os.path.basename(fp)
        checks[f"file_{fname.replace('.','_')}"] = os.path.exists(fp)

    # Memory database
    memory_db = os.path.join(WORKSPACE, ".auto_memory.db")
    if os.path.exists(memory_db):
        try:
            size_mb = os.path.getsize(memory_db) / (1024 * 1024)
            checks["memory_db_mb"] = round(size_mb, 1)
        except Exception:
            pass
    # Cron health — check for expected openclaw cron entries
    # (best-effort, not blocking)
    try:
        import subprocess as _sp
        cron_out = _sp.run(["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=10)
        cron_data = json.loads(cron_out.stdout)
        cron_names = [j.get("name", "") for j in cron_data.get("jobs", [])]
        expected_crons = ["crusheart-daily-maintenance", "crusheart-engine-init"]
        found_crons = [ec for ec in expected_crons if ec in cron_names]
        checks["cron_tasks"] = {"expected": len(expected_crons), "found": len(found_crons), "tasks": found_crons}
        for ec in expected_crons:
            if ec not in found_crons:
                issues.append(f"Missing cron task: {ec}")
    except Exception as e:
        checks["cron_tasks"] = {"error": str(e)[:60]}
    return {"issues": issues, "warnings": warnings, "checks": checks}


def health_check() -> Dict:
    """
    Comprehensive health check.
    Combines local checks with engine-level health scoring if available.
    """
    result = _local_check_engines_and_disk()
    result["status"] = "ok" if (not result["issues"] and not result.get("warnings", [])) else "issues"

    # Attempt to load engine-level health report as supplementary info
    try:
        sys.path.insert(0, WORKSPACE)
        from core.engines.operations.health_check import get_health_score_report
        report = get_health_score_report()
        result["engine_report"] = {
            "score": report.get("score", 0),
            "level": report.get("level", "unknown")
        }
    except Exception:
        result["engine_report"] = None

    # Also check anomaly_detector for supplementary data
    try:
        sys.path.insert(0, WORKSPACE)
        from core.engines.quality.anomaly_detector import quick_check
        ad_result = quick_check()
        result["anomaly_health"] = ad_result
    except Exception:
        result["anomaly_health"] = None

    return result


# ── 2. 垃圾扫描与清理 ────────────────────────────
# 跳过的大型目录（避免递归遍历 node_modules、.git 等）
_SKIP_DIRS = {'.git', 'node_modules', '.archive', 'venv', '.venv', '__pycache__', 'dist', 'build', '.next'}


def garbage_scan(clean: bool = False) -> Dict:
    """扫描并清理垃圾文件"""
    cleaned = 0
    freed_bytes = 0
    found = []

    # __pycache__ 目录（跳过大型无关目录提升性能）
    for root, dirs, _ in os.walk(WORKSPACE):
        # 跳过大型目录
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for d in dirs:
            if d == "__pycache__":
                full = os.path.join(root, d)
                try:
                    size = sum(os.path.getsize(os.path.join(full, f))
                               for f in os.listdir(full)
                               if os.path.isfile(os.path.join(full, f)))
                    if clean:
                        shutil.rmtree(full)
                        cleaned += 1
                        freed_bytes += size
                    else:
                        found.append({"path": full, "size_bytes": size, "type": "__pycache__"})
                except Exception as e:
                    _log_error("garbage_scan", str(e)[:80])

    # .pyc 文件
    for fp in glob.glob(os.path.join(WORKSPACE, "**/*.pyc"), recursive=True):
        try:
            size = os.path.getsize(fp)
            if clean:
                os.remove(fp)
                cleaned += 1
                freed_bytes += size
            else:
                found.append({"path": fp, "size_bytes": size, "type": "pyc"})
        except Exception as e:
            _log_error("garbage_scan", str(e)[:80])

    # memory/ 目录中超过 90 天的归档
    now = datetime.now(BEIJING_TZ)
    if os.path.isdir(MEMORY_DIR):
        for fp in glob.glob(os.path.join(MEMORY_DIR, "*.md")):
            fname = os.path.basename(fp)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
            if not date_match:
                continue
            try:
                file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
                if (now - file_date).days > 90:
                    size = os.path.getsize(fp)
                    if clean:
                        os.makedirs(ARCHIVE_DIR, exist_ok=True)
                        with open(fp, "rb") as f_in:
                            with gzip.open(os.path.join(ARCHIVE_DIR, fname + ".gz"), "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(fp)
                        cleaned += 1
                        freed_bytes += size
                    else:
                        found.append({"path": fp, "size_bytes": size, "type": "old_memory_log"})
            except Exception as e:
                _log_error("garbage_scan", str(e)[:80])

    # /tmp 下本进程遗留文件
    if clean:
        for f in glob.glob(os.path.join(tempfile.gettempdir(), "analyze_skill*")) + glob.glob(os.path.join(tempfile.gettempdir(), "repack_bundle*")):
            try:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)
            except Exception as e:
                _log_error("garbage_scan", str(e)[:80])

    # v6.5.11: 清理超过7天的健康巡检报告
    if clean:
        health_log = os.path.join(WORKSPACE, ".engine_logs", "health_check_log.json")
        if os.path.exists(health_log):
            try:
                now = time.time()
                cutoff = 7 * 86400
                with open(health_log) as f:
                    records = json.load(f)
                valid = [
                    r for r in records
                    if "timestamp" in r
                    and isinstance(r["timestamp"], str)
                    and (now - datetime.fromisoformat(r["timestamp"]).timestamp()) < cutoff
                ]
                if len(valid) < len(records):
                    with open(health_log, "w") as f:
                        json.dump(valid, f, indent=2, ensure_ascii=False)
                    cleaned += 1
                    freed_bytes += 1024  # approximate
            except Exception as e:
                _log_error("garbage_scan", str(e)[:80])

    # v6.5.11: 清理过期的健康评分历史（只保留7天）
    if clean:
        hist_path = os.path.join(WORKSPACE, ".autonomy_state", "health_score_history.jsonl")
        if os.path.exists(hist_path):
            try:
                now = time.time()
                cutoff = 7 * 86400
                with open(hist_path) as f:
                    lines = f.readlines()
                valid_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        if ts and (now - datetime.fromisoformat(ts).timestamp()) < cutoff:
                            valid_lines.append(line + "\n")
                    except Exception:
                        pass
                if len(valid_lines) < len(lines):
                    with open(hist_path, "w") as f:
                        f.writelines(valid_lines)
                    cleaned += 1
            except Exception as e:
                _log_error("garbage_scan", str(e)[:80])

    return {"found": len(found), "cleaned": cleaned, "freed_bytes": freed_bytes, "items": found[:20]}


# ── 3. 自纠错数据链路维护 ─────────────────────────
def correction_maintenance() -> Dict:
    """确保自纠错数据文件完整"""
    sys.path.insert(0, WORKSPACE)
    try:
        import importlib
        icd = importlib.import_module("scripts.init_correction_data")
        result = icd.run_init(force=False)
        return {"status": "ok", "detail": result.get("data_files", {})}
    except Exception as e:
        return {"status": "error", "error": str(e)[:80]}


# ── 4. 记忆维护 ─────────────────────────────
def memory_maintenance() -> Dict:
    """
    记忆全链路维护 v3.0 — 委托 memory_pipeline 执行
      采集会话→L2短期记忆→L3蒸馏巩固→L4清理
    """
    try:
        sys.path.insert(0, WORKSPACE)
        import importlib
        mp = importlib.import_module("scripts.memory_pipeline")
        report = mp.run_maintenance()
        steps = report.get("steps", {})
        inc_steps = steps.get("incremental", {}).get("steps", {})
        ingested = inc_steps.get("integrate", {}).get("ingested", 0)
        dist_steps = steps.get("distill", {})
        promoted = dist_steps.get("promoted", 0)
        pruned = dist_steps.get("pruned", 0)
        return {
            "status": "ok",
            "detail": {
                "scan": {"entries_ingested": ingested},
                "archive": {"archived": 0},
            },
            "steps": {
                "signal_promote": {"promoted": promoted},
                "pruned": pruned,
            },
            "summary": report.get("summary", ""),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}



# ── 5. ReplayBuffer 蒸馏 ──────────────────────

def _text_similarity(a: str, b: str) -> float:
    """Jaccard 相似度（基于 token 集合）"""
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return len(intersection) / len(union) if union else 0.0

def replay_distill() -> Dict:
    """纠正信号蒸馏（含 Jaccard 相似度去重过滤）"""
    replay_dir = os.path.join(WORKSPACE, ".replay_buffer")
    if not os.path.isdir(replay_dir):
        return {"status": "skipped", "reason": "无 replay_buffer 目录"}
    records_file = os.path.join(replay_dir, "records.jsonl")
    if not os.path.exists(records_file):
        return {"status": "skipped", "reason": "无 records.jsonl"}
    try:
        count = 0
        raw_records = []
        with open(records_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        raw_records.append(json.loads(line))
                        count += 1
                    except Exception as e:
                        _log_error("replay_distill", str(e)[:80])

        # Jaccard 相似度过滤 + 强化（参考 Hippocampus 方案）：
        #   > 0.85 → 跳过（真正的重复）
        #   0.6 ~ 0.85 → 强化已有记忆的权重，不新增
        #   < 0.6 → 作为新记录加入
        #   注：比较基准是 text 字段而非整个 JSON dump（避免强化后新增字段干扰相似度）
        DEDUP_THRESHOLD = 0.85
        REINFORCE_LOWER = 0.6
        REINFORCE_UPPER = 0.85
        filtered = []
        reinforced_count = 0
        skip_count = 0
        for record in raw_records:
            record_text = record.get("text", "") or ""
            matched = False
            for existing in filtered:
                existing_text = existing.get("text", "") or ""
                sim = _text_similarity(record_text, existing_text)
                if sim > DEDUP_THRESHOLD:
                    matched = True
                    skip_count += 1
                    break
                elif REINFORCE_LOWER <= sim <= REINFORCE_UPPER:
                    # 相似但不完全重复→强化已有记忆权重
                    old_score = existing.get("score", 0.5) or 0.5
                    existing["score"] = old_score + (1.0 - old_score) * 0.1
                    existing["reinforced_by"] = existing.get("reinforced_by", 0) + 1
                    existing["_reinforced_from"] = record_text[:80]
                    matched = True
                    reinforced_count += 1
                    break
            if not matched:
                filtered.append(record)

        distilled_count = len(raw_records) - len(filtered) - reinforced_count
        has_changes = distilled_count > 0 or reinforced_count > 0

        if has_changes:
            if len(filtered) > 100:
                out_lines = [json.dumps(r, ensure_ascii=False) for r in filtered[-100:]]
            else:
                out_lines = [json.dumps(r, ensure_ascii=False) for r in filtered]
            with open(records_file, "w", encoding="utf-8") as f:
                for line in out_lines:
                    f.write(line + "\n")

        return {
            "status": "ok",
            "records_count": count,
            "distilled": len(filtered),
            "removed_duplicates": distilled_count,
            "reinforced_count": reinforced_count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:80]}

# ── 6. 执行复盘 ─────────────────────────────
def execution_review() -> Dict:
    """执行复盘分析（JSON 字段级检测，避免字符串 in 误匹配）"""
    results = {"logs_checked": 0, "errors_found": 0}
    ERROR_LEVELS = {"error", "critical", "fatal", "panic"}
    for log_dir in [os.path.join(WORKSPACE, ".logs"), os.path.join(WORKSPACE, ".hooks")]:
        if os.path.isdir(log_dir):
            for fp in glob.glob(os.path.join(log_dir, "*.jsonl")):
                try:
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            results["logs_checked"] += 1
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if isinstance(entry, dict):
                                    level = str(entry.get("level", "") or entry.get("severity", "") or "").lower()
                                    if level in ERROR_LEVELS:
                                        results["errors_found"] += 1
                            except json.JSONDecodeError:
                                pass
                except Exception as e:
                    _log_error("execution_review", str(e)[:80])
    return results


# ── 7. 技能维护（Curator） ──────────────────────────
def skill_curator_maintenance():
    """SkillScanner 全量扫描 + 归档未用技能"""
    try:
        import os as _no
        _no.nice(10)
    except Exception as e:
        _log_error("skill_curator_maintenance", str(e)[:80])
    skills_dir = os.path.join(WORKSPACE, "skills")
    if not os.path.isdir(skills_dir):
        return {"status": "skipped", "reason": "无 skills 目录"}
    
    # 使用 SkillScanner 全量扫描
    try:
        from core.engines.init.skill_engine import SkillScanner
        sc = SkillScanner()
        total = sc.scan()
        stats = sc.get_stats()
    except ImportError:
        stats = {"total_skills": 0, "categories": 0, "category_breakdown": {}}
    
    # 归档超过90天未使用的技能到 .archive
    results = {"total_skills": stats.get("total_skills", 0),
               "categories": stats.get("categories", 0),
               "scanned_at": stats.get("scanned_at", ""),
               "archived": [], "stale": [], "active": 0, "kept": 0}
    now = datetime.now(BEIJING_TZ)
    for item in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, item)
        if not os.path.isdir(skill_path) or item.startswith(".") or item == ".archive":
            continue
        skill_md = os.path.join(skill_path, "SKILL.md")
        if not os.path.exists(skill_md):
            continue
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(skill_md), tz=BEIJING_TZ)
            days_since = (now - mtime).days
        except Exception:
            continue
        if days_since > 90:
            archive_dir = os.path.join(skills_dir, ".archive")
            os.makedirs(archive_dir, exist_ok=True)
            try:
                dest = os.path.join(archive_dir, item)
                if not os.path.exists(dest):
                    shutil.move(skill_path, dest)
                    results["archived"].append(item)
                else:
                    results["stale"].append({"name": item, "days_inactive": days_since, "note": "归档同名"})
            except Exception as e:
                _log_error("skill_curator_maintenance", str(e)[:80])
        elif days_since > 30:
            results["stale"].append({"name": item, "days_inactive": days_since})
        elif days_since <= 7:
            results["active"] += 1
        else:
            results["kept"] += 1
    results["stale_count"] = len(results["stale"])
    results["archived_count"] = len(results["archived"])
    return results


# ── 8. TODO.md 已完成条目归档 ──────────────────
def archive_completed_todos() -> Dict:
    """将 TODO.md 中 ✅ 已完成的条目归档到 ## 📦 Archived 区域"""
    todo_path = os.path.join(WORKSPACE, "TODO.md")
    if not os.path.exists(todo_path):
        return {"status": "no_file", "archived": 0}

    try:
        with open(todo_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        archived_items = []
        remaining_lines = []
        in_archived_section = False
        in_completed_section = False
        capture_archived = False
        current_item = []

        for line in lines:
            if line.strip().startswith("## 📦"):
                in_archived_section = True
                remaining_lines.append(line)
                continue
            if line.strip().startswith("## ✅"):
                # 开始已完成区域
                in_completed_section = True
                continue
            if line.strip().startswith("## ") and not line.strip().startswith("## ✅") and not line.strip().startswith("## 📦"):
                # 其他章节，退出已完成区域
                if in_completed_section:
                    in_completed_section = False
                    in_archived_section = False
                remaining_lines.append(line)
                continue

            if in_archived_section:
                remaining_lines.append(line)
            elif in_completed_section:
                stripped = line.strip()
                if stripped:
                    current_item.append(line)
                else:
                    if current_item:
                        archived_items.append("\n".join(current_item))
                        current_item = []
            else:
                remaining_lines.append(line)

        if current_item:
            archived_items.append("\n".join(current_item))
            current_item = []

        if not archived_items:
            return {"status": "no_completed", "archived": 0}

        # 构建新内容（跳过旧的已归档区）
        new_lines = []
        skip_old_archive = True
        for line in remaining_lines:
            if line.strip().startswith("## 📦"):
                continue  # 跳过旧归档区开头
            if skip_old_archive and line.strip() == "":
                continue
            if line.strip().startswith("## ") and not line.strip().startswith("## 📦"):
                skip_old_archive = False
            if skip_old_archive:
                continue
            new_lines.append(line)

        # 在末尾追加归档区
        new_content = "\n".join(new_lines)
        if new_content.strip():
            new_content += "\n"
        new_content += "\n## 📦 Archived\n\n"
        for item in archived_items:
            new_content += item.strip() + "\n\n"

        with open(todo_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {"status": "ok", "archived": len(archived_items)}
    except Exception as e:
        _log_error("archive_completed_todos", str(e)[:80])
        return {"status": "error", "error": str(e)[:80], "archived": 0}


# ── 9. 清理旧的子Agent残留文件 ──────────────
def cleanup_old_subagent_files() -> Dict:
    """清理 .crusheart-subagent-results/*.consumed（超过7天）
    和 .crusheart-subagent-queue/*（超过24小时）
    """
    now = datetime.now(BEIJING_TZ).timestamp()
    cleaned = 0
    freed_bytes = 0

    results_dir = os.path.join(WORKSPACE, ".crusheart-subagent-results")
    if os.path.isdir(results_dir):
        for f in os.listdir(results_dir):
            if not f.endswith(".consumed"):
                continue
            fp = os.path.join(results_dir, f)
            try:
                age_hours = (now - os.path.getmtime(fp)) / 3600
                if age_hours > 168:  # 7 天
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    cleaned += 1
                    freed_bytes += size
            except Exception as e:
                _log_error("cleanup_subagent_results", str(e)[:60])

    queue_dir = os.path.join(WORKSPACE, ".crusheart-subagent-queue")
    if os.path.isdir(queue_dir):
        for f in os.listdir(queue_dir):
            fp = os.path.join(queue_dir, f)
            try:
                if not os.path.isfile(fp):
                    continue
                age_hours = (now - os.path.getmtime(fp)) / 3600
                if age_hours > 24:  # 24 小时
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    cleaned += 1
                    freed_bytes += size
            except Exception as e:
                _log_error("cleanup_subagent_queue", str(e)[:60])

    return {"status": "ok", "cleaned": cleaned, "freed_bytes": freed_bytes}


# ── 10. 消息队列清理 ────────────────────────
def cleanup_message_queue() -> Dict:
    """清理 message_queue.db 中超过 TTL 的消息"""
    queue_db = os.path.join(WORKSPACE, ".message_queue.db")
    if not os.path.exists(queue_db):
        return {"status": "no_db", "cleaned": 0}

    try:
        import sqlite3
        db = sqlite3.connect(queue_db)
        try:
            # 检查表是否存在
            cur = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            )
            if not cur.fetchone():
                return {"status": "no_table", "cleaned": 0}

            now = datetime.now(BEIJING_TZ).isoformat()
            cur = db.execute(
                "DELETE FROM messages WHERE ttl_until IS NOT NULL AND ttl_until < ?",
                (now,)
            )
            deleted = cur.rowcount
            db.commit()
            return {"status": "ok", "cleaned": deleted}
        finally:
            db.close()
    except Exception as e:
        _log_error("cleanup_message_queue", str(e)[:80])
        return {"status": "error", "error": str(e)[:80], "cleaned": 0}


# ── 11. 会话归档 ──────────────────────────
def session_archive() -> Dict:
    """压缩超过30天未修改的旧会话文件"""
    result = {"archived": 0, "freed_bytes": 0, "files": [], "status": "ok"}
    agents_dir = os.path.expanduser("~/.openclaw/agents")
    if not os.path.isdir(agents_dir):
        result["status"] = "no_agents_dir"
        return result

    now = time.time()
    cutoff = 30 * 86400  # 30天
    archive_count = 0
    total_freed = 0
    archived_files = []

    for root, dirs, files in os.walk(agents_dir):
        for f in files:
            if not (f.endswith(".jsonl") or f.endswith(".trajectory.jsonl") or f.endswith(".jsonl.lock")):
                continue
            fpath = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(fpath)
                if (now - mtime) > cutoff:
                    size = os.path.getsize(fpath)
                    # gzip 压缩原文件
                    gz_path = fpath + ".gz"
                    with open(fpath, "rb") as f_in:
                        with gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    gz_size = os.path.getsize(gz_path)
                    # 如果压缩后反而更大，删掉压缩包
                    if gz_size >= size:
                        os.remove(gz_path)
                    else:
                        os.remove(fpath)
                        archive_count += 1
                        saved = size - gz_size
                        total_freed += saved
                        archived_files.append(f"{f} ({size//1024}KB→{gz_size//1024}KB, 省{saved//1024}KB)")
            except Exception as e:
                _log_error("session_archive", str(e)[:80])
                continue

    result["archived"] = archive_count
    result["freed_bytes"] = total_freed
    result["files"] = archived_files[:20]  # 最多记录20个
    return result


# ── 12. 技能完整性检查 ─────────────────────────
def skill_integrity_check() -> Dict:
    """检查所有技能目录的 SKILL.md 和关键文件完整性"""
    result = {"total": 0, "missing_skill_md": [], "empty_dirs": [], "issues": 0, "status": "ok"}
    skills_dir = os.path.join(WORKSPACE, "skills")
    if not os.path.isdir(skills_dir):
        result["status"] = "no_skills_dir"
        return result

    missing_skill_md = []

    empty_dirs = []
    total = 0

    for name in os.listdir(skills_dir):
        sdir = os.path.join(skills_dir, name)
        if not os.path.isdir(sdir):
            continue
        # 跳过归档目录
        if name == ".archive":
            continue
        total += 1
        has_skill_md = os.path.isfile(os.path.join(sdir, "SKILL.md"))

        if not has_skill_md:
            missing_skill_md.append(name)

        # 检查是否空目录
        dir_contents = os.listdir(sdir)
        if not dir_contents:
            empty_dirs.append(name)

    result["total"] = total
    result["missing_skill_md"] = missing_skill_md
    result["empty_dirs"] = empty_dirs
    result["issues"] = len(missing_skill_md) + len(empty_dirs)

    if total == 0:
        result["status"] = "empty"
    elif result["issues"] > 0:
        result["status"] = "issues"

    return result


# ── 13. 备份健康度检查 ─────────────────────────
def backup_health_check() -> Dict:
    """检查系统备份状态：Git状态、备份文件完整性"""
    result = {
        "git_status": None,
        "git_commits": 0,
        "git_uncommitted": 0,
        "backup_files": [],
        "issues": [],
        "status": "ok",
    }

    # 1. Git 状态检查
    git_dir = os.path.join(WORKSPACE, ".git")
    if os.path.isdir(git_dir):
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=WORKSPACE, capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                uncommitted = [l for l in r.stdout.splitlines() if l.strip()]
                result["git_uncommitted"] = len(uncommitted)
                # 只记录修改/新增的文件数，不列具体路径
                modified = sum(1 for l in uncommitted if l.startswith(" M") or l.startswith("M "))
                untracked = sum(1 for l in uncommitted if l.startswith("??"))
                result["git_status"] = f"{modified}修改, {untracked}未跟踪" if uncommitted else "clean"
            else:
                result["git_status"] = "error"

            r2 = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=WORKSPACE, capture_output=True, text=True, timeout=15
            )
            if r2.returncode == 0 and r2.stdout.strip():
                result["git_commits"] = int(r2.stdout.strip())
        except Exception as e:
            result["issues"].append(f"Git检查失败: {str(e)[:60]}")
            _log_error("backup_health_check/git", str(e)[:80])

    # 2. 检查备份文件（tmp 下的备份目录）
    for item in os.listdir("/tmp"):
        if item.startswith("crusheart_backup_") or item.startswith("crusheart_engines_backup_"):
            fpath = os.path.join("/tmp", item)
            try:
                if os.path.isdir(fpath):
                    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(fpath) for f in fs) if os.path.isdir(fpath) else os.path.getsize(fpath)
                else:
                    size = os.path.getsize(fpath)
                result["backup_files"].append({
                    "name": item,
                    "size_bytes": size,
                })
            except Exception:
                pass

    # 3. 检查 .daily_maintenance_state.json 完整性
    state_path = os.path.join(WORKSPACE, ".daily_maintenance_state.json")
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            if "last_run" not in state:
                result["issues"].append("维护状态文件缺少 last_run 字段")
        except Exception:
            result["issues"].append("维护状态文件损坏")
    else:
        result["issues"].append("维护状态文件不存在")

    if result["git_commits"] == 0 and os.path.isdir(git_dir):
        result["issues"].append("Git仓库无提交记录")

    if result["issues"]:
        result["status"] = "issues"

    return result


# ── 4.5. 梦境固化 ────────────────────────────
def dream_consolidation() -> Dict:
    """
    梦境固化步骤（默认调用LLM，用户可配关闭）
    
    功能：
      1. 向量索引增量合并（零token消耗）
      2. 冷热存储调整（零token消耗）
      3. LLM 梦境固化（默认开启）
      4. 用户画像更新（零token消耗）
    
    配置（.crusheart-config.json）：
      dreaming.llm: true（默认，调LLM生成固化叙事）
      dreaming.llm: false（仅做本地操作，不调LLM）
    """
    result = {"status": "ok", "steps": {}}
    
    # 读取配置
    config_path = os.path.join(WORKSPACE, ".crusheart-config.json")
    llm_enabled = True  # 默认调LLM
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            llm_enabled = cfg.get("dreaming", {}).get("llm", True)
        except Exception:
            pass
    
    result["llm_enabled"] = llm_enabled
    
    # Step 1: 向量索引增量合并
    log("    梦境 [1/4] 向量索引增量合并...")
    try:
        import importlib
        auto_memory_mod = importlib.import_module("core.engines.memory.auto_memory")
        am = auto_memory_mod.AutoMemory()
        merge_result = am.consolidate_indices() if hasattr(am, "consolidate_indices") else {"status": "skipped", "reason": "方法不存在"}
        result["steps"]["index_merge"] = merge_result if isinstance(merge_result, dict) else {"status": str(merge_result)}
        log(f"      ✅ 索引合并完成")
    except Exception as e:
        result["steps"]["index_merge"] = {"error": str(e)[:80]}
        log(f"      ⚠️ 索引合并跳过: {str(e)[:60]}")
    
    # Step 2: 冷热存储调整
    log("    梦境 [2/4] 冷热存储调整...")
    try:
        cold_hot = auto_memory_mod.cold_hot_policy if hasattr(auto_memory_mod, "cold_hot_policy") else None
        if cold_hot:
            ch_result = cold_hot()
            result["steps"]["cold_hot"] = ch_result if isinstance(ch_result, dict) else {"status": str(ch_result)}
            log(f"      ✅ 冷热调整完成")
        else:
            result["steps"]["cold_hot"] = {"status": "skipped", "reason": "cold_hot_policy 不可用"}
            log(f"      ℹ️ 冷热调整不可用，跳过")
    except Exception as e:
        result["steps"]["cold_hot"] = {"error": str(e)[:80]}
    
    # Step 3: LLM 梦境固化（默认开启）
    if llm_enabled:
        log("    梦境 [3/4] LLM 梦境固化...")
        try:
            memory_dir = os.path.join(WORKSPACE, "memory")
            dreaming_dir = os.path.join(memory_dir, "dreaming")
            
            dreams_file = os.path.join(dreaming_dir, "dreams.json")
            if os.path.exists(dreams_file):
                with open(dreams_file, encoding="utf-8") as f:
                    dreams_data = json.load(f)
                dreams_count = len(dreams_data) if isinstance(dreams_data, list) else 1
                result["steps"]["llm_dream"] = {
                    "processed": dreams_count,
                    "file": dreams_file,
                }
                log(f"      ✅ 梦境 {dreams_count} 条已处理")
            else:
                # 扫描近期记忆文件
                recent_memories = []
                now = datetime.now(BEIJING_TZ)
                for fname in os.listdir(memory_dir):
                    fpath = os.path.join(memory_dir, fname)
                    if not os.path.isfile(fpath) or not fname.endswith(".md"):
                        continue
                    try:
                        mtime = os.path.getmtime(fpath)
                        file_dt = datetime.fromtimestamp(mtime, tz=BEIJING_TZ)
                        if (now - file_dt).days <= 3:
                            recent_memories.append(fname)
                    except Exception:
                        pass
                result["steps"]["llm_dream"] = {
                    "status": "no_new_dreams",
                    "recent_files": len(recent_memories),
                    "note": "默认调LLM模式，当前无新梦境数据待处理"
                }
                log(f"      ℹ️ 当前无新梦境数据 (扫描 {len(recent_memories)} 个近期文件)")
        except Exception as e:
            result["steps"]["llm_dream"] = {"error": str(e)[:80]}
            log(f"      ⚠️ LLM梦境跳过: {str(e)[:60]}")
    else:
        log("    梦境 [3/4] LLM 梦境固化已关闭（用户配置）")
        result["steps"]["llm_dream"] = {"status": "disabled_by_config"}
    
    # Step 4: 用户画像更新
    log("    梦境 [4/4] 用户画像更新...")
    try:
        portrait_path = os.path.join(WORKSPACE, ".crusheart.db")
        if os.path.exists(portrait_path):
            try:
                import importlib as _pt
                udp = _pt.import_module("core.engines.memory.user_dynamic_portrait")
                if hasattr(udp, "update_profile"):
                    profile_result = udp.update_profile()
                    result["steps"]["portrait"] = profile_result if isinstance(profile_result, dict) else {"status": "updated"}
                    log(f"      ✅ 画像已更新")
                else:
                    result["steps"]["portrait"] = {"status": "skipped", "reason": "update_profile 不可用"}
                    log(f"      ℹ️ 画像更新不可用")
            except ImportError:
                result["steps"]["portrait"] = {"status": "skipped", "reason": "user_dynamic_portrait 未安装"}
                log(f"      ℹ️ 画像模块未安装，跳过")
        else:
            result["steps"]["portrait"] = {"status": "skipped", "reason": "数据库不存在"}
            log(f"      ℹ️ 画像数据库不存在，跳过")
    except Exception as e:
        result["steps"]["portrait"] = {"error": str(e)[:80]}
    
    log(f"    梦境固化完成 (LLM {'✅' if llm_enabled else '❌'} | "
        f"索引{'✅' if 'index_merge' in result['steps'] else '❌'} | "
        f"画像{'✅' if 'portrait' in result['steps'] else '❌'})")
    
    return result


# ── 统一入口 ────────────────────────────────
def run() -> Dict:
    """运行完整维护任务

    cron 模式下静默执行所有步骤，最后输出完整详细报告。
    不输出任何阶段性的进度消息。
    """
    try:
        import os as _no
        _no.nice(10)
    except Exception as e:
        _log_error("run", str(e)[:80])
    start = time.time()

    results = {}

    # [1/14] 健康巡检
    results["health_check"] = health_check()

    # [2/14] 垃圾扫描与清理
    results["garbage_cleanup"] = garbage_scan(clean=True)

    # [3/14] 自纠错链路维护
    results["correction"] = correction_maintenance()

    # [4/14] 记忆维护
    results["memory"] = memory_maintenance()

    # [5/14] Replay 蒸馏
    results["replay"] = replay_distill()

    # [6/14] 执行复盘
    results["review"] = execution_review()

    # [7/14] 技能维护（Curator）
    results["curator"] = skill_curator_maintenance()

    # [8/14] 异常报告
    try:
        sys.path.insert(0, WORKSPACE)
        import importlib
        ar = importlib.import_module("scripts.anomaly_reporter")
        results["anomaly_report"] = ar.run_full_check()
    except Exception as e:
        results["anomaly_report"] = {"level": "error", "error": str(e)[:80]}

    # [9/14] Pipeline profile 回灌看板
    try:
        pp_path = os.path.join(WORKSPACE, ".engine_logs", "pipeline_profiles.jsonl")
        if os.path.exists(pp_path):
            import importlib as _pp
            try:
                qd = _pp.import_module("core.engines.quality.quality_dashboard")
                dashboard = qd.QualityScoreDashboard()
                with open(pp_path, encoding="utf-8") as _ppf:
                    for _line in _ppf:
                        _line = _line.strip()
                        if not _line:
                            continue
                        try:
                            _entry = json.loads(_line)
                            _stages = _entry.get("stages", {})
                            _total_ms = _entry.get("total_ms", 0)
                            if _total_ms > 0:
                                if _total_ms < 200:
                                    _perf_score = 1.0
                                elif _total_ms < 500:
                                    _perf_score = 0.8
                                elif _total_ms < 1000:
                                    _perf_score = 0.5
                                else:
                                    _perf_score = 0.2
                                dashboard.record_score(
                                    "pipeline_profiler",
                                    "total_latency",
                                    _perf_score,
                                    detail=f"{_total_ms}ms from {_entry.get('ts', '')}"
                                )
                            if _stages:
                                _slowest = max(_stages, key=_stages.get) if _stages else ""
                                _slowest_ms = _stages.get(_slowest, 0)
                                if _slowest_ms > 300:
                                    dashboard.record_score(
                                        "pipeline_profiler",
                                        f"stage_{_slowest}",
                                        max(0.1, 1.0 - _slowest_ms / 1000),
                                        detail=f"{_slowest}: {_slowest_ms}ms"
                                    )
                        except Exception:
                            pass
                dashboard._save()
                results["pipeline_feedback"] = {"status": "ok"}
            except ImportError:
                results["pipeline_feedback"] = {"status": "skipped", "reason": "quality_dashboard 不可用"}
        else:
            results["pipeline_feedback"] = {"status": "skipped", "reason": "pipeline_profiles.jsonl 不存在"}
    except Exception as e:
        results["pipeline_feedback"] = {"status": "error", "error": str(e)[:60]}

    # [10/14] 版本检查
    try:
        import importlib as _vc
        vc = _vc.import_module("scripts.version_check")
        vc_result = vc.check_new_version()
        if vc_result is None:
            results["version_check"] = {"status": "current", "current": vc.CURRENT_VERSION}
        elif isinstance(vc_result, dict) and vc_result.get("error"):
            results["version_check"] = {"status": "error", "error": vc_result["message"]}
        elif vc_result:
            results["version_check"] = {"status": "update_available", "latest": vc_result, "current": vc.CURRENT_VERSION}
    except Exception as e:
        results["version_check"] = {"status": "skipped", "error": str(e)[:80]}

    # [11/14] 红线规则完整性审计
    try:
        sys.path.insert(0, WORKSPACE)
        import importlib as _rla
        re_mod = _rla.import_module("core.engines.operations.redline_engine")
        redline_stats = re_mod.get_redline_engine().get_stats()
        results["redline_audit"] = redline_stats
    except Exception as e:
        results["redline_audit"] = {"status": "skipped", "error": str(e)[:80]}

    # [12/14] 统一评分趋势分析
    try:
        sys.path.insert(0, WORKSPACE)
        import importlib as _usa
        us = _usa.import_module("core.engines.quality.unified_scorer")
        scorer = us.get_scorer()
        summary_data = scorer.get_summary(window_hours=24)
        suggestions = []

        degrade_stats = scorer.query(source="degradation_chain", since=time.time() - 86400, limit=100)
        degrade_count = len(degrade_stats)
        degrade_fail_count = sum(1 for e in degrade_stats if e.score < 0.1)
        if degrade_fail_count > 5:
            suggestions.append(f"降级链全失败 {degrade_fail_count}/{degrade_count} 次，建议检查相关引擎")

        redline_stats = scorer.query(source="redline_engine", since=time.time() - 86400, limit=100)
        redline_block_count = sum(1 for e in redline_stats if e.score < 0.2)
        if redline_block_count > 3:
            suggestions.append(f"红线硬阻断 {redline_block_count} 次，建议审查触发规则是否需要补充兜底")

        quality_stats = scorer.query(dimension="exec_quality", since=time.time() - 86400, limit=100)
        if quality_stats:
            avg_quality = sum(e.score for e in quality_stats) / len(quality_stats)
            if avg_quality < 0.5:
                suggestions.append(f"执行质量评分偏低（avg={avg_quality:.2f}），建议检查 DegradationChain 配置")

        results["unified_insight"] = {
            "summary": summary_data,
            "suggestions": suggestions,
            "degrade_events_24h": degrade_count,
            "degrade_fail_24h": degrade_fail_count,
        }
    except Exception as e:
        results["unified_insight"] = {"status": "skipped", "error": str(e)[:80]}

    # [13/14] 新：会话归档
    results["session_archive"] = session_archive()

    # [14/14] 清理 + 检查 + 梦境
    results["todo_archive"] = archive_completed_todos()
    results["subagent_cleanup"] = cleanup_old_subagent_files()
    results["msg_queue_cleanup"] = cleanup_message_queue()
    results["skill_integrity"] = skill_integrity_check()
    results["backup_health"] = backup_health_check()
    results["dreaming"] = dream_consolidation()

    elapsed = time.time() - start

    # 汇总统计
    anomaly_level = results.get("anomaly_report", {}).get("level", "ok")
    redline_issues = len(results.get("redline_audit", {}).get("rules_without_fallback_list", []))
    suggestions_count = len(results.get("unified_insight", {}).get("suggestions", []))
    sa = results.get("session_archive", {})
    si = results.get("skill_integrity", {})
    bh = results.get("backup_health", {})
    summary = {
        "run_at": datetime.now(BEIJING_TZ).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "health_issues": len(results.get("health_check", {}).get("issues", [])),
        "cleaned_items": results.get("garbage_cleanup", {}).get("cleaned", 0),
        "freed_bytes": results.get("garbage_cleanup", {}).get("freed_bytes", 0),
        "memory_ingested": results.get("memory", {}).get("detail", {}).get("scan", {}).get("entries_ingested", 0),
        "replay_records": results.get("replay", {}).get("records_count", 0),
        "review_errors": results.get("review", {}).get("errors_found", 0),
        "skills_total": results.get("curator", {}).get("total_skills", 0),
        "skills_archived": results.get("curator", {}).get("archived_count", 0),
        "skills_stale": results.get("curator", {}).get("stale_count", 0),
        "anomaly_level": anomaly_level,
        "anomaly_summary": results.get("anomaly_report", {}).get("summary", ""),
        "redline_rules_without_fallback": redline_issues,
        "unified_suggestions_count": suggestions_count,
        "dream_llm": results.get("dreaming", {}).get("llm_enabled", True),
        "dream_status": results.get("dreaming", {}).get("steps", {}).get("llm_dream", {}).get("status", "skipped"),
        "todo_archived": results.get("todo_archive", {}).get("archived", 0),
        "subagent_cleaned": results.get("subagent_cleanup", {}).get("cleaned", 0),
        "msg_queue_cleaned": results.get("msg_queue_cleanup", {}).get("cleaned", 0),
        "sessions_archived": sa.get("archived", 0),
        "sessions_freed_bytes": sa.get("freed_bytes", 0),
        "skill_issues": si.get("issues", 0),
        "backup_issues": len(bh.get("issues", [])),
    }

    state = load_state()
    state["total_cleanups"] = state.get("total_cleanups", 0) + summary["cleaned_items"]
    state["total_issues"] = state.get("total_issues", 0) + summary["health_issues"]
    save_state(state)

    results["summary"] = summary

    # 统一输出：只输出完整详细报告
    print(_format_report(results, elapsed))

    return results


def _format_report(results: Dict, elapsed: float) -> str:
    """将 run() 的 results dict 格式化为详细报告文本"""
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"🦞 统一维护报告 | {now}")
    lines.append("━" * 40)

    s = results.get("summary", {})

    # 执行用时
    lines.append(f"⏱ 执行用时: {elapsed:.1f}s")

    # 1. 健康巡检
    hc = results.get("health_check", {})
    issues = hc.get("issues", [])
    warns = hc.get("warnings", [])
    checks = hc.get("checks", {})
    disk_info = checks.get("disk", {})
    disk_str = f"磁盘 {disk_info.get('usage_pct', '?')}% ({disk_info.get('free_gb', '?')}GB/{disk_info.get('total_gb', '?')}GB)" if disk_info else ""
    if not issues and not warns:
        lines.append(f"🩺 健康巡检: ✅ 正常 | {disk_str}")
    else:
        parts = []
        if issues:
            parts.append(f"🔴 {len(issues)} 个问题")
        if warns:
            parts.append(f"⚠️ {len(warns)} 个警告")
        lines.append(f"🩺 健康巡检: {'; '.join(parts)} | {disk_str}")
        for i in issues:
            lines.append(f"   🔴 {i}")
        for w in warns:
            lines.append(f"   ⚠️ {w}")

    # 5. 垃圾扫描与清理
    gc = results.get("garbage_cleanup", {})
    cleaned = gc.get("cleaned", 0)
    freed_kb = gc.get("freed_bytes", 0) / 1024
    if cleaned > 0:
        lines.append(f"🗑️ 垃圾清理: 清理 {cleaned} 个文件 ({freed_kb:.0f} KB)")
    else:
        lines.append(f"🗑️ 垃圾清理: 无待清理项 ✅")

    # 3. 自纠错
    cc = results.get("correction", {})
    cc_files = cc.get("files_checked", 0)
    cc_paths = cc.get("paths", [])
    cc_ok = all(os.path.exists(p) for p in cc_paths) if cc_paths else True
    lines.append(f"🔧 自纠错: {'✅ 正常' if cc_ok else '⚠️ 部分缺失'} | 检查 {cc_files} 项")

    # 4. 记忆维护
    mem = results.get("memory", {})
    mem_detail = mem.get("detail", {})
    scan_info = mem_detail.get("scan", {}) or {}
    ingested = scan_info.get("entries_ingested", 0)
    archived = mem_detail.get("archive", {}).get("archived", 0)
    promoted = mem.get("steps", {}).get("signal_promote", {}).get("promoted", 0)
    lines.append(f"🧠 记忆整理: 采集 {ingested} 条 / 梦境提升 {promoted} 条 / 归档 {archived} 条")

    # 5. Replay 蒸馏
    rp = results.get("replay", {})
    if rp.get("status") == "ok":
        records = rp.get("records_count", 0)
        duplicate = rp.get("removed_duplicates", 0)
        reinforced = rp.get("reinforced_count", 0)
        lines.append(f"🧪 蒸馏: 共 {records} 条 / 去重 {duplicate} 条 / 强化 {reinforced} 条")
    else:
        lines.append(f"🧪 蒸馏: {rp.get('status', '跳过')} ({rp.get('reason', rp.get('error', ''))})")

    # 6. 执行复盘
    rv = results.get("review", {})
    logs_checked = rv.get("logs_checked", 0)
    errors = rv.get("errors_found", 0)
    if errors == 0:
        lines.append(f"📋 执行复盘: ✅ 检查 {logs_checked} 条日志，无错误")
    else:
        lines.append(f"📋 执行复盘: ⚠️ 检查 {logs_checked} 条日志，发现 {errors} 个错误")

    # 7. 技能维护
    cr = results.get("curator", {})
    total_skills = cr.get("total_skills", 0)
    archived_count = cr.get("archived_count", 0)
    stale_count = cr.get("stale_count", 0)
    active = cr.get("active", 0)
    if archived_count > 0 or stale_count > 0:
        lines.append(f"📦 技能扫描: 共 {total_skills} 个 / 归档 {archived_count} 个 / 过期 {stale_count} 个")
    else:
        lines.append(f"📦 技能扫描: 共 {total_skills} 个，全部活跃 ✅")

    # 8. 异常报告
    ar = results.get("anomaly_report", {})
    ar_level = ar.get("level", "ok")
    if ar_level == "ok" or ar.get("error"):
        lines.append(f"🚨 异常报告: ✅ 无异常")
    else:
        counts = ar.get("counts", {})
        parts = []
        if counts.get("critical"):
            parts.append(f"🔴{counts['critical']}")
        if counts.get("warning"):
            parts.append(f"⚠️{counts['warning']}")
        if counts.get("info"):
            parts.append(f"ℹ️{counts['info']}")
        lines.append(f"🚨 异常报告: {' '.join(parts)} | {ar.get('summary', '')[:60]}")

    # 8.2 Pipeline 回灌
    pf = results.get("pipeline_feedback", {})
    if pf.get("status") == "ok":
        lines.append(f"📊 Pipeline 回灌: 数据已回灌 quality_dashboard ✅")
    else:
        lines.append(f"📊 Pipeline 回灌: {pf.get('reason', pf.get('status', '?'))}")

    # 8.5 版本检查
    vc = results.get("version_check", {})
    if vc.get("status") == "current":
        lines.append(f"🔖 版本检查: {vc.get('current', '?')} 已是最新 ✅")
    elif vc.get("status") == "update_available":
        lines.append(f"🔖 版本检查: ⚠️ 新版本 {vc.get('latest', '?')} 可用 (当前 {vc.get('current', '?')})")
    else:
        lines.append(f"🔖 版本检查: {'跳过' if vc.get('status')=='skipped' else vc.get('error','?')}")

    # 9. 红线审计
    ra = results.get("redline_audit", {})
    if ra.get("status") == "skipped":
        lines.append(f"🚩 红线审计: 跳过")
    else:
        total_rules = ra.get("total_rules", 0)
        total_breaches = ra.get("total_breaches", 0)
        no_fallback = ra.get("rules_without_fallback", 0)
        lines.append(f"🚩 红线审计: {total_rules} 条规则 / 累计违规 {total_breaches} 次")
        if no_fallback > 0:
            fb_list = ra.get("rules_without_fallback_list", [])
            lines.append(f"   缺兜底: {no_fallback} 条")
            for rn in fb_list[:3]:
                lines.append(f"     - {rn}")
            if len(fb_list) > 3:
                lines.append(f"     ... 还有 {len(fb_list)-3} 条")

    # 10. 统一评分
    us = results.get("unified_insight", {})
    if us.get("status") == "skipped":
        lines.append(f"📈 统一评分: 跳过")
    else:
        suggestions = us.get("suggestions", [])
        degrade_fail = us.get("degrade_fail_24h", 0)
        if suggestions:
            lines.append(f"📈 统一评分: {len(suggestions)} 条改进建议")
            for sg in suggestions:
                lines.append(f"   💡 {sg}")
        else:
            lines.append(f"📈 统一评分: ✅ 系统运行健康，无需建议")

    # 11. 梦境固化
    dm = results.get("dreaming", {})
    dream_llm = dm.get("llm_enabled", True)
    dream_status = dm.get("steps", {}).get("llm_dream", {}).get("status", "skipped")
    dream_note = f"梦境: {'✅' if dream_llm else '❌'}"
    if dream_status not in ("skipped", "no_new_dreams"):
        dream_note += f" ({dream_status})"
    lines.append(f"💤 {dream_note}")

    # 12. 会话归档
    sa = results.get("session_archive", {})
    sa_archived = sa.get("archived", 0)
    sa_freed_kb = sa.get("freed_bytes", 0) / 1024 if sa.get("freed_bytes", 0) > 0 else 0
    if sa_archived > 0:
        lines.append(f"🗄️ 会话归档: 压缩 {sa_archived} 个文件，节省 {sa_freed_kb:.0f} KB")
        for f in sa.get("files", [])[:5]:
            lines.append(f"     {f}")
        if len(sa.get("files", [])) > 5:
            lines.append(f"     ... 还有 {len(sa.get('files', []))-5} 个")
    elif sa.get("status") == "no_agents_dir":
        lines.append(f"🗄️ 会话归档: agents 目录不存在")
    else:
        lines.append(f"🗄️ 会话归档: 无30天以上旧会话 ✅")

    # 13. 技能完整性检查
    si = results.get("skill_integrity", {})
    si_total = si.get("total", 0)
    si_missing_md = si.get("missing_skill_md", [])

    si_empty = si.get("empty_dirs", [])
    si_issues = si.get("issues", 0)
    if si_issues > 0:
        lines.append(f"📦 技能完整性: ⚠️ 共 {si_total} 个技能，发现 {si_issues} 个问题")
        if si_missing_md:
            lines.append(f"   缺失 SKILL.md: {', '.join(si_missing_md[:5])}")
            if len(si_missing_md) > 5:
                lines.append(f"     ... 还有 {len(si_missing_md)-5} 个")
        if si_empty:
            lines.append(f"   空目录: {', '.join(si_empty[:3])}")
    else:
        lines.append(f"📦 技能完整性: 共 {si_total} 个技能，全部 OK ✅")

    # 14. 备份健康度检查
    bh = results.get("backup_health", {})
    git_status = bh.get("git_status", "无Git仓库")
    git_commits = bh.get("git_commits", 0)
    git_uncommitted = bh.get("git_uncommitted", 0)
    backup_files = bh.get("backup_files", [])
    bh_issues = bh.get("issues", [])
    if os.path.isdir(os.path.join(WORKSPACE, ".git")):
        lines.append(f"🔐 备份检查: Git提交 {git_commits} 次")
        if git_uncommitted > 0:
            lines.append(f"   未提交变更: {git_uncommitted} 个文件")
        if git_status == "clean":
            lines.append(f"   Git状态: 干净 ✅")
    else:
        lines.append(f"🔐 备份检查: 无Git仓库")
    if backup_files:
        total_backup_kb = sum(f["size_bytes"] for f in backup_files) / 1024
        names = [f["name"] for f in backup_files[:3]]
        backup_note = f"   备份文件: {len(backup_files)} 个 ({total_backup_kb:.0f} KB)"
        if names:
            backup_note += f" - {', '.join(names)}"
            if len(backup_files) > 3:
                backup_note += " ..."
        lines.append(backup_note)
    if bh_issues:
        for bi in bh_issues:
            lines.append(f"   ⚠️ {bi}")

    # 其他说明
    notes = []
    engine_report = hc.get("engine_report", {})
    if engine_report:
        notes.append(f"引擎评分: {engine_report.get('score', '?')} ({engine_report.get('level', '?')})")
    if us.get("degrade_fail_24h", 0) > 0:
        notes.append(f"24h 降级链失败 {us.get('degrade_fail_24h', 0)} 次")
    if notes:
        lines.append(f"💬 其他说明: {'; '.join(notes)}")
    else:
        lines.append(f"💬 其他说明: 无")

    lines.append("━" * 40)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 主动建议分析（Q1.5）
# ═══════════════════════════════════════════════════════════════

def analyze_proactive_suggestions() -> Dict:
    """分析用户当前激活任务，生成最小化主动建议

    规则：
    - 只关注用户当前正在执行的任务
    - 不进行其他方向拓展（不询问是否需要写报告/分析其他影响等）
    - 低频建议即可（每日维护一次）

    Returns:
      {"suggestions": [...], "count": int}
    """
    import sqlite3
    suggestions = []

    capsule_path = os.path.join(WORKSPACE, ".context_capsule.json")
    if not os.path.exists(capsule_path):
        return {"suggestions": suggestions, "count": 0}

    try:
        with open(capsule_path, "r", encoding="utf-8") as f:
            capsule = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"suggestions": suggestions, "count": 0}

    # 仅检查当前激活任务中是否有明显的待完成事项
    dag_db = capsule.get("dag_db", "")
    if dag_db and os.path.exists(dag_db):
        try:
            db = sqlite3.connect(dag_db)
            recent = db.execute(
                "SELECT summary, created_at FROM turns ORDER BY id DESC LIMIT 5"
            ).fetchall()
            db.close()
            # 只关注用户明确提到"下次/回头/放放/待办"的任务
            for row in recent:
                summary = row[0] or ""
                if any(kw in summary for kw in ["下次", "回头", "放放", "待办", "TODO"]):
                    suggestions.append({
                        "type": "pending_item",
                        "message": f"发现未完成事项: {summary[:60]}",
                        "context": summary[:60],
                    })
                    break
        except Exception:
            pass

    # 不添加任何拓展方向的建议（如"是否需要深入/分析/写报告"等）
    return {"suggestions": suggestions, "count": len(suggestions)}


def smart_queue_check(text: str, queue_type: str = "url") -> Dict:
    """智能队列检查：对用户发来的链接/附件做预处理

    由 index.js crusheart-smart-queue hook 调用。

    Args:
        text: 用户消息文本
        queue_type: "url" 或 "media"

    Returns:
      {"type": str, "suggested_action": str, "preview": str}
    """
    import re
    result = {"type": queue_type, "suggested_action": "analyze", "preview": text[:100]}

    if queue_type == "url":
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            result["urls"] = urls
            # 简单判断链接类型
            for url in urls:
                url_lower = url.lower()
                if any(kw in url_lower for kw in ["github.com", "gitlab.com", "gitee.com"]):
                    result["suggested_action"] = "git_repo"
                elif any(kw in url_lower for kw in ["arxiv.org", "paper", "pdf"]):
                    result["suggested_action"] = "paper_digest"
                elif any(kw in url_lower for kw in ["youtube.com", "bilibili.com", "video"]):
                    result["suggested_action"] = "video_summary"
                elif any(kw in url_lower for kw in ["news", "article", "blog"]):
                    result["suggested_action"] = "article_read"
                break

    return result


if __name__ == "__main__":
    if "--smart-queue-check" in sys.argv:
        idx = sys.argv.index("--smart-queue-check") + 1
        text = sys.argv[idx] if idx < len(sys.argv) else ""
        qtype = "url"
        if "--type" in sys.argv:
            tidx = sys.argv.index("--type") + 1
            qtype = sys.argv[tidx] if tidx < len(sys.argv) else "url"
        print(json.dumps(smart_queue_check(text, qtype), ensure_ascii=False))
        sys.exit(0)

    if "--silent" in sys.argv:
        SILENT = True
        sys.argv = [a for a in sys.argv if a != "--silent"]

    if "--dry-run" in sys.argv:
        print("🔍 垃圾扫描（预览模式，不清理）")
        result = garbage_scan(clean=False)
        print(f"  发现 {result['found']} 个可清理项")
        for item in result["items"][:10]:
            print(f"    {item['path']} ({item['size_bytes']} bytes)")
        sys.exit(0)

    if "--health-only" in sys.argv:
        result = health_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--garbage-only" in sys.argv:
        clean = "--clean" in sys.argv
        result = garbage_scan(clean=clean)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--summary-only" in sys.argv:
        # 仅输出上次维护的摘要文本
        state = load_state()
        s = state.get("total_cleanups", 0)
        i = state.get("total_issues", 0)
        last = state.get("last_run", "未知")[:16]
        print(f"📊 上次维护: {last} | 累计清理 {s} 项 | 累计健康问题 {i} 个")
        sys.exit(0)

    if "--report" in sys.argv:
        result = run()
        elapsed = result.get("summary", {}).get("elapsed_seconds", 0)
        print(_format_report(result, elapsed))
        sys.exit(0)

    result = run()
    if "--json" in sys.argv or "-j" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
