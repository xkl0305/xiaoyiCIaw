"""
Crusheart Agent OS — 消息预处理流水线主编排器
将7个阶段按顺序串行执行，生成结构化分析结果
"""

import os, sys, time
from datetime import datetime, timezone, timedelta

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)

BEIJING_TZ = timezone(timedelta(hours=8))


def now_str():
    return datetime.now(BEIJING_TZ).strftime("%H:%M:%S")


def _init_result(user_message: str) -> dict:
    return {
        "ts": now_str(),
        "message_preview": user_message[:100],
        "engines": {},
        "dual_mode": {},
        "skill_match": {},
        "risk_check": {},
        "engine_route": {},
        "iron_rules": {},
        "context_warning": {},
        "outbound_fake_check": {},
        "extra_engines": {},
        "session_state": {},
        "memory_alignment": {},
        "self_reflection": {},
        "evolution_context": {},
        "summary": {},
        "_profile": {},
        "_trace_summary": "",
    }


def _finalize(result: dict) -> dict:
    """汇总最终决策"""
    mode = result["dual_mode"].get("mode", "fast")
    risk_level = "suspicious" if result["risk_check"].get("is_suspicious") else "normal"
    skills_needed = result["skill_match"].get("matched_count", 0)
    needs_anti_fake = result.get("engine_route", {}).get("needs_anti_fake", False)

    result["final_decision"] = {
        "mode": "agent" if mode == "agent" else "fast",
        "anti_fake_required": needs_anti_fake or risk_level == "suspicious",
        "recommended_tools": result["skill_match"].get("top_skills", []),
    }

    # 引擎健康摘要
    engine_states = []
    for name, info in result.get("engines", {}).items():
        if info.get("status") == "ready":
            engine_states.append(f"✅{name}")
        elif info.get("status") == "error":
            engine_states.append(f"❌{name}")
    engine_summary = " | ".join(engine_states) if engine_states else "⚠️ 引擎无状态"

    route_info = result.get("engine_route", {})
    finish = route_info.get("finish_process", {})
    memory_note = " | 📝含记忆指令" if finish.get("should_evolve", False) else ""

    result["summary"] = (
        f"{'🟠 Agent模式' if result['final_decision']['mode'] == 'agent' else '🟢 快速模式'}"
        f" | 技能:{skills_needed}"
        f" | {'⚠️ 注意' if risk_level == 'suspicious' else '正常'}"
        f"{memory_note}"
        f" | {engine_summary}"
    )

    return result


