"""
Crusheart Agent OS — 统一执行日志与审计系统
功能：
  1. 记录每次工具调用/决策的详细信息
  2. 按维度查询和过滤
  3. 生成审计报告和趋势分析
  4. 决策溯源（"为什么系统会这样做"）
"""

import os
import json
import time
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from collections import Counter, defaultdict

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
LOG_DIR = os.path.join(WORKSPACE, ".engine_logs")
os.makedirs(LOG_DIR, exist_ok=True)

EXEC_LOG = os.path.join(LOG_DIR, "exec_log.jsonl")       # 工具调用日志
DECISION_LOG = os.path.join(LOG_DIR, "decision_log.jsonl") # 决策日志
AUDIT_LOG = os.path.join(LOG_DIR, "security_audit.jsonl")   # 安全审计日志（只追加，不可篡改）


# ═══════════════════════════════════════════════════════
# 1. 工具调用日志
# ═══════════════════════════════════════════════════════

def log_execution(
    tool_name: str,
    status: str,
    duration_ms: int,
    result_summary: str = "",
    params_summary: str = "",
    error: str = "",
    session_id: str = "",
):
    """
    记录一次工具调用

    Args:
        tool_name: 工具名称
        status: success | fail | timeout | blocked
        duration_ms: 耗时(毫秒)
        result_summary: 结果长度/摘要
        params_summary: 参数摘要(脱敏)
        error: 错误信息
        session_id: 会话ID（可选）
    """
    # 确保 status 是字符串（防御传入 dict 等情况）
    if not isinstance(status, str):
        try:
            status = json.dumps(status, ensure_ascii=False)[:100]
        except Exception:
            status = str(status)[:100]

    record = {
        "type": "execution",
        "ts": datetime.now(BEIJING_TZ).isoformat(),
        "ts_unix": int(time.time()),
        "tool": tool_name,
        "status": status,
        "duration_ms": duration_ms,
        "result_summary": result_summary[:200],
        "params": params_summary[:100],
        "error": error[:200],
        "session_id": session_id,
    }
    with open(EXEC_LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_decision(
    decision: str,
    options: List[str],
    chosen: str,
    reasoning: str,
    context: str = "",
):
    """
    记录一次决策过程（决策溯源）

    Args:
        decision: 决策类型（如 skill_selection / chain_choice / model_selection）
        options: 备选方案列表
        chosen: 最终选择
        reasoning: 选择理由
        context: 决策背景
    """
    record = {
        "type": "decision",
        "ts": datetime.now(BEIJING_TZ).isoformat(),
        "ts_unix": int(time.time()),
        "decision": decision,
        "options": options[:5],       # 最多记5个备选
        "chosen": chosen,
        "reasoning": reasoning[:300],
        "context": context[:200],
    }
    with open(DECISION_LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_security_event(
    action: str,
    resource: str,
    status: str,
    detail: str = "",
    user_initiated: bool = True,
):
    """
    记录安全审计事件（只追加，不可修改/删除）

    Args:
        action: 操作类型（如 delete / modify / system_update / config_change）
        resource: 操作对象路径或标识
        status: 状态（success / blocked / failed）
        detail: 额外细节
        user_initiated: 是否由用户触发
    """
    record = {
        "type": "security_audit",
        "ts": datetime.now(BEIJING_TZ).isoformat(),
        "ts_unix": int(time.time()),
        "action": action,
        "resource": resource[:200],
        "status": status,
        "detail": detail[:300],
        "user_initiated": user_initiated,
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


# ═══════════════════════════════════════════════════════
# 2. 查询
# ═══════════════════════════════════════════════════════

def _read_jsonl(path: str) -> List[Dict]:
    """读取 JSONL 文件"""
    if not os.path.exists(path):
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def query_executions(
    limit: int = 50,
    tool: str = "",
    status: str = "",
    since_hours: int = 0,
    keyword: str = "",
) -> List[Dict]:
    """
    查询执行日志，支持多维度过滤

    Args:
        limit: 返回条数上限
        tool: 按工具名过滤（支持模糊匹配）
        status: 按状态过滤（success/fail/timeout/blocked）
        since_hours: 最近几小时内的记录（0=全部）
        keyword: 按关键词过滤摘要内容

    Returns:
        匹配的记录列表
    """
    records = _read_jsonl(EXEC_LOG)
    if since_hours > 0:
        cutoff = time.time() - since_hours * 3600
        records = [r for r in records if r.get("ts_unix", 0) > cutoff]
    if tool:
        records = [r for r in records if tool.lower() in r.get("tool", "").lower()]
    if status:
        records = [r for r in records if r.get("status") == status]
    if keyword:
        keyword_lower = keyword.lower()
        records = [
            r for r in records
            if keyword_lower in r.get("result_summary", "").lower()
            or keyword_lower in r.get("params", "").lower()
            or keyword_lower in r.get("tool", "").lower()
        ]
    return records[-limit:]


def query_decisions(
    limit: int = 50,
    decision_type: str = "",
    since_hours: int = 0,
) -> List[Dict]:
    """
    查询决策日志

    Args:
        limit: 返回条数上限
        decision_type: 按决策类型过滤
        since_hours: 最近几小时

    Returns:
        决策记录列表
    """
    records = _read_jsonl(DECISION_LOG)
    if since_hours > 0:
        cutoff = time.time() - since_hours * 3600
        records = [r for r in records if r.get("ts_unix", 0) > cutoff]
    if decision_type:
        records = [r for r in records if r.get("decision") == decision_type]
    return records[-limit:]


def why(decision: str = "", context: str = "", recent_minutes: int = 30) -> str:
    """
    决策溯源解释器（"为什么系统会这样做"）

    Args:
        decision: 可选，指定决策类型
        context: 可选，指定上下文关键词
        recent_minutes: 回溯最近多少分钟

    Returns:
        自然语言的解释文本
    """
    cutoff = time.time() - recent_minutes * 60
    decisions = _read_jsonl(DECISION_LOG)
    executions = _read_jsonl(EXEC_LOG)

    # 过滤最近的决策
    recent_decisions = [
        d for d in decisions
        if d.get("ts_unix", 0) > cutoff
        and (not decision or d.get("decision") == decision)
        and (not context or context.lower() in d.get("context", "").lower() or context.lower() in d.get("reasoning", "").lower())
    ]

    if not recent_decisions:
        # 回退到执行日志找最近的
        recent_execs = [e for e in executions if e.get("ts_unix", 0) > cutoff][-5:]
        if not recent_execs:
            return "最近没有找到相关的执行记录或决策记录。"

        parts = ["最近系统执行的操作："]
        for e in recent_execs:
            status_icon = "✅" if e.get("status") == "success" else "❌"
            parts.append(f"  {status_icon} {e.get('tool', '?')} ({e.get('status', '?')}, {e.get('duration_ms', 0)}ms) — {e.get('result_summary', '')[:60]}")
        return "\n".join(parts)

    # 生成解释
    parts = [f"关于「{decision or context or '最近操作'}」的决策溯源："]
    for d in recent_decisions[-3:]:  # 最多展示3条
        parts.append(f"\n📌 决策类型: {d.get('decision', '?')}")
        parts.append(f"  选择: {d.get('chosen', '?')}")
        parts.append(f"  理由: {d.get('reasoning', '?')}")
        if d.get("options"):
            options_str = " | ".join(d["options"][:3])
            parts.append(f"  备选: {options_str}")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════
# 3. 统计与审计报告
# ═══════════════════════════════════════════════════════

def get_stats(hours: int = 24) -> Dict:
    """获取指定时间范围内的执行统计"""
    records = query_executions(limit=100000, since_hours=hours)
    if not records:
        return {
            "total": 0, "success": 0, "fail": 0,
            "success_rate": 0, "avg_duration_ms": 0,
            "by_tool": {}, "period_hours": hours
        }

    total = len(records)
    success = sum(1 for r in records if r["status"] == "success")
    fail = total - success
    avg_duration = sum(r.get("duration_ms", 0) for r in records) / total if total > 0 else 0

    by_tool = {}
    for r in records:
        tool = r["tool"]
        if tool not in by_tool:
            by_tool[tool] = {"count": 0, "success": 0, "fail": 0, "total_duration": 0, "timeouts": 0}
        # status 非字符串时归入 fail（防御旧数据/异常输入）
        status = r["status"]
        if not isinstance(status, str):
            status = "fail"
        by_tool[tool]["count"] += 1
        by_tool[tool][status] = by_tool[tool].get(status, 0) + 1
        by_tool[tool]["total_duration"] += r.get("duration_ms", 0)

    return {
        "total": total,
        "success": success,
        "fail": fail,
        "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        "avg_duration_ms": round(avg_duration, 0),
        "by_tool": by_tool,
        "period_hours": hours,
    }


def generate_audit_report(hours: int = 24) -> str:
    """生成人类可读的审计报告"""
    stats = get_stats(hours)
    decisions = query_decisions(limit=20, since_hours=hours)
    failures = query_executions(limit=50, status="fail", since_hours=hours)

    lines = [
        f"📊 审计报告 — 最近{hours}小时",
        f"  生成时间: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"  总调用: {stats['total']} 次",
        f"  成功率: {stats['success']} / {stats['total']} ({stats['success_rate']}%)",
        f"  平均耗时: {stats['avg_duration_ms']}ms",
        "",
        "  --- 按工具统计 ---",
    ]

    for tool, data in sorted(stats.get("by_tool", {}).items(), key=lambda x: x[1]["count"], reverse=True):
        avg_ms = data["total_duration"] / data["count"] if data["count"] > 0 else 0
        fail_count = data.get("fail", 0) + data.get("timeout", 0)
        lines.append(f"    {tool}: {data['count']}次, ✅{data['success']}, ❌{fail_count}, ⏱{avg_ms:.0f}ms")

    if failures:
        lines.extend(["", "  --- 最近失败记录 ---"])
        for f in failures[-5:]:
            lines.append(f"    ❌ {f.get('tool', '?')} — {f.get('error', '无错误信息')[:80]}")

    if decisions:
        lines.extend(["", "  --- 最近决策记录 ---"])
        for d in decisions[-5:]:
            lines.append(f"    📌 {d.get('decision', '?')}: 选择 {d.get('chosen', '?')} — {d.get('reasoning', '')[:60]}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# 4. CLI 入口
# ═══════════════════════════════════════════════════════

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

    import sys

    if len(sys.argv) < 2:
        print("用法: python3 exec_logger.py <stats|report|why|query|decisions> [参数...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        s = get_stats(hours)
        print(f"📊 统计 (最近{hours}h):")
        print(f"   总调用: {s['total']}")
        print(f"   成功率: {s['success_rate']}%")
        print(f"   平均耗时: {s['avg_duration_ms']}ms")
        print(f"\n   按工具统计:")
        for tool, data in sorted(s.get("by_tool", {}).items(), key=lambda x: x[1]["count"], reverse=True):
            avg_ms = data["total_duration"] / data["count"] if data["count"] > 0 else 0
            print(f"      {tool}: {data['count']}次, 成功={data['success']}, 平均{avg_ms:.0f}ms")

    elif cmd == "report":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        print(generate_audit_report(hours))

    elif cmd == "why":
        decision = sys.argv[2] if len(sys.argv) > 2 else ""
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        minutes = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        print(why(decision, context, minutes))

    elif cmd == "query":
        kwargs = {}
        if len(sys.argv) > 2:
            kwargs["tool"] = sys.argv[2]
        if len(sys.argv) > 3:
            kwargs["status"] = sys.argv[3]
        if len(sys.argv) > 4:
            kwargs["since_hours"] = int(sys.argv[4])
        if len(sys.argv) > 5:
            kwargs["keyword"] = sys.argv[5]
        kwargs["limit"] = 20
        results = query_executions(**kwargs)
        print(f"找到 {len(results)} 条记录:")
        for r in results[-5:]:
            print(f"  {r.get('ts', '')[:19]} | {r.get('tool', '?'):20s} | {r.get('status', '?'):8s} | {r.get('duration_ms', 0):>5}ms | {r.get('result_summary', '')[:40]}")

    elif cmd == "decisions":
        d_type = sys.argv[2] if len(sys.argv) > 2 else ""
        hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        results = query_decisions(limit=20, decision_type=d_type, since_hours=hours)
        print(f"找到 {len(results)} 条决策记录:")
        for r in results[-5:]:
            print(f"  {r.get('ts', '')[:19]} | {r.get('decision', '?'):20s} → {r.get('chosen', '?')} | {r.get('reasoning', '')[:80]}")

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


# ── 用户活动分析（design 三 from 6/5） ──

_USER_ACTIVITY_LOG = os.path.join(WORKSPACE, ".engine_logs", "user_activity.jsonl")

def log_user_activity(user_id: str, activity_type: str, metadata: dict = None) -> str:
    """记录用户活动事件到 JSONL"""
    import uuid
    entry = {
        "id": str(uuid.uuid4())[:8],
        "ts": datetime.now(BEIJING_TZ).isoformat(),
        "user_id": user_id,
        "type": activity_type,
        "metadata": metadata or {},
    }
    os.makedirs(os.path.dirname(_USER_ACTIVITY_LOG), exist_ok=True)
    with open(_USER_ACTIVITY_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["id"]

def get_usage_pattern(user_id: str = "", hours: int = 24) -> dict:
    """分析用户在指定时段内的使用模式"""
    if not os.path.exists(_USER_ACTIVITY_LOG):
        return {"status": "no_data"}
    activities = []
    cutoff = (datetime.now(BEIJING_TZ) - timedelta(hours=hours)).isoformat()
    with open(_USER_ACTIVITY_LOG) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("ts", "") >= cutoff:
                    if not user_id or entry.get("user_id") == user_id:
                        activities.append(entry)
            except Exception:
                continue
    if not activities:
        return {"status": "no_activity", "hours": hours}
    from collections import Counter
    type_dist = Counter(a.get("type", "unknown") for a in activities)
    hourly_buckets = Counter()
    for a in activities:
        try:
            h = int(a.get("ts", "")[11:13])
            hourly_buckets[h] += 1
        except Exception:
            pass
    return {
        "status": "ok",
        "total_activities": len(activities),
        "hours_analyzed": hours,
        "type_distribution": dict(type_dist),
        "peak_hours": [h for h, _ in hourly_buckets.most_common(3)],
        "avg_per_hour": round(len(activities) / max(hours, 1), 1),
    }

def get_skill_usage_stats(user_id: str = "", hours: int = 168) -> dict:
    """分析技能使用统计（默认7天）"""
    pattern = get_usage_pattern(user_id, hours)
    if pattern.get("status") != "ok":
        return pattern
    return pattern

def get_habit_insights(user_id: str = "", days: int = 7) -> dict:
    """分析用户行为习惯变化"""
    current = get_usage_pattern(user_id, hours=days * 24)
    previous = get_usage_pattern(user_id, hours=days * 24 * 2)
    if current.get("status") != "ok":
        return {"status": "no_data"}
    change = 0
    if previous.get("status") == "ok" and previous.get("total_activities", 0) > 0:
        curr_rate = current.get("total_activities", 0) / max(days, 1)
        prev_rate = previous.get("total_activities", 0) / max(days * 2, 1)
        if prev_rate > 0:
            change = round((curr_rate - prev_rate) / prev_rate * 100, 1)
    return {
        "status": "ok",
        "period_days": days,
        "total_current": current.get("total_activities", 0),
        "activity_change_pct": change,
        "trend": "up" if change > 10 else ("down" if change < -10 else "stable"),
        "peak_hours": current.get("peak_hours", []),
    }

def get_efficiency_pattern(user_id: str = "", hours: int = 168) -> dict:
    """分析效率模式：响应时间分布"""
    if not os.path.exists(_USER_ACTIVITY_LOG):
        return {"status": "no_data"}
    activities = []
    cutoff = (datetime.now(BEIJING_TZ) - timedelta(hours=hours)).isoformat()
    with open(_USER_ACTIVITY_LOG) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("ts", "") >= cutoff:
                    if not user_id or entry.get("user_id") == user_id:
                        activities.append(entry)
            except Exception:
                continue
    if not activities:
        return {"status": "no_activity"}
    return {
        "status": "ok",
        "total_activities": len(activities),
        "hours_analyzed": hours,
    }
