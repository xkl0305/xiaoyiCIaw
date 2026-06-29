"""
Crusheart Agent OS — Insights Engine v2.0
Token/成本/工具/活跃度洞察。
从 exec_logger 的 JSONL 数据读取统计信息，生成使用报告。

v7.0: 重写为可读代码，注册为引擎，接入 exec_logger 数据流。
"""

import json, os, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

# Default pricing (per 1K tokens)
_PRICING = {
    "gpt-4o": {"i": 0.0025, "o": 0.01},
    "gpt-4o-mini": {"i": 0.00015, "o": 0.0006},
    "claude-3-haiku": {"i": 0.00025, "o": 0.00125},
    "deepseek-chat": {"i": 0.00014, "o": 0.00028},
    "qwen-plus": {"i": 0.00015, "o": 0.0006},
}


class InsightsEngine:
    """Usage insights engine — reads exec_logger JSONL and generates reports."""

    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(WORKSPACE, ".logs")
        self._log_dir = log_dir
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_file = os.path.join(self._log_dir, "exec_log.jsonl")

    def generate_report(self, days=30):
        """Generate a full usage report for the last N days."""
        cutoff = time.time() - days * 86400
        sessions = self._load_sessions(cutoff)
        if not sessions:
            return {"days": days, "empty": True}

        overview = self._overview(sessions)
        model_breakdown = self._model_breakdown(sessions)
        daily_activity = self._daily_activity(sessions)
        top_tokens = self._top_token_consumers(sessions)

        return {
            "days": days,
            "empty": False,
            "generated_at": datetime.now(BJ).isoformat(),
            "overview": overview,
            "model_breakdown": model_breakdown,
            "daily_activity": daily_activity,
            "top_consumers": top_tokens,
        }

    def _load_sessions(self, cutoff):
        """Load exec_log.jsonl entries newer than cutoff."""
        if not os.path.exists(self._log_file):
            return []
        sessions = []
        with open(self._log_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("ts", 0) or entry.get("timestamp", 0)
                    if ts and isinstance(ts, (int, float)) and ts >= cutoff:
                        sessions.append(entry)
                except json.JSONDecodeError:
                    continue
        return sessions

    def _overview(self, sessions):
        """Compute overview stats."""
        total_input = sum(
            s.get("input_tokens", 0) or s.get("prompt_tokens", 0) for s in sessions
        )
        total_output = sum(
            s.get("output_tokens", 0) or s.get("completion_tokens", 0) for s in sessions
        )
        total_cost = sum(
            self._estimate_cost(
                s.get("model", ""),
                s.get("input_tokens", 0) or s.get("prompt_tokens", 0),
                s.get("output_tokens", 0) or s.get("completion_tokens", 0),
            )
            for s in sessions
        )
        tool_counter = Counter()
        for s in sessions:
            tool = s.get("tool_name", "") or s.get("tool", "")
            if tool:
                tool_counter[tool] += 1

        return {
            "sessions": len(sessions),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(total_cost, 4),
            "model_count": len(set(s.get("model", "") for s in sessions if s.get("model"))),
            "top_tools": tool_counter.most_common(10),
        }

    def _estimate_cost(self, model, input_tok, output_tok):
        """Estimate cost for a single call."""
        pricing = _PRICING.get(model)
        if not pricing:
            return 0.0
        return round((input_tok / 1000) * pricing["i"] + (output_tok / 1000) * pricing["o"], 4)

    def _model_breakdown(self, sessions):
        """Break down usage by model."""
        models = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        for s in sessions:
            model = s.get("model", "?")
            inp = s.get("input_tokens", 0) or s.get("prompt_tokens", 0)
            out = s.get("output_tokens", 0) or s.get("completion_tokens", 0)
            models[model]["calls"] += 1
            models[model]["input_tokens"] += inp
            models[model]["output_tokens"] += out
            models[model]["cost"] += self._estimate_cost(model, inp, out)

        return [
            {"model": m, **d, "cost": round(d["cost"], 4)}
            for m, d in sorted(models.items(), key=lambda x: x[1]["calls"], reverse=True)
        ]

    def _daily_activity(self, sessions):
        """Group activity by day."""
        daily = Counter()
        for s in sessions:
            ts = s.get("ts", 0) or s.get("timestamp", 0)
            if ts:
                daily[datetime.fromtimestamp(ts, tz=BJ).strftime("%m-%d")] += 1
        max_count = max(daily.values()) if daily else 1
        return [
            {"date": d, "count": c, "bar": "█" * max(1, int(c / max_count * 20))}
            for d, c in sorted(daily.items())
        ]

    def _top_token_consumers(self, sessions):
        """Top 10 token-consuming sessions."""
        sorted_sessions = sorted(
            sessions,
            key=lambda s: (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0),
            reverse=True,
        )[:10]
        result = []
        for s in sorted_sessions:
            ts = s.get("ts", 0) or s.get("timestamp", 0)
            result.append({
                "time": datetime.fromtimestamp(ts, tz=BJ).strftime("%m-%d %H:%M") if ts else "",
                "model": s.get("model", ""),
                "tool": s.get("tool_name", "") or s.get("tool", ""),
                "tokens": (s.get("input_tokens", 0) or 0) + (s.get("output_tokens", 0) or 0),
            })
        return result

    def summary(self) -> dict:
        """Quick summary for dashboard display."""
        report = self.generate_report(1)
        if report.get("empty"):
            return {"status": "no_data"}
        ov = report["overview"]
        return {
            "status": "ready",
            "sessions_today": ov["sessions"],
            "tokens_today": ov["total_tokens"],
            "cost_today": ov["estimated_cost_usd"],
            "active_models": ov["model_count"],
        }



    # ── 用户行为分析（design 三 from 6/5） ──

    def analyze_usage_pattern(self, user_id: str = "", hours: int = 24) -> dict:
        """分析用户使用模式"""
        try:
            from core.engines.memory.exec_logger import get_usage_pattern
            return get_usage_pattern(user_id, hours)
        except Exception:
            return {"status": "error", "note": "exec_logger not available"}

    def analyze_skill_usage(self, user_id: str = "", hours: int = 168) -> dict:
        """分析技能使用统计"""
        try:
            from core.engines.memory.exec_logger import get_skill_usage_stats
            return get_skill_usage_stats(user_id, hours)
        except Exception:
            return {"status": "error", "note": "exec_logger not available"}

    def detect_habit_changes(self, user_id: str = "", days: int = 7) -> dict:
        """检测用户习惯变化"""
        try:
            from core.engines.memory.exec_logger import get_habit_insights
            return get_habit_insights(user_id, days)
        except Exception:
            return {"status": "error", "note": "exec_logger not available"}

    def detect_efficiency_pattern(self, user_id: str = "", hours: int = 168) -> dict:
        """分析效率模式"""
        try:
            from core.engines.memory.exec_logger import get_efficiency_pattern
            return get_efficiency_pattern(user_id, hours)
        except Exception:
            return {"status": "error", "note": "exec_logger not available"}

# ── Engine init (#45: 统一单例注册表) ──

def init() -> InsightsEngine:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(InsightsEngine)

def get_insights() -> InsightsEngine:
    return init()

def run():
    """CLI entry: print report to stdout."""
    engine = init()
    report = engine.generate_report(30)
    if report.get("empty"):
        print("📊 无会话数据")
        return
    ov = report["overview"]
    print("📊 使用洞察报告")
    print("=" * 40)
    print(f"  会话数: {ov['sessions']}")
    print(f"  总 Token: {ov['total_tokens']:,} (输入 {ov['input_tokens']:,} / 输出 {ov['output_tokens']:,})")
    print(f"  估算成本: ${ov['estimated_cost_usd']:.4f}")
    print(f"  模型数: {ov['model_count']}")
    if ov.get("top_tools"):
        print("\n🔧 高频工具:")
        for tool, count in ov["top_tools"][:5]:
            print(f"  {tool}: {count}次")
    if report.get("model_breakdown"):
        print("\n🤖 模型使用:")
        for m in report["model_breakdown"][:5]:
            print(f"  {m['model']}: {m['calls']}次 ({m['input_tokens']:,}/{m['output_tokens']:,} tok, ${m['cost']:.4f})")
    if report.get("daily_activity"):
        print("\n📅 活跃度:")
        for d in report["daily_activity"][-14:]:
            print(f"  {d['date']} {d['bar']} {d['count']}次")



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

    run()
