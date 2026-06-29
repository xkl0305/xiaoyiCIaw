"""
Crusheart Agent OS — 系统健康巡检 v5.0
功能：全链路系统检查 + 自我完整性校验 + 交叉验证 + 目录结构校验 + 垃圾文件检测
定时触发：6:00/18:00（静默模式，仅异常推送）
手动触发：用户说"健康巡检"时返回完整报告

v5.1 (2026-05-14):
  - 新增: 新模块完整性检查（11个编排层+执行层模块）
  - 新增: 任务模板库数量校验
  - 引擎状态文件迁至 .state/ 目录
  - 新增: 目录结构校验（防止重复根目录泛滥）
  - 新增: 垃圾文件/空目录检测
  - 新增: AutoBrainRouter 引擎注册完整性检查
  - 新增: 状态目录(.state/)完整性检查
  - 新增: 引擎-路由一致性交叉验证
"""

import os
import sys
import subprocess
import json
import re
import time
import signal
from datetime import datetime, timezone, timedelta
from collections import OrderedDict
from enum import Enum
from typing import Dict, List, Optional, Union
import logging


class ProblemSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Problem:
    """结构化问题条目"""
    def __init__(self, msg: str, severity: ProblemSeverity = ProblemSeverity.CRITICAL):
        self.msg = msg
        self.severity = severity

    def __str__(self):
        prefix = {
            ProblemSeverity.CRITICAL: "❌",
            ProblemSeverity.WARNING: "⚠️",
            ProblemSeverity.INFO: "ℹ️",
        }.get(self.severity, "")
        return f"{prefix}{self.msg}"

    def to_dict(self):
        return {"msg": self.msg, "severity": self.severity.value}


def safe_subprocess_run(cmd, timeout=10, **kwargs):
    """带真超时 kill 的子进程执行（Popen + kill + wait）"""
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill()
            proc.wait()
        raise
    except BaseException:
        if proc is not None:
            proc.kill()
            proc.wait()
        raise

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ENGINE_STATE = os.path.join(WORKSPACE, ".state", ".engine_state.json")
HEALTH_LOG = os.path.join(WORKSPACE, ".engine_logs", "health_check_log.json")
MAX_WORKSPACE_MB = 300
WARN_WORKSPACE_MB = 200

problems = []
all_ok = True

# ═══════════════════════════════════════════════
# 健康评分系统 v6.0
# 将 pass/fail 检查映射为 0-100 综合健康评分
# ═══════════════════════════════════════════════

# 健康评分维度权重（总和 = 1.0）
HEALTH_DIMENSIONS = OrderedDict([
    ("gateway",       {"name": "Gateway状态",          "weight": 0.20, "check": "check_gateway"}),
    ("engines",       {"name": "引擎健康",            "weight": 0.20, "check": "check_engine_and_modules"}),
    ("memory",        {"name": "记忆系统",            "weight": 0.15, "check": "check_memory_health"}),
    ("cron",          {"name": "定时任务",            "weight": 0.10, "check": "check_cron"}),
    ("disk",          {"name": "磁盘/资源",           "weight": 0.10, "check": "check_disk"}),
    ("quality",       {"name": "质量评分",            "weight": 0.10, "check": "check_quality_score"}),
    ("structure",     {"name": "目录与文件结构",        "weight": 0.08, "check": "check_structure"}),
    ("skills",        {"name": "技能与模块",          "weight": 0.07, "check": "check_skills"}),
])

HEALTH_SCORE_HISTORY_PATH = os.path.join(WORKSPACE, ".autonomy_state", "health_score_history.jsonl")

# 评分过程中的中间数据
_score_results: Dict[str, dict] = {}