def run_pipeline(user_message: str) -> dict:
    """
    消息预处理全流水线
    顺序执行：阶段0→1→2→3→4→5→6→7
    """
    result = _init_result(user_message)
    t0 = time.monotonic()

    # 看门狗 — pipeline 启动
    try:
        from core.engines.operations.watchdog_engine import watchdog_tick, watchdog_mark, get_watchdog
        wd = get_watchdog()
        wd.reset()
        watchdog_tick("pipeline")
    except ImportError:
        wd = None

    # 阶段0: 引擎状态检测
    from core.pipeline.engines import run_stage0
    result = run_stage0(result, user_message)
    if wd: watchdog_tick("stage0_engines")

    # 钩子阻止则提前返回
    if result.get("summary") == "🚫 钩子引擎阻止了请求执行":
        if wd: wd.mark_complete("pipeline")
        result["final_decision"] = {"mode": "fast", "anti_fake_required": False}
        return result

    # 阶段1: 双模式分类
    from core.pipeline.dual_mode import run_stage1
    result = run_stage1(result, user_message)
    if wd: watchdog_tick("stage1_dual_mode")

    # 阶段2: 技能匹配
    from core.pipeline.skill_match import run_stage2
    result = run_stage2(result, user_message)
    if wd: watchdog_tick("stage2_skill_match")

    # 阶段3: 防幻觉风险提示
    from core.pipeline.anti_fake import run_stage3
    result = run_stage3(result, user_message)
    if wd: watchdog_tick("stage3_anti_fake")

    # 阶段4: 引擎路由预分析
    from core.pipeline.engine_route import run_stage4
    result = run_stage4(result, user_message)
    if wd: watchdog_tick("stage4_engine_route")

    # 阶段5: 热RAM层
    from core.pipeline.session_state import run_stage5
    result = run_stage5(result, user_message)
    if wd: watchdog_tick("stage5_session_state")

    # 阶段5.5: 对话粘性引擎（语气调整）
    try:
        from core.engines.hooks.contextual_tone import generate_tone_hints
        tone_hints = generate_tone_hints(
            conversation_rounds=result.get("session_state", {}).get("round", 0),
            is_first_today=result.get("session_state", {}).get("first_today", False),
        )
        result["tone_hints"] = tone_hints
    except Exception:
        result["tone_hints"] = {"tone_hints": {"period": "default", "voice_style": ""}}
    if wd: watchdog_tick("stage55_contextual_tone")

    # 阶段5.6: 上下文策略编排（策略层统一调度）
    try:
        from core.pipeline.context_orchestrator import get_context_policy
        mode = result.get("dual_mode", {}).get("mode", "fast")
        risk_level = "suspicious" if result.get("risk_check", {}).get("is_suspicious") else "normal"
        is_memory_instruction = bool(result.get("engine_route", {}).get("finish_process", {}).get("should_evolve", False))
        context_policy = get_context_policy(
            mode="agent" if mode == "agent" else "balanced",
            risk_level=risk_level,
            is_memory_instruction=is_memory_instruction,
        )
        result["context_policy"] = context_policy
    except Exception as e:
        result["context_policy"] = {
            "budget_tokens": 400,
            "recall": {"depth": 10, "min_score": 0.4, "load_core_anchor": False},
            "inject_results": False,
            "injection_context": [],
            "compaction": {"should_compact": False},
        }
    if wd: watchdog_tick("stage56_context_policy")

    # 阶段5.7: 记忆路由（MemoryRouter）
    from core.pipeline.memory_router import run_stage57
    result = run_stage57(result, user_message)
    if wd: watchdog_tick("stage57_memory_router")

    # 阶段6: 记忆对齐
    from core.pipeline.memory_align import run_stage6
    result = run_stage6(result, user_message)
    if wd: watchdog_tick("stage6_memory_align")

    # 阶段6.5: 自进化上下文注入
    from core.pipeline.evolution_context import run_stage_evolution_context
    result = run_stage_evolution_context(result, user_message)
    if wd: watchdog_tick("stage6_evolution_context")

    # 阶段7: 自进化复盘
    from core.pipeline.self_reflection import run_stage7
    result = run_stage7(result, user_message)
    if wd: watchdog_tick("stage7_self_reflection")

    # 阶段6.7: 反遗忘扫描（非阻塞）
    try:
        from core.engines.memory.anti_forget_engine import get_anti_forget_engine
        af_engine = get_anti_forget_engine()
        forget_risks = af_engine.scan(force=False, top_k=3)
        result["anti_forget_risks"] = [r.memory.id for r in forget_risks[:3]]
        result["engines"]["anti_forget"] = {"status": "ready", "risks": len(forget_risks)}
    except Exception:
        result["anti_forget_risks"] = []
        result["engines"]["anti_forget"] = {"status": "not_loaded"}
    # 阶段8: 出站防幻觉校验（占位，实际调用在响应生成后由调用方传入content）
    # 初始化 outbound_fake_check 为空字典
    result["outbound_fake_check"] = result.get("outbound_fake_check", {})

    # 汇总
    result = _finalize(result)

    # 写执行日志
    from core.engines.memory.exec_logger import log_execution
    log_execution(
        tool_name="pipeline.run",
        status="success",
        duration_ms=int((time.monotonic() - t0) * 1000),
        result_summary=f"mode={result['final_decision']['mode']} skills={result['skill_match'].get('matched_count',0)} len={len(user_message)}",
        params_summary=user_message[:60],
    )

    # 后处理：纠正信号检测 + 技能失配记录
    _post_pipeline_learning(result, user_message)

    return result


