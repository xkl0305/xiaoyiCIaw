"""
Crusheart AutoBrain v6.6.0-p2 — Auto Tuning 引擎参数自调优
功能：基于引擎执行数据（优先 UnifiedScorer），自动调优运行时参数

v6.6.0-p2:
  - 新增 analyze_from_unified(): 从 UnifiedScorer 读取评分数据出调优建议
  - UnifiedScorer 不可用时回退到原有独立日志分析
  - 技能质量自动调优映射（SKILL_QUALITY_CONFIG）
"""

import os, json, time
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
TUNING_LOG = os.path.join(WORKSPACE, ".tuning_log.json")
CONFIG_PATH = os.path.join(WORKSPACE, "skills", "Crusheart-AutoBrain-Turbo", "config.json")

# ── UnifiedScorer 统一评分通道 ──
try:
    from core.engines.quality.unified_scorer import get_scorer as _at_get_scorer
except ImportError:
    _at_get_scorer = None


# 默认参数基线（首次使用）
DEFAULT_CONFIG = {
    "anti_fake": {
        "risk_threshold": "high",
        "authority_domains": [
            ".gov.cn", ".gov", ".edu.cn", ".edu",
            "arxiv.org", "reuters.com", "xinhuanet.com"
        ]
    },
    "dual_mode": {
        "default_mode": "fast",
        "auto_switch": True,
        "fast_keyword_weight": 10,
        "agent_keyword_weight": 8,
        "multi_tool_weight": 15,
        "text_length_threshold": 120
    },
    "lazy_load": {
        "search_interval_ms": 500,
        "max_searches_per_task": 5,
        "cache_ttl_seconds": 1800
    },
    "mutex": {
        "task_timeout_seconds": 180,
        "max_retry": 3,
        "skill_weights": {
            "image_reading_weight": 1.0,
            "web_search_weight": 1.0,
            "pdf_reader_weight": 1.0,
        }
    },
    "self_evolution": {
        "enabled": True,
        "require_confirmation": True
    },
    "memory_layer": {
        "l2_retention_days": 7,
        "decay_start_days": 30,
        "decay_end_days": 90,
        "decay_min_weight": 0.5
    }
}

# 调优建议模板
TUNING_SUGGESTIONS = {
    "anti_fake": {
        "high": {"field": "risk_threshold", "action": "保持 high，若误报频繁可降为 medium"},
        "medium": {"field": "risk_threshold", "action": "medium 适中，适合高吞吐场景"}
    },
    "dual_mode": {
        "fast_too_slow": {"field": "fast_keyword_weight", "action": "提高 fast_keyword_weight，减少误切 Agent"},
        "agent_too_fast": {"field": "agent_keyword_weight", "action": "提高 agent_keyword_weight，减少误切 Fast"},
        "text_too_short": {"field": "text_length_threshold", "action": "降低 text_length_threshold，长文本更易进 Agent"}
    },
    "lazy_load": {
        "cache_miss_high": {"field": "cache_ttl_seconds", "action": "提高 cache_ttl，减少重复搜索"},
        "search_retry_high": {"field": "max_searches_per_task", "action": "降低 max_searches_per_task，节约配额"}
    },
    "mutex": {
        "timeout_frequent": {"field": "task_timeout_seconds", "action": "提高 timeout，给长任务更多时间"},
        "retry_exhausted": {"field": "max_retry", "action": "提高 max_retry，增加容错"}
    },
    "memory_layer": {
        "decay_too_fast": {"field": "decay_start_days", "action": "提高 decay_start_days，延长活跃期"},
        "retention_short": {"field": "l2_retention_days", "action": "提高 l2_retention_days，短期记忆更持久"}
    },
    "masa": {
        "low_alignment": {"field": "masa_confidence_bias", "action": "MASA 对齐度持续偏低，建议降低默认置信度"},
        "frequent_underestimate": {"field": "task_timeout_seconds", "action": "MASA 难度低估频繁，建议提高 task_timeout"},
        "frequent_overconfidence": {"field": "masa_confidence_bias", "action": "MASA 过于自信频繁，建议启用低置信度强制验证"}
    },
    "skill_weights": {
        "low_quality": {"field": "skill_weight", "action": "技能质量偏低，自动降低权重，同类任务切换备用技能"}
    }
}


def load_tuning_log():
    """加载调优日志"""
    if os.path.exists(TUNING_LOG):
        try:
            with open(TUNING_LOG) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"history": [], "stats": {}}
    return {"history": [], "stats": {}}