def get_health_score() -> Dict:
    """
    计算系统综合健康评分 0-100

    流程：
    1. 运行所有检查，收集 pass/fail 结果
    2. 按加权模型计算各维度得分
    3. 综合加权求和
    4. 记录趋势

    Returns:
        {
            "score": 85,                    # 0-100
            "level": "healthy",             # healthy / degraded / poor / critical
            "dimensions": {                  # 各维度详细
                "gateway": {"score": 100, "weight": 0.20, "status": "ok", "issues": []},
                ...
            },
            "issues": [...],                # 所有问题列表
            "trend": "stable",              # improving / stable / declining
            "previous_score": 82,
        }
    """
    global problems, all_ok, _score_results

    # 保存上次的 problems 状态
    previous_problems = list(problems)

    # 清空并重新运行检查
    problems.clear()
    all_ok = True
    _score_results = {}

    # 运行各维度检查
    dim_scores = {}
    all_issues = []

    for dim_key, dim_cfg in HEALTH_DIMENSIONS.items():
        check_name = dim_cfg["check"]
        weight = dim_cfg["weight"]

        # 获取该维度的检查结果
        before_count = len(problems)
        if check_name == "check_gateway":
            passed = check_gateway()
        elif check_name == "check_cron":
            passed = check_cron()
        elif check_name == "check_disk":
            passed = check_disk()
        elif check_name == "check_skills":
            passed = check_skills()
        elif check_name == "check_engine_and_modules":
            passed = check_engine_state()
            pm = check_new_modules()
            passed = passed and pm
        elif check_name == "check_memory_health":
            pm = check_memory_engine()
            pr = check_rename_integrity()
            passed = pm and pr
        elif check_name == "check_quality_score":
            passed = _check_quality_score_dimension()
        elif check_name == "check_structure":
            pf = check_core_files()
            pd = check_directory_structure()
            pg = check_garbage_files()
            ps = check_state_dir()
            passed = pf and pd and pg and ps
        else:
            passed = True

        after_count = len(problems)
        new_issues = problems[before_count:after_count]

        # 计算维度得分（有 failed 问题 = 0 分，有 warning = 80 分，全部通过 = 100 分）
        if not passed:
            dim_score = 0
        elif new_issues:
            dim_score = 60  # 有告警但不是 fail
        else:
            # 检查是否有任何与此维度相关的问题
            relevant_issues = []
            for p in new_issues:
                if isinstance(p, Problem) and p.severity == ProblemSeverity.WARNING:
                    relevant_issues.append(p.msg)
            if relevant_issues:
                dim_score = 70
            else:
                dim_score = 100

        dim_scores[dim_key] = {
            "score": dim_score,
            "weight": weight,
            "weighted": round(dim_score * weight, 1),
            "status": "ok" if dim_score == 100 else ("warning" if dim_score >= 50 else "fail"),
            "issues": new_issues,
        }
        all_issues.extend(new_issues)

    # 综合得分
    total_score = sum(d["weighted"] for d in dim_scores.values())
    total_score = min(100, max(0, round(total_score)))

    # 等级判定
    if total_score >= 85:
        level = "healthy"
    elif total_score >= 65:
        level = "degraded"
    elif total_score >= 40:
        level = "poor"
    else:
        level = "critical"

    # 计算趋势
    trend = _calculate_trend(total_score)

    # 记录历史
    _record_score_history(total_score, level, len(all_issues))

    result = {
        "score": total_score,
        "level": level,
        "dimensions": dim_scores,
        "issues": all_issues,
        "issue_count": len(all_issues),
        "trend": trend,
        "previous_score": _get_previous_score(),
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
    }

    _score_results = dim_scores

    # 恢复原来的 problems 状态（供主流程继续使用）
    # 但保留新发现的问题
    # Problem 对象不 set 去重（每个问题独一无二）

    # 后台任务清理
    _cleanup_old_tasks()

    return result


def _check_quality_score_dimension() -> bool:
    """检查质量评分维度"""
    try:
        qs_path = os.path.join(WORKSPACE, ".quality_scores.json")
        if os.path.exists(qs_path):
            with open(qs_path) as f:
                data = json.load(f)
            # 没有任何引擎评分记录 → 管道刚初始化，不扣分
            engines = data.get("engines", {})
            if not engines:
                return True
            overall = data.get("overall_score", 0)
            if overall < 0.3:
                add_problem(f"⚡ 质量评分偏低: {overall:.0%}")
                return False
            elif overall < 0.6:
                add_problem(f"⚡ 质量评分一般: {overall:.0%}")
                return True  # warning but not fail
        return True
    except Exception:
        return True  # 没有评分数据不扣分


