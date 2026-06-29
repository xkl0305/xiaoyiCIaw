"""
Crusheart Agent OS — Trace Timeline + Stage Profiler v1.0
跟踪：每个 pipeline 阶段耗时、引擎决策、路由路径
写入：JSONL 文件，供后续回溯和趋势分析
"""

import os, json, time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
TRACE_DIR = os.path.join(WORKSPACE, ".trace")
TRACE_FILE = os.path.join(TRACE_DIR, "pipeline_timeline.jsonl")

class TraceTimeline:
    """轻量级 pipeline 执行追踪器"""

    def __init__(self):
        os.makedirs(TRACE_DIR, exist_ok=True)
        self._stages: Dict[str, float] = {}
        self._trace_events: List[dict] = []

    def enter(self, stage: str, detail: str = ""):
        """进入某个阶段"""
        now = time.monotonic()
        self._stages[stage] = now
        self._trace_events.append({
            "event": "enter",
            "stage": stage,
            "detail": detail,
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "monotonic_s": now,
        })

    def exit(self, stage: str, result_info: str = ""):
        """离开某个阶段，返回该阶段耗时（ms）"""
        now = time.monotonic()
        start = self._stages.pop(stage, None)
        duration_ms = int((now - start) * 1000) if start else 0
        self._trace_events.append({
            "event": "exit",
            "stage": stage,
            "duration_ms": duration_ms,
            "result": result_info,
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "monotonic_s": now,
        })
        return duration_ms

    def snapshot(self) -> dict:
        """生成当前各阶段耗时快照（用于写入 result）"""
        return {
            e["event"]: {
                "stage": e["stage"],
                "duration_ms": e.get("duration_ms", 0),
                "detail": e.get("detail", e.get("result", "")),
            }
            for e in self._trace_events
        }

    def flush(self, pipeline_result: dict):
        """将本次追踪写入 JSONL"""
        trace = {
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "message_preview": pipeline_result.get("message_preview", "")[:60],
            "final_mode": pipeline_result.get("final_decision", {}).get("mode", "unknown"),
            "trace_events": self._trace_events,
        }
        # 从 profile 累加总耗时
        profile = pipeline_result.get("_profile", {})
        total_ms = sum(v for v in profile.values() if isinstance(v, (int, float)))
        trace["total_ms"] = total_ms
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    def summary(self) -> str:
        """可读摘要"""
        lines = ["📊 Pipeline Trace:"]
        for e in self._trace_events:
            if e["event"] == "exit":
                icon = "✅" if e.get("duration_ms", 0) < 100 else "⚠️" if e.get("duration_ms", 0) < 500 else "🐌"
                lines.append(f"  {icon} {e['stage']}: {e['duration_ms']}ms ({e.get('result','')})")
        return "\n".join(lines)

def get_recent_traces(limit: int = 10) -> List[dict]:
    """获取最近 N 条 trace 记录"""
    if not os.path.exists(TRACE_FILE):
        return []
    traces = []
    with open(TRACE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))
    return traces[-limit:]

# ── Engine init ──

def init() -> TraceTimeline:
    global _instance
    if _instance is None:
        _instance = TraceTimeline()
    return _instance

def get_trace() -> TraceTimeline:
    return init()

def slow_stage_report(threshold_ms: int = 500, limit: int = 50) -> List[dict]:
    """找出耗时超过阈值的阶段，用于性能分析"""
    if not os.path.exists(TRACE_FILE):
        return []
    slow = []
    with open(TRACE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                trace = json.loads(line)
                for e in trace.get("trace_events", []):
                    if e.get("event") == "exit" and e.get("duration_ms", 0) >= threshold_ms:
                        slow.append({
                            "stage": e["stage"],
                            "duration_ms": e["duration_ms"],
                            "message": trace.get("message_preview", ""),
                            "ts": trace.get("ts", ""),
                        })
            except (json.JSONDecodeError, KeyError):
                continue
    return slow[-limit:]