def save_tuning_log(log_data):
    """保存调优日志"""
    os.makedirs(os.path.dirname(TUNING_LOG), exist_ok=True)
    with open(TUNING_LOG, "w") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def get_current_config():
    """获取当前配置"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULT_CONFIG)


# ── 从 UnifiedScorer 分析 ──────────────────────────────

def analyze_from_unified(window_hours: int = 48):
    """
    从 UnifiedScorer 读取评分数据，生成调优建议。
    替代原先只读自己独立日志的分析逻辑。

    Args:
        window_hours: 分析窗口（小时）

    Returns:
        调优建议列表（空列表表示无需调整）
    """
    if _at_get_scorer is None:
        return []

    try:
        scorer = _at_get_scorer()
    except Exception:
        return []

    results = []
    config = get_current_config()

    try:
        # 1. 降级链执行质量
        quality_events = scorer.query(
            source="degradation_chain",
            since=time.time() - window_hours * 3600,
            limit=200
        )
        if quality_events:
            avg_exec = sum(e.score for e in quality_events) / len(quality_events)
            fail_count = sum(1 for e in quality_events if e.score < 0.1)
            if avg_exec < 0.3 and fail_count > 10:
                results.append({
                    "engine": "dual_mode",
                    "field": "multi_tool_weight",
                    "action": f"降级链失败率 {fail_count}/{len(quality_events)}，建议提高 multi_tool_weight",
                    "reason": f"UnifiedScorer: degradation_chain avg={avg_exec:.2f}",
                    "type": "optimization",
                    "source": "unified_scorer",
                })
            elif avg_exec < 0.6:
                results.append({
                    "engine": "mutex",
                    "field": "task_timeout_seconds",
                    "action": f"执行质量 {avg_exec:.2f}，建议提高 task_timeout",
                    "reason": f"UnifiedScorer: exec_quality avg={avg_exec:.2f}",
                    "type": "optimization",
                    "source": "unified_scorer",
                })

        # 2. 红线违规趋势
        redline_events = scorer.query(
            source="redline_engine",
            since=time.time() - window_hours * 3600,
            limit=100
        )
        if redline_events:
            hard_block_count = sum(1 for e in redline_events if e.score < 0.2)
            if hard_block_count > 10:
                results.append({
                    "engine": "anti_fake",
                    "field": "risk_threshold",
                    "action": f"红线硬阻断 {hard_block_count}/{len(redline_events)} 次，建议降级 risk_threshold",
                    "reason": f"UnifiedScorer: redline hard_block={hard_block_count}",
                    "type": "optimization",
                    "source": "unified_scorer",
                })

        # 3. JudgeEngine 评分趋势
        judge_events = scorer.query(
            source="judge_engine",
            since=time.time() - window_hours * 3600,
            limit=200
        )
        if judge_events:
            faithful = [e for e in judge_events if e.dimension == "faithfulness"]
            if faithful:
                avg_f = sum(e.score for e in faithful) / len(faithful)
                if avg_f < 0.5:
                    results.append({
                        "engine": "self_evolution",
                        "field": "require_confirmation",
                        "action": f"忠实度评分偏低（avg={avg_f:.2f}），建议开启 require_confirmation",
                        "reason": f"UnifiedScorer: faithfulness avg={avg_f:.2f}",
                        "type": "optimization",
                        "source": "unified_scorer",
                    })

        # 4. Skill 执行质量 → 动态调整技能权重
        skill_events = scorer.query(
            dimension="exec_quality",
            since=time.time() - window_hours * 3600,
            limit=500
        )
        if skill_events:
            # 按 task_type 分组
            task_scores = {}
            for e in skill_events:
                # 从 metadata 中提取 task 名称
                task = e.metadata.get("task", e.context)[:30]
                if task not in task_scores:
                    task_scores[task] = []
                task_scores[task].append(e.score)
            # 找出持续低分的 task
            for task, scores in task_scores.items():
                if len(scores) >= 3:
                    avg_s = sum(scores) / len(scores)
                    if avg_s < 0.4:
                        # 技能持续低分，建议自动降级
                        from core.engines.quality.unified_scorer import get_scorer
                        results.append({
                            "engine": "skill_weights",
                            "field": "skill_weight",
                            "action": f"任务 '{task[:20]}' 评分 {avg_s:.2f}（{len(scores)}次），建议自动切换备用技能",
                            "reason": f"UnifiedScorer: {task} avg={avg_s:.2f}",
                            "type": "optimization",
                            "source": "unified_scorer",
                            "confidence": min(0.5 + avg_s, 0.95),
                        })

    except Exception:
        pass

    return results


# ── 从独立日志分析（回退方案） ──────────────────────────

def analyze_tuning(suggestions=None):
    """
    根据收集的性能数据生成调优建议
    优先从 UnifiedScorer 读取数据，回退到独立日志

    v6.6.0-p2: 新增 UnifiedScorer 数据源优先
    """
    # 如果 UnifiedScorer 可用，先用它
    if _at_get_scorer is not None:
        try:
            unified_suggestions = analyze_from_unified()
            if unified_suggestions:
                if suggestions:
                    unified_suggestions.extend(
                        s for s in suggestions if isinstance(s, dict))
                return unified_suggestions
        except Exception:
            pass

    # 回退到原有的独立日志分析
    log_data = load_tuning_log()
    stats = log_data.get("stats", {})
    config = get_current_config()
    results = []

    if suggestions is None:
        suggestions = {}

    # 检查 dual_mode 是否频繁误切换
    if "dual_mode_misclassifications" in stats and stats["dual_mode_misclassifications"] > 5:
        results.append({
            "engine": "dual_mode",
            "field": TUNING_SUGGESTIONS["dual_mode"]["fast_too_slow"]["field"],
            "action": TUNING_SUGGESTIONS["dual_mode"]["fast_too_slow"]["action"],
            "reason": f"双模式误分类达 {stats['dual_mode_misclassifications']} 次",
            "type": "optimization"
        })

    # 检查 lazy_load 缓存命中率
    if "cache_hit_rate" in stats:
        rate = stats["cache_hit_rate"]
        if isinstance(rate, (int, float)) and rate < 0.3:
            results.append({
                "engine": "lazy_load",
                "field": TUNING_SUGGESTIONS["lazy_load"]["cache_miss_high"]["field"],
                "action": TUNING_SUGGESTIONS["lazy_load"]["cache_miss_high"]["action"],
                "reason": f"缓存命中率仅 {rate:.0%}",
                "type": "optimization"
            })

    # 检查 mutex 超时
    if "mutex_timeouts" in stats and stats["mutex_timeouts"] > 3:
        results.append({
            "engine": "mutex",
            "field": TUNING_SUGGESTIONS["mutex"]["timeout_frequent"]["field"],
            "action": TUNING_SUGGESTIONS["mutex"]["timeout_frequent"]["action"],
            "reason": f"任务超时达 {stats['mutex_timeouts']} 次",
            "type": "optimization"
        })

    # MASA 对齐度监控
    if "masa_alignment_score" in stats:
        align_score = stats["masa_alignment_score"]
        if isinstance(align_score, (int, float)) and align_score < 0.5:
            results.append({
                "engine": "masa",
                "field": TUNING_SUGGESTIONS["masa"]["low_alignment"]["field"],
                "action": TUNING_SUGGESTIONS["masa"]["low_alignment"]["action"],
                "reason": f"MASA 对齐度仅 {align_score:.2f}",
                "type": "optimization"
            })
    if "masa_difficulty_mismatch" in stats:
        mismatch_count = stats["masa_difficulty_mismatch"]
        if isinstance(mismatch_count, (int, float)) and mismatch_count > 5:
            results.append({
                "engine": "masa",
                "field": TUNING_SUGGESTIONS["masa"]["frequent_underestimate"]["field"],
                "action": TUNING_SUGGESTIONS["masa"]["frequent_underestimate"]["action"],
                "reason": f"MASA 难度误判达 {mismatch_count} 次",
                "type": "optimization"
            })
    if "masa_overconfidence_count" in stats:
        overconf = stats["masa_overconfidence_count"]
        if isinstance(overconf, (int, float)) and overconf > 3:
            results.append({
                "engine": "masa",
                "field": TUNING_SUGGESTIONS["masa"]["frequent_overconfidence"]["field"],
                "action": TUNING_SUGGESTIONS["masa"]["frequent_overconfidence"]["action"],
                "reason": f"MASA 过于自信达 {overconf} 次",
                "type": "optimization"
            })
    if "masa_time_error_rate" in stats:
        terr = stats["masa_time_error_rate"]
        if isinstance(terr, (int, float)) and abs(terr) > 200:
            results.append({
                "engine": "mutex",
                "field": TUNING_SUGGESTIONS["mutex"]["timeout_frequent"]["field"],
                "action": TUNING_SUGGESTIONS["mutex"]["timeout_frequent"]["action"],
                "reason": f"MASA 时间偏差达 {terr:.0f}%",
                "type": "optimization"
            })

    # 添加用户手动传入的建议
    if suggestions:
        for engine, suggestion in suggestions.items():
            if engine in TUNING_SUGGESTIONS and suggestion in TUNING_SUGGESTIONS[engine]:
                sug = TUNING_SUGGESTIONS[engine][suggestion]
                results.append({
                    "engine": engine,
                    "field": sug["field"],
                    "action": sug["action"],
                    "reason": "用户手动触发调优建议",
                    "type": "manual"
                })

    return results


def apply_suggestion(signal: dict) -> dict:
    """
    接收调优信号，直接修改 config.json。
    v2.0 新增：让参数自调优从"只写日志"变成"真改配置"。

    信号格式：
    {
        "from_engine": "user_dynamic_portrait",
        "dispatch_type": "auto_tuning",
        "engine": "dual_mode",
        "field": "fast_keyword_weight",
        "suggested_value": 15,
        "reason": "...",
        "confidence": 0.85,
    }
    """
    config = get_current_config()
    engine_name = signal.get("engine", "")
    field = signal.get("field", "")
    suggested = signal.get("suggested_value")
    reason = signal.get("reason", "")
    confidence = signal.get("confidence", 0.7)

    if engine_name not in TUNING_SUGGESTIONS:
        return {"status": "skipped", "reason": f"未知引擎: {engine_name}"}

    field_valid = False
    for suggestion_group in TUNING_SUGGESTIONS[engine_name].values():
        if suggestion_group.get("field") == field:
            field_valid = True
            break
    if not field_valid:
        return {"status": "skipped", "reason": f"引擎 {engine_name} 无字段 {field} 的调优建议"}

    if engine_name in config.get("engines", {}):
        current = config["engines"][engine_name].get(field)
        if current == suggested:
            return {"status": "skipped", "reason": f"字段 {field} 当前值已是 {suggested}"}
    elif engine_name in config:
        current = config[engine_name].get(field)
        if current == suggested:
            return {"status": "skipped", "reason": f"字段 {field} 当前值已是 {suggested}"}

    if engine_name in config.get("engines", {}):
        if field in config["engines"][engine_name]:
            old_val = config["engines"][engine_name].get(field)
            config["engines"][engine_name][field] = suggested
        else:
            config["engines"][engine_name][field] = suggested
            old_val = None
    elif engine_name in config:
        old_val = config[engine_name].get(field)
        config[engine_name][field] = suggested
    else:
        return {"status": "error", "reason": f"引擎 {engine_name} 不在配置中"}

    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"status": "error", "reason": f"写入config失败: {e}"}

    record_metric(engine_name, f"{field}_tuned", suggested)

    return {
        "status": "applied",
        "engine": engine_name,
        "field": field,
        "old_value": old_val,
        "new_value": suggested,
        "reason": reason,
        "confidence": confidence,
        "applied_at": datetime.now(BEIJING_TZ).isoformat(),
    }


def record_metric(engine, metric_name, value):
    """记录一条性能指标"""
    log_data = load_tuning_log()
    if "stats" not in log_data:
        log_data["stats"] = {}
    log_data["stats"][f"{engine}_{metric_name}"] = value
    if "history" not in log_data:
        log_data["history"] = []
    log_data["history"].append({
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        "engine": engine,
        "metric": metric_name,
        "value": value
    })
    if len(log_data["history"]) > 100:
        log_data["history"] = log_data["history"][-100:]
    save_tuning_log(log_data)


def init():
    """引擎初始化时的自检入口"""
    suggestions = analyze_tuning()

    result = {
        "status": "ready",
        "pending_suggestions": len(suggestions),
        "suggestions": suggestions,
        "unified_available": _at_get_scorer is not None,
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
    }

    if suggestions:
        print(f"  ⚙️ Auto Tuning: {len(suggestions)} 条调优建议待处理")
        if _at_get_scorer is not None:
            print(f"     （数据源：UnifiedScorer）")
        else:
            print(f"     （数据源：独立日志）")

    return result


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

    result = init()
    print(json.dumps(result, indent=2, ensure_ascii=False))