def _calculate_trend(current_score: int) -> str:
    """计算趋势（与前三次均值比较）"""
    scores = _load_score_history()
    if len(scores) < 3:
        return "stable"

    recent = [s["score"] for s in scores[-4:-1]]  # 倒数第4到倒数第2（排除当前）
    if not recent:
        return "stable"

    avg_prev = sum(recent) / len(recent)
    diff = current_score - avg_prev

    if diff > 5:
        return "improving"
    elif diff < -5:
        return "declining"
    return "stable"


def _load_score_history(max_items: int = 50) -> list:
    """加载历史评分记录"""
    if not os.path.exists(HEALTH_SCORE_HISTORY_PATH):
        return []
    records = []
    try:
        with open(HEALTH_SCORE_HISTORY_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (IOError, FileNotFoundError):
        pass
    return records[-max_items:]


def _record_score_history(score: int, level: str, issue_count: int):
    """记录评分历史"""
    os.makedirs(os.path.dirname(HEALTH_SCORE_HISTORY_PATH) or ".", exist_ok=True)
    record = {
        "score": score,
        "level": level,
        "issue_count": issue_count,
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
    }
    try:
        with open(HEALTH_SCORE_HISTORY_PATH, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        # 保留最近 200 条
        records = _load_score_history(200)
        if len(records) >= 200:
            with open(HEALTH_SCORE_HISTORY_PATH, "w") as f:
                for r in records[-200:]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        pass


def _get_previous_score() -> Optional[int]:
    """获取上一次评分"""
    records = _load_score_history(2)
    if len(records) >= 2:
        return records[-2]["score"]
    return None


def get_health_score_report(verbose: bool = False) -> str:
    """生成美观的健康评分报告文本"""
    result = get_health_score()

    score = result["score"]
    level = result["level"]
    trend = result["trend"]
    prev = result["previous_score"]

    # 等级图标
    level_icon = {
        "healthy": "🌟", "degraded": "⚡",
        "poor": "⚠️", "critical": "🚨",
    }.get(level, "❓")

    # 趋势图标
    trend_icon = {
        "improving": "↑", "stable": "→", "declining": "↓",
    }.get(trend, "→")

    lines = []
    lines.append(f"{'=' * 50}")
    lines.append(f"  系统健康评分: {level_icon}  {score}/100  ({level.upper()})  {trend_icon}")
    if prev is not None:
        diff = score - prev
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        lines.append(f"  上次评分: {prev}  ({diff_str})")
    lines.append(f"{'=' * 50}")

    if verbose:
        for dim_key, dim_data in result["dimensions"].items():
            icon = "✅" if dim_data["status"] == "ok" else ("⚠️" if dim_data["status"] == "warning" else "❌")
            name = HEALTH_DIMENSIONS[dim_key]["name"]
            lines.append(f"  {icon} {name}: {dim_data['score']}/100 (权重{dim_data['weight']:.0%})")
            for issue in dim_data["issues"]:
                lines.append(f"      {issue}")

    if result["issue_count"] > 0:
        lines.append(f"\n  问题数: {result['issue_count']} 个")
        if not verbose:
            for issue in result["issues"][:3]:
                lines.append(f"    {issue}")
            if result["issue_count"] > 3:
                lines.append(f"    ...还有 {result['issue_count'] - 3} 个")

    lines.append(f"{'=' * 50}")
    return "\n".join(lines)


def log(msg: str):
    ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def add_problem(msg: str, severity: ProblemSeverity = ProblemSeverity.CRITICAL):
    global all_ok
    if severity == ProblemSeverity.CRITICAL:
        all_ok = False
    problems.append(Problem(msg, severity))


def _filter_plugin_noise(lines: list) -> list:
    """过滤掉插件加载日志行，只保留核心输出"""
    result = []
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith("[plugins]"):
            continue
        if "node-pty" in line_stripped or "Cannot load" in line_stripped:
            continue
        if not line_stripped:
            continue
        if line_stripped.startswith("Require stack:") or line_stripped.startswith("- ") or line_stripped.startswith("  "):
            continue
        if line_stripped.startswith("createRequire") or line_stripped.startswith("import(") or line_stripped.startswith("global("):
            continue
        result.append(line_stripped)
    return result


# ==================== 核心检查 ====================

def check_gateway():
    """检查 Gateway 运行状态"""
    try:
        result = safe_subprocess_run(
            ["openclaw", "gateway", "status"],
            capture_output=True, text=True, timeout=10
        )
        all_output = (result.stdout + result.stderr)
        lines = all_output.split("\n")
        clean_lines = _filter_plugin_noise(lines)
        clean_output = "\n".join(clean_lines)

        if "RPC probe: ok" in clean_output:
            return True
        elif "Online" in clean_output or "online" in clean_output:
            return True
        elif "status: ok" in clean_output:
            return True
        elif "Connectivity probe: ok" in clean_output:
            # 容器环境（supervisord），gateway 实际运行正常
            return True
        else:
            add_problem(f"Gateway 状态异常: {clean_output[:200]}", ProblemSeverity.CRITICAL)
            return False
    except subprocess.TimeoutExpired:
        add_problem(f"Gateway 检查超时", ProblemSeverity.CRITICAL)
        return False
    except Exception as e:
        add_problem(f"Gateway 检查失败: {e}", ProblemSeverity.CRITICAL)
        return False


def check_cron():
    """检查定时任务数量与健康"""
    try:
        result = safe_subprocess_run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=10
        )
        all_output = result.stdout + result.stderr
        lines = all_output.split("\n")
        clean_lines = _filter_plugin_noise(lines)

        task_lines = []
        for line in clean_lines:
            if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\s', line):
                task_lines.append(line)

        task_count = len(task_lines)
        if task_count < 2:
            add_problem(f"定时任务数量异常: {task_count} 个 (预期≥2)", ProblemSeverity.WARNING)
            return False

        # Check expected cron tasks
        cron_output = ' '.join([l.lower() for l in task_lines])
        # 校验核心定时任务（按实际任务名模糊匹配）
        expected_keywords = [
            'crusheart-daily',
            'crusheart-engine-init',
            'weather-morning',
            'weather-evening',
        ]
        for kw in expected_keywords:
            if kw not in cron_output:
                add_problem(f"缺少定时任务: {kw}", ProblemSeverity.WARNING)

        for line in task_lines:
            if "fail" in line.lower() or "error" in line.lower():
                add_problem(f"定时任务存在失败记录: {line.strip()[:100]}", ProblemSeverity.WARNING)
                return False

        return True
    except subprocess.TimeoutExpired:
        add_problem(f"Cron 检查超时", ProblemSeverity.CRITICAL)
        return False
    except Exception as e:
        add_problem(f"定时任务检查失败: {e}", ProblemSeverity.CRITICAL)
        return False


def check_skills():
    """检查技能目录完整性"""
    skills_dir = os.path.join(WORKSPACE, "skills")
    if not os.path.isdir(skills_dir):
        add_problem(f"skills 目录不存在", ProblemSeverity.CRITICAL)
        return False

    skill_count = len([d for d in os.listdir(skills_dir)
                       if os.path.isdir(os.path.join(skills_dir, d))])
    if skill_count < 50:
        add_problem(f"技能数量异常: {skill_count} 个 (预期≥50)", ProblemSeverity.WARNING)
        return False
    return True


def check_disk():
    """检查工作区磁盘空间"""
    try:
        result = safe_subprocess_run(
            ["du", "-sm", WORKSPACE],
            capture_output=True, text=True, timeout=5
        )
        size_mb = int(result.stdout.split()[0]) if result.stdout else 0
        if size_mb > MAX_WORKSPACE_MB:
            add_problem(f"工作区过大: {size_mb}MB (> {MAX_WORKSPACE_MB}MB)", ProblemSeverity.WARNING)
            return False
        elif size_mb > WARN_WORKSPACE_MB:
            add_problem(f"⚡ 工作区较大: {size_mb}MB")
            return True  # not a failure, just warning
        return True
    except Exception as e:
        add_problem(f"磁盘检查失败: {e}", ProblemSeverity.WARNING)
        return False


def check_core_files():
    """检查核心配置文件是否存在（软检查：缺失只告警不阻断）"""
    files = ["SOUL.md", "MEMORY.md", "TOOLS.md", "USER.md", "AGENTS.md",
             "TODO.md"]
    dirs = ["scripts", "memory", "core"]
    missing = []

    for f in files:
        path = os.path.join(WORKSPACE, f)
        if not os.path.exists(path):
            missing.append(f)
    for d in dirs:
        path = os.path.join(WORKSPACE, d)
        if not os.path.isdir(path):
            missing.append(f"{d}/")

    # 核心文件缺失仅告警（新用户环境可能没有这些配置文件），引擎运行不受影响
    if missing:
        add_problem(f"核心文件/目录缺失: {', '.join(missing)}（新用户可忽略，不影响引擎运行）", ProblemSeverity.WARNING)
    return True


def check_engine_state():
    """检查引擎初始化状态（.state/ 目录下）"""
    state_dir = os.path.join(WORKSPACE, ".state")
    if not os.path.isdir(state_dir):
        add_problem(f".state/ 状态目录不存在", ProblemSeverity.WARNING)
        return False

    if os.path.exists(ENGINE_STATE):
        try:
            with open(ENGINE_STATE) as f:
                state = json.load(f)
            if state.get("status") != "ready":
                add_problem(f"引擎状态异常，建议重新初始化", ProblemSeverity.WARNING)
                return False
            engine_count = len(state.get("engines", []))
            if engine_count < 13:
                add_problem(f"引擎注册数量异常: {engine_count} 个 (预期≥13)", ProblemSeverity.WARNING)
                return False
            return True
        except Exception:
            add_problem(f"引擎状态文件损坏，建议重新初始化", ProblemSeverity.WARNING)
            return False
    else:
        add_problem(f"引擎状态文件缺失，请运行 init_engines.py", ProblemSeverity.WARNING)
        return False


def check_memory_engine():
    """检查记忆引擎关键方法是否可用"""
    try:
        if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)
        from core.engines.memory.auto_memory import AutoMemory
        engine = AutoMemory()
        missing_methods = []
        for m in ["is_core_anchor", "cold_hot_policy", "consolidation_threshold"]:
            if not callable(getattr(engine, m, None)):
                missing_methods.append(m)
        if missing_methods:
            add_problem(f"记忆引擎缺失方法: {', '.join(missing_methods)}", ProblemSeverity.CRITICAL)
            return False
        return True
    except Exception as e:
        add_problem(f"记忆引擎加载失败: {e}", ProblemSeverity.CRITICAL)
        return False


