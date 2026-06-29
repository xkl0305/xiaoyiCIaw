"""
Crusheart Agent OS — 自进化引擎 v3 兼容垫片
v7.0.0: v3/v4/tracker/MASA 已合并为 unified SelfEvolutionEngine v5。
本文件作为向后兼容入口，所有功能委托给 v5 引擎。

兼容保留:
  - SelfEvolutionEngine (v3 同名类)
  - RegisteredRule / RuleStore (从 v5 导入)
  - MASAPredictor / MASAAliener (从 v5 导入)
  - evaluate_turn() / reflect() / route_to_memory_or_evolution()
  - CLI --evaluate-turn 入口
"""

import os, json, sys, logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

# ── 从 v5 统一引擎导入所有需要暴露的类和函数 ──
from core.engines.hooks.self_evolution_engine import (
    SelfEvolutionEngine as V5Engine,
    RegisteredRule,
    RuleStore,
    RuleStore as RuleStoreV5,
    MASAPredictor,
    MASAAliener,
    DifficultyLevel,
    BiasPattern,
    JsonStore,
    init as v5_init,
    get_evolution_engine,
)

class SelfEvolutionEngine(V5Engine):
    """v3 兼容子类 — 继承 v5 统一引擎，保留旧签名"""
    pass

def init() -> SelfEvolutionEngine:
    global _instance
    if _instance is None:
        _instance = SelfEvolutionEngine()
    return _instance

def get_engine() -> SelfEvolutionEngine:
    return init()

def get_store() -> RuleStore:
    """兼容 evolution_tracker.get_store()"""
    engine = get_engine()
    return engine.rule_store

def evaluate_turn(context: dict = None, dry_run: bool = False) -> Dict:
    """兼容 v3 evaluate_turn 签名 → 委托 v5 unified_run_cycle"""
    ctx = context or {}
    user_msg = ctx.get("user_msg", "")
    assistant_msg = ctx.get("assistant_msg", "")
    turn_count = ctx.get("turn_count", 0)
    tool_calls = ctx.get("tool_calls", 0)
    tool_failures = ctx.get("tool_failures", 0)
    # 如果 context 里带了 dry_run 覆盖参数，优先使用
    if "dry_run" in ctx:
        dry_run = ctx["dry_run"]

    engine = get_engine()
    result = engine.unified_run_cycle(
        goal=f"用户消息: {user_msg[:200]}",
        context={
            "user_msg": user_msg,
            "assistant_msg": assistant_msg,
            "turn_count": turn_count,
            "tool_calls": tool_calls,
            "tool_failures": tool_failures,
        },
        dry_run=dry_run,  # v5 内部有触发门禁，不会浪费算力
    )
    # EvolutionCycleResult 是 dataclass，转 dict 访问
    if hasattr(result, "evolved"):
        return {
            "status": "ok",
            "source": "v5_unified",
            "evolved": result.evolved,
            "precipitated": result.precipitated,
            "rules_triggered": 0,
            "corrections": 0,
        }
    return {
        "status": "ok",
        "source": "v5_unified",
        "evolved": result.get("evolved", False),
        "precipitated": result.get("precipitated", False),
        "rules_triggered": result.get("rules_triggered", 0),
        "corrections": result.get("corrections", 0),
    }

def load_tuning_log():
    engine = get_engine()
    return engine.tuning_log

def save_tuning_log(log_data):
    engine = get_engine()
    engine.tuning_log = log_data
    engine._save_tuning_log()

def get_current_config():
    return dict(DEFAULT_CONFIG)

DEFAULT_CONFIG = {
    "anti_fake": {"risk_threshold": "high"},
    "dual_mode": {"default_mode": "fast", "auto_switch": True},
    "lazy_load": {"search_interval_ms": 500, "max_searches_per_task": 5, "cache_ttl_seconds": 1800},
    "mutex": {"task_timeout_seconds": 180, "max_retry": 3},
    "memory_layer": {"l2_retention_days": 7, "decay_start_days": 30, "decay_end_days": 90, "decay_min_weight": 0.5},
}

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

    if "--evaluate-turn" in sys.argv:
        context = {}
        if "--user-msg" in sys.argv:
            idx = sys.argv.index("--user-msg") + 1
            if idx < len(sys.argv):
                context["user_msg"] = sys.argv[idx]
        if "--assistant-msg" in sys.argv:
            idx = sys.argv.index("--assistant-msg") + 1
            if idx < len(sys.argv):
                context["assistant_msg"] = sys.argv[idx]
        if "--turn-count" in sys.argv:
            idx = sys.argv.index("--turn-count") + 1
            if idx < len(sys.argv):
                try:
                    context["turn_count"] = int(sys.argv[idx])
                except ValueError:
                    pass
        if "--tool-calls" in sys.argv:
            idx = sys.argv.index("--tool-calls") + 1
            if idx < len(sys.argv):
                try:
                    context["tool_calls"] = int(sys.argv[idx])
                except ValueError:
                    pass
        if "--tool-failures" in sys.argv:
            idx = sys.argv.index("--tool-failures") + 1
            if idx < len(sys.argv):
                try:
                    context["tool_failures"] = int(sys.argv[idx])
                except ValueError:
                    pass
        if "--dry-run" in sys.argv:
            idx = sys.argv.index("--dry-run") + 1
            if idx < len(sys.argv):
                raw = sys.argv[idx].lower()
                context["dry_run"] = raw in ("1", "true", "yes", "y")
        result = evaluate_turn(context, dry_run=context.get("dry_run", False))
        print(json.dumps(result, ensure_ascii=False))
    elif "--init" in sys.argv or "--bootstrap" in sys.argv:
        engine = get_engine()
        result = engine.init()
        print(json.dumps(result, ensure_ascii=False))
    else:
        engine = get_engine()
        print(json.dumps({"status": "ok", "version": "v3-compat-shim → v5",
                           "mode": "standalone"}, ensure_ascii=False))
