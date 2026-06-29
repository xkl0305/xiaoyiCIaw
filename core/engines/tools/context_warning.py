"""
Crusheart Performance AutoBrain v6.6.0 — Context Warning 上下文长度预警（Token 百分比版）
功能：根据上下文窗口的 Token 占用百分比，分三档预警提醒创建新会话
"""

import os, json
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_PATH = os.path.join(WORKSPACE, ".context_warning_state.json")

# 默认 Token 阈值（如无法读取模型配置则用此值）
_DEFAULT_CONTEXT_WINDOW = 256000
WARN_PCT = 50                    # ≥ 50% → 黄牌提醒
URGENT_PCT = 70                  # ≥ 70% → 橙牌建议新会话
CRITICAL_PCT = 85                # ≥ 85% → 红牌强制建议新会话
EXPIRY_MINUTES = 10              # 超过 10 分钟无操作，重置计数


def load_context_window() -> int:
    """
    从 OpenClaw 模型配置动态读取当前主模型的 contextWindow。
    扫描路径：
      1. ~/.openclaw/agents/main/agent/models.json
      2. ~/.openclaw/openclaw.json
      3. 回退到 _DEFAULT_CONTEXT_WINDOW
    """
    paths = [
        os.path.expanduser("~/.openclaw/agents/main/agent/models.json"),
        os.path.expanduser("~/.openclaw/openclaw.json"),
    ]
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # models.json 结构: {"providers": {"xxx": {"models": [{...}]}}}
            # openclaw.json 结构: {"mode": "replace", "providers": {...}}
            providers = data.get("providers", {})
            for pname, pdata in providers.items():
                models = pdata.get("models", [])
                for m in models:
                    cw = m.get("contextWindow")
                    if cw and isinstance(cw, int) and cw > 0:
                        return cw
        except (json.JSONDecodeError, IOError, KeyError):
            continue
    return _DEFAULT_CONTEXT_WINDOW


def load_state() -> dict:
    """加载上下文状态（含自动迁移旧版结构）"""
    state = None
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                loaded = json.load(f)
            # 迁移：旧版状态可能缺少字段
            defaults = _default_state()
            for key in defaults:
                if key not in loaded:
                    loaded[key] = defaults[key]
            state = loaded
        except (json.JSONDecodeError, IOError):
            pass
    if state is None:
        state = _default_state()
    return state


def _default_state() -> dict:
    return {
        "session_rounds": 0,
        "estimated_tokens": 0,
        "token_level": "green",
        "warning_triggered": False,
        "last_activity": None,
        "session_started_at": None,
        "reset_count": 0
    }


def save_state(state: dict):
    """保存上下文状态"""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _estimate_tokens(rounds: int, tool_calls: int) -> int:
    """
    估算当前上下文的 Token 数。
    基于经验公式：每轮对话 ≈ 1500 tokens，每次工具调用 ≈ 800 tokens
    （实际应在 pipeline 中获取真实 token 计数，此为后备估算）
    """
    round_tokens = rounds * 1500
    tool_tokens = tool_calls * 800
    return round_tokens + tool_tokens


def _get_token_level(estimated: int) -> tuple:
    """返回 (level_str, pct) — green/yellow/orange/red + 百分比"""
    max_tok = load_context_window()
    pct = min(100.0, (estimated / max_tok) * 100)
    if pct >= CRITICAL_PCT:
        return "red", pct
    elif pct >= URGENT_PCT:
        return "orange", pct
    elif pct >= WARN_PCT:
        return "yellow", pct
    return "green", pct