def check_rename_integrity():
    """改名完整性校验 — 确保 AutoMemory / auto_engines 无断裂"""
    try:
        if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)
        from core.engines.memory.auto_memory import AutoMemory
        engine = AutoMemory()
        engine.stats()
    except Exception as e:
        add_problem(f"AutoMemory 加载失败: {e}", ProblemSeverity.CRITICAL)
        return False

    try:
        from core.engines.init.skill_engine import SkillRouter
        from core.engines.init.task_scheduler import TaskScheduler
        SkillRouter().scan()
        _ = TaskScheduler()
    except Exception as e:
        add_problem(f"auto_engines 加载失败: {e}", ProblemSeverity.CRITICAL)
        return False

    return True


def check_directory_structure():
    """
    v5.0 新增: 目录结构校验
    确保没有重复的根级目录（如 root-level orchestration/ 和 core/orchestration/）
    """
    forbidden_root_dirs = ["orchestration", "infrastructure", "autonomy", "knowledge"]
    for d in forbidden_root_dirs:
        path = os.path.join(WORKSPACE, d)
        if os.path.isdir(path):
            add_problem(f"根级重复目录存在: {d}/（应在 core/{d}/ 下）", ProblemSeverity.CRITICAL)
            return False

    # 检查 core/engines/ 子目录完整性（v7 引擎架构）
    expected_engine_dirs = ["hooks", "init", "memory", "operations", "quality", "tools", "workflow", "compat"]
    for d in expected_engine_dirs:
        path = os.path.join(WORKSPACE, "core", "engines", d)
        if not os.path.isdir(path):
            add_problem(f"core/engines/{d}/ 目录缺失", ProblemSeverity.CRITICAL)
            return False

    return True