def _sync_context_capsule(result: dict, user_message: str):
    """同步当前会话上下文到 .context_capsule.json，供 auto_save_capsule 读取"""
    try:
        capsule_path = os.path.join(WORKSPACE, ".context_capsule.json")
        goal = result.get("final_decision", {}).get("mode", "")
        if goal == "agent":
            goal = "高级任务处理"
        else:
            goal = "快速应答"

        # 读取现有胶囊
        data = {}
        if os.path.exists(capsule_path):
            with open(capsule_path) as f:
                data = json.load(f)

        data["current_goal"] = goal
        data["next_best_action"] = "继续回应用户"
        data["last_updated"] = datetime.now(BEIJING_TZ).isoformat()
        data.setdefault("pending_items", [])
        data.setdefault("task_stack", [])
        data.setdefault("recent_events", [])

        # 记录本次消息
        event = {
            "type": "user_message",
            "content": user_message[:100],
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        }
        data["recent_events"].append(event)
        if len(data["recent_events"]) > 20:
            data["recent_events"] = data["recent_events"][-20:]

        with open(capsule_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 不阻塞主流程


def _dispatch_portrait_signals(result: dict, user_message: str):
    """分发用户动态画像信号到自进化/参数调优"""
    try:
        from core.engines.memory.user_dynamic_portrait import get_portrait
        portrait = get_portrait()
        portrait.update_from_message(user_message)
        pending = portrait.get_pending_signals()
        for sig in pending:
            dispatch_type = sig.get("dispatch_type", "self_evolution")
            if dispatch_type == "self_evolution":
                result.setdefault("extra_engines", {})
                result["extra_engines"]["user_portrait_dispatch"] = {
                    "status": "pending",
                    "signals": len(pending),
                    "details": [s["signal_type"] for s in pending],
                }
            if dispatch_type == "auto_tuning" and "tuning_target" in sig:
                from core.engines.tools.auto_tuning import apply_suggestion
                tuning_pack = {
                    "from_engine": "user_dynamic_portrait",
                    "dispatch_type": "auto_tuning",
                    "engine": sig["tuning_target"]["engine"],
                    "field": sig["tuning_target"]["field"],
                    "suggested_value": sig["tuning_target"]["suggested_value"],
                    "reason": sig["tuning_target"].get("reason", "画像驱动调优"),
                    "confidence": sig.get("confidence", 0.7),
                }
                try:
                    apply_suggestion(tuning_pack)
                except Exception:
                    pass
    except Exception:
        pass


def _post_pipeline_learning(result: dict, user_message: str):
    """
    pipeline 后处理 — 非阻塞的纠正学习 + 上下文同步
    """
    # 同步上下文胶囊 + 用户画像信号分发（必须放在最前面）
    _sync_context_capsule(result, user_message)
    _dispatch_portrait_signals(result, user_message)

    # 记忆自动入库：每次对话后增量采集会话内容到 AutoMemory
    try:
        import importlib
        mp = importlib.import_module("scripts.memory_pipeline")
        mp.run_incremental()
    except Exception:
        pass  # 非阻塞，不影响主流程

    try:
        from core.engines.quality.judge_engine import ReplayBuffer
        rb = ReplayBuffer()

        # 1. 纠正信号检测
        prev_response = result.get("summary", "")
        rb.detect_correction(user_message, prev_response)

        # 2. 技能失配检测 — pipeline 阶段无真实执行结果，由调用方在技能实际执行后传入

        # 3. 模式失配检测（快速模式选了但任务复杂）
        chosen_mode = result.get("final_decision", {}).get("mode", "fast")
        rb.detect_mode_mismatch(chosen_mode, user_message)

    except ImportError:
        pass  # ReplayBuffer 未安装
    except Exception:
        pass  # 不阻塞主流程


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

    import json
    user_msg = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    if not user_msg:
        result = {"error": "未提供用户消息"}
    else:
        result = run_pipeline(user_msg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