def check(estimated_tokens: int = 0):
    """
    主检查函数 — 每次收到用户消息时调用
    传入 estimated_tokens 为 pipeline 估算值，0 则自动估算
    返回 dict 包含是否需提醒
    """
    state = load_state()
    now = datetime.now(BEIJING_TZ)

    # 新会话检测
    if state["last_activity"]:
        last = datetime.fromisoformat(state["last_activity"])
        if (now - last).total_seconds() > EXPIRY_MINUTES * 60:
            state = _default_state()
            state["session_started_at"] = now.isoformat()
            state["last_activity"] = now.isoformat()
            save_state(state)
            return {"warning": False, "level": "green", "pct": 0, "reason": "new_session_reset"}

    # 首次启动
    if state["session_started_at"] is None:
        state["session_started_at"] = now.isoformat()
        state["last_activity"] = now.isoformat()
        save_state(state)
        return {"warning": False, "level": "green", "pct": 0, "reason": "first_start"}

    # 递增轮次
    state["session_rounds"] += 1
    state["last_activity"] = now.isoformat()

    # 估算 Token
    if estimated_tokens > 0:
        state["estimated_tokens"] = estimated_tokens
    else:
        # 用工具调用次数作更准估算；外部调用 tool_call() 时会加，这里沿用旧值
        state["estimated_tokens"] = _estimate_tokens(
            state["session_rounds"],
            state.get("tool_calls", 0)
        )

    level, pct = _get_token_level(state["estimated_tokens"])
    state["token_level"] = level

    warning = False
    reason = ""
    if level == "red":
        warning = True
        _max_tok = load_context_window()
        reason = f"[🔴 红色预警] 上下文已达 {pct:.0f}%（{state['estimated_tokens']:,}/{_max_tok:,}），强烈建议开启新会话"
        state["warning_triggered"] = True
    elif level == "orange":
        warning = True
        _max_tok = load_context_window()
        reason = f"[🟠 橙牌预警] 上下文 {pct:.0f}%（{state['estimated_tokens']:,}/{_max_tok:,}），建议开启新会话"
        state["warning_triggered"] = True
    elif level == "yellow" and not state["warning_triggered"]:
        warning = True
        _max_tok = load_context_window()
        reason = f"[🟡 黄牌提醒] 上下文已达 {pct:.0f}%（{state['estimated_tokens']:,}/{_max_tok:,}），留意上下文使用"
        state["warning_triggered"] = True

    save_state(state)

    result = {
        "warning": warning,
        "level": level,
        "pct": round(pct, 1),
        "estimated_tokens": state["estimated_tokens"],
        "max_tok": load_context_window(),
        "reason": reason,
        "session_rounds": state["session_rounds"],
        "session_started_at": state["session_started_at"]
    }

    if warning:
        print(f"  {reason}")

    return result


def record_tool_call():
    """记录一次工具调用（保持向后兼容）"""
    state = load_state()
    if state["session_started_at"] is None:
        state["session_started_at"] = datetime.now(BEIJING_TZ).isoformat()
    state["estimated_tokens"] = _estimate_tokens(
        state["session_rounds"],
        state.get("tool_calls", 0) + 1
    )
    state["last_activity"] = datetime.now(BEIJING_TZ).isoformat()
    save_state(state)


def reset():
    """手动重置状态（用户主动开启新会话）"""
    state = _default_state()
    state["session_started_at"] = datetime.now(BEIJING_TZ).isoformat()
    state["last_activity"] = state["session_started_at"]
    save_state(state)
    print("  ✅ Context Warning: 状态已重置（新会话）")
    return state


def get_stats() -> dict:
    """获取上下文统计信息"""
    state = load_state()
    level, pct = _get_token_level(state.get("estimated_tokens", 0))
    return {
        "session_rounds": state["session_rounds"],
        "estimated_tokens": state["estimated_tokens"],
        "token_level": level,
        "token_pct": round(pct, 1),
        "thresholds": {
            "context_window_max": load_context_window(),
            "warn_pct": WARN_PCT,
            "urgent_pct": URGENT_PCT,
            "critical_pct": CRITICAL_PCT,
            "expiry_minutes": EXPIRY_MINUTES
        },
        "session_started_at": state["session_started_at"],
        "last_activity": state["last_activity"],
        "reset_count": state.get("reset_count", 0)
    }


def init():
    """引擎初始化入口"""
    stats = get_stats()
    warned = stats["warning_triggered"] if "warning_triggered" in stats else False
    max_tok = load_context_window()
    info = f"Token {stats['estimated_tokens']:,}/{max_tok:,} ({stats['token_pct']}%) | 轮次 {stats['session_rounds']}"
    if stats["token_level"] != "green":
        info += f" ⚠️ {stats['token_level']}级预警"

    print(f"  📏 Context Warning: {info}")

    return {
        "status": "ready",
        "stats": stats,
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
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

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        result = check(tokens)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset()
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        result = init()
        print(json.dumps(result, indent=2, ensure_ascii=False))