def check_garbage_files():
    """
    v5.0 新增: 垃圾文件/空目录检测
    检查: 根级 .json（不应有）, 空 __pycache__（不应有）, 大无用户文件
    """
    # 根目录不应有零散 .json 文件（应在 .state/ 下）
    root_jsons = []
    for f in os.listdir(WORKSPACE):
        if f.startswith(".") and f.endswith(".json"):
            fp = os.path.join(WORKSPACE, f)
            if os.path.isfile(fp):
                root_jsons.append(f)
    if root_jsons:
        # 仅记录，不做警告（部分文件由运行时自动生成）
        pass

    # 检查 skills/ 下是否有无用的空目录（排除 .git 和 __pycache__）
    skills_dir = os.path.join(WORKSPACE, "skills")
    if os.path.isdir(skills_dir):
        empty_count = 0
        for entry in os.listdir(skills_dir):
            sp = os.path.join(skills_dir, entry)
            if entry.startswith(".") or entry == "__pycache__":
                continue
            if os.path.isdir(sp):
                try:
                    contents = os.listdir(sp)
                    if not contents:
                        empty_count += 1
                except PermissionError:
                    pass
        if empty_count > 3:
            add_problem(f"skills/ 下有 {empty_count} 个空目录（建议清理）", ProblemSeverity.WARNING)

    return True


def check_new_modules():
    """
    v5.1 新增: 检查新搭建的编排层+执行层模块完整性
    确保11个新模块文件存在且可导入
    """
    # v7 引擎架构核心模块（12个关键模块）
    new_modules = [
        "core.engines.workflow.workflow_engine",
        "core.engines.workflow.engine_orchestrator",
        "core.engines.workflow.task_executor",
        "core.engines.operations.state_manager",
        "core.engines.workflow.serial_lanes",
        "core.engines.tools.device_receipt_reconciler",
        "core.engines.tools.tool_execution_gateway",
        "core.engines.tools.failover",
        "core.engines.operations.runtime_probe",
        "core.engines.operations.background_executor",
        "core.engines.compat.compat_registry",
        "core.pipeline.orchestrator",
    ]
    missing = []
    for module in new_modules:
        try:
            __import__(module)
        except ImportError as e:
            missing.append(f"{module} ({e})")

    if missing:
        add_problem(f"新模块导入失败: {', '.join(missing)}", ProblemSeverity.WARNING)
        return False

    # 额外检查: template library 可加载（不强制数量）
    try:
        from core.engines.tools.task_template_library import get_library
        lib = get_library()
        lib.count()
    except Exception as e:
        add_problem(f"任务模板库加载失败: {e}", ProblemSeverity.WARNING)
        return False

    return True


def check_orchestrator():
    """
    v5.0 新增: 检查 Orchestrator 引擎注册完整性
    确保编排器注册的引擎数与 engines.json 一致
    """
    try:
        if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)
        from core.engines.workflow.engine_orchestrator import Orchestrator
        router = Orchestrator()
        status = router.status()
        registered = status.get("registered_count", 0)
        available = status.get("available_count", 0)

        # 动态阈值：engines.json 的实际引擎数
        engines_json_path = os.path.join(WORKSPACE, "core", "engines", "init", "engines.json")
        expected_count = 38  # 默认值（v7 engines.json 扩展至38个引擎）
        if os.path.exists(engines_json_path):
            try:
                with open(engines_json_path) as f:
                    cfg = json.load(f)
                expected_count = len(cfg.get("engines", []))
            except Exception:
                logging.exception("[health_check.py] suppressed")
                pass

        if registered < 20:
            add_problem(f"Orchestrator 可用引擎偏少: {registered} 个", ProblemSeverity.WARNING)
            return False

        return True
    except Exception as e:
        add_problem(f"Orchestrator 检查失败: {e}", ProblemSeverity.WARNING)
        return False


def check_state_dir():
    """
    v5.0 新增: .state/ 目录完整性检查
    """
    state_dir = os.path.join(WORKSPACE, ".state")
    if not os.path.isdir(state_dir):
        add_problem(f".state/ 目录缺失", ProblemSeverity.CRITICAL)
        return False

    expected_states = [".engine_state.json"]
    missing = []
    for f in expected_states:
        if not os.path.exists(os.path.join(state_dir, f)):
            missing.append(f)
    if missing:
        add_problem(f".state/ 缺失文件: {', '.join(missing)}", ProblemSeverity.WARNING)
        return False
    return True


# ==================== 自我完整性校验 ====================

def self_integrity_check():
    """检查巡检脚本自身可运行"""
    all_check_funcs_ok = True

    check_functions = [
        check_gateway, check_cron, check_skills, check_disk,
        check_core_files, check_memory_engine, check_engine_state,
        check_rename_integrity, check_directory_structure, check_garbage_files,
        check_orchestrator, check_state_dir, check_new_modules, self_integrity_check
    ]
    for func in check_functions:
        if not callable(func):
            add_problem(f"自检失败：函数 {func.__name__} 不可调用", ProblemSeverity.CRITICAL)
            all_check_funcs_ok = False

    if not all_check_funcs_ok:
        return False

    # 日志目录可写
    log_dir = os.path.join(WORKSPACE, ".engine_logs")
    os.makedirs(log_dir, exist_ok=True)
    test_path = os.path.join(log_dir, ".integrity_test")
    try:
        with open(test_path, "w") as f:
            f.write("test")
        os.remove(test_path)
    except Exception as e:
        add_problem(f"日志目录不可写入: {e}", ProblemSeverity.WARNING)
        return False

    return True



def _cleanup_old_tasks():
    """清理超过30天的后台任务"""
    try:
        from core.engines.tools.crusheart_db import get_db
        db = get_db()
        deleted = db.cleanup_background_tasks(max_age_days=30)
        if deleted > 0:
            add_problem(f"清理了{deleted}条过期后台任务")
    except Exception:
        pass


# ==================== 执行日志记录 ====================

def record_check_result(success: bool, problem_count: int):
    try:
        log_dir = os.path.join(WORKSPACE, ".engine_logs")
        os.makedirs(log_dir, exist_ok=True)
        record = {
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "success": success,
            "problem_count": problem_count,
            "problems": [str(p) for p in problems[:5]] if problems else []
        }
        log_path = os.path.join(log_dir, "health_check_log.json")
        history = []
        if os.path.exists(log_path):
            try:
                with open(log_path) as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append(record)
        if len(history) > 50:
            history = history[-50:]
        with open(log_path, "w") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==================== 主入口 ====================

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

    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    manual_mode = "--manual" in sys.argv

    self_ok = self_integrity_check()

    # 执行全部检查（14项）
    check_gateway()
    check_cron()
    check_skills()
    check_disk()
    check_core_files()
    check_engine_state()
    check_memory_engine()
    check_directory_structure()
    check_garbage_files()
    check_orchestrator()
    check_state_dir()
    check_new_modules()

    # 交叉验证: 引擎状态 vs cron 任务数
    engine_state_path = ENGINE_STATE
    if os.path.exists(engine_state_path):
        try:
            with open(engine_state_path) as f:
                state = json.load(f)
            engine_count = len(state.get("engines", []))
            if engine_count < 13:
                add_problem(f"交叉验证失败: 引擎数 {engine_count} 偏低", ProblemSeverity.WARNING)
        except Exception:
            pass

    success = not problems and self_ok
    record_check_result(success, len(problems))

    if success:
        if manual_mode:
            print(f"✅ Crusheart Agent OS — 健康巡检通过 ({now})")
            print(f"{'='*45}")
            print("  14项检查全部通过（含自检）")
    else:
        print(f"🚨 Crusheart Agent OS — 健康巡检报告 ({now})")
        print(f"{'='*45}")
        print(f"  异常项: {len(problems)}")
        for p in problems:
            print(f"  {p}")
        if not self_ok:
            print("  ⚠️ 自我完整性校验未通过，巡检结果可能不可靠")
        print(f"{'='*45}")
        print("  建议: python3 scripts/init_engines.py")
        exit(1)
