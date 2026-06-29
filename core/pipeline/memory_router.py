"""
Crusheart Agent OS — 流水线阶段5.7：记忆路由（Memory Router）

职责：
  将用户的记忆相关查询自动路由到正确的记忆层级，
  避免暴力扫描全量记忆导致数据爆炸。

路由策略：
  1. 先用关键词规则快速识别时间范围和检索意图（降级备用）
  2. 再用 LLM 语义判断做主体（由 pipeline 后续的模型推理自然完成，
     本层只提供时间范围策略 + 层级选择建议）
  3. 根据时间范围决定查哪层：
     - < 5min  → 会话热RAM（session_state）
     - < 24h   → DAG 胶囊（context_capsule）
     - 昨天/前天 → DAG + 原始 session 文件
     - >= 7d / 无时间实体 → 向量记忆（auto_memory）

输出：
  result["memory_router"] = {
    "strategy": "dag" | "session" | "vector" | "hotram",
    "time_range": { "start": timestamp, "end": timestamp } | None,
    "keywords": [...],
    "is_memory_query": bool,
    "fallback_used": bool,    # 是否走关键词降级
    "dag_search_params": {...} | None,
    "vector_search_params": {...} | None,
  }
"""

import re, os, json, time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

DAG_DB = os.path.join(WORKSPACE, ".context_capsule_dag.db")
CAPSULE_FILE = os.path.join(WORKSPACE, ".context_capsule.json")

# ============================================================
# 规则1：时间关键词识别（降级备用）
# 覆盖中英文常见时间表达，优先级从近到远
# ============================================================

# ── 时间关键词模式 ──
TIME_PATTERNS = [
    # 刚刚 / 刚才 / 刚说的 （< 5分钟）
    (r"刚[才说]?|刚才|刚刚|上一[句条]|前一句|上一条", "just_now"),

    # 今天 / 今天凌晨 / 今天早上 / 今晚
    (r"今天|今日|今晚|今早|今晨", "today"),

    # 昨天 / 昨日 / 昨晚 / 昨天凌晨 / 昨天早上
    (r"昨天|昨日|昨晚|昨天凌晨|昨天早上|昨天下午|昨天上午|昨[日天]?晚|昨[日天]?凌晨|昨[日天]?早|昨天[早中下晚]", "yesterday"),

    # 前天 / 前天晚
    (r"前天|前天晚|前天凌晨|前天早上", "day_before_yesterday"),

    # 凌晨 / 早上 / 上午 / 中午 / 下午 / 晚上
    (r"(凌晨|早上|早[上晨]?|上午|中午|下午|晚上|夜间|深夜)", "time_period"),

    # 具体时间 HH:MM
    (r"([0-2]?[0-9])[：:]([0-5][0-9])", "specific_time"),

    # 具体日期 YYYY-MM-DD / MM-DD
    (r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2})", "specific_date"),

    # N 分钟 / 小时 / 天前
    (r"(\d+)\s*(分钟|小时|天|周|月|年)\s*(前|之前|以前)", "n_ago"),

    # 上周 / 上个月
    (r"上[周个]|上周[一二三四五六日天]?|上个月", "last_week"),

    # 之前 / 以前 / 上次 / 上一轮
    (r"之前|以前|上次|上一轮|上轮|上回", "previous"),

    # 近 N 天 / 最近 N 天
    (r"(近|最近)\s*(\d+)\s*(天|日|周|小时|分钟)", "recent_n"),

    # 第几轮 / 第几次对话
    (r"第\s*(\d+)\s*(轮|次|个|条)", "specific_turn"),
]


def _detect_time_keywords(text: str) -> Dict:
    """关键词降级：从文本中提取时间范围

    Returns:
      {
        "matched_type": str | None,   # 匹配的时间类别
        "time_range": { "start": str, "end": str } | None,
        "confidence": float,           # 0.0 ~ 1.0
        "raw_match": str | None,       # 匹配到的原文片段
      }
    """
    text_lower = text.lower()
    now = datetime.now(BEIJING_TZ)

    for pattern, category in TIME_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue

        raw = m.group(0)
        time_range = None

        if category == "just_now":
            time_range = {
                "start": (now - timedelta(minutes=5)).isoformat(),
                "end": now.isoformat(),
            }
            return {"matched_type": "just_now", "time_range": time_range,
                    "confidence": 0.95, "raw_match": raw}

        elif category == "today":
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # 检测是否是具体时段
            period_m = re.search(r"(凌晨|早上|上午|中午|下午|晚上)", text)
            if period_m:
                period = period_m.group(1)
                period_map = {
                    "凌晨": (0, 5), "早上": (6, 8), "上午": (8, 11),
                    "中午": (11, 13), "下午": (13, 18), "晚上": (18, 23),
                }
                h_start, h_end = period_map.get(period, (0, 23))
                time_range = {
                    "start": today_start.replace(hour=h_start).isoformat(),
                    "end": today_start.replace(hour=h_end, minute=59).isoformat(),
                }
            else:
                time_range = {
                    "start": today_start.isoformat(),
                    "end": now.isoformat(),
                }
            return {"matched_type": "today", "time_range": time_range,
                    "confidence": 0.9, "raw_match": raw}

        elif category == "yesterday":
            yesterday = now - timedelta(days=1)
            y_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

            period_m = re.search(r"(凌晨|早上|上午|中午|下午|晚上)", text)
            if period_m:
                period = period_m.group(1)
                period_map = {
                    "凌晨": (0, 5), "早上": (6, 8), "上午": (8, 11),
                    "中午": (11, 13), "下午": (13, 18), "晚上": (18, 23),
                }
                h_start, h_end = period_map.get(period, (0, 23))
                time_range = {
                    "start": y_start.replace(hour=h_start).isoformat(),
                    "end": y_start.replace(hour=h_end, minute=59).isoformat(),
                }
            else:
                time_range = {
                    "start": y_start.isoformat(),
                    "end": yesterday.replace(hour=23, minute=59, second=59).isoformat(),
                }
            return {"matched_type": "yesterday", "time_range": time_range,
                    "confidence": 0.95, "raw_match": raw}

        elif category == "day_before_yesterday":
            dby = now - timedelta(days=2)
            dby_start = dby.replace(hour=0, minute=0, second=0, microsecond=0)
            time_range = {
                "start": dby_start.isoformat(),
                "end": dby.replace(hour=23, minute=59, second=59).isoformat(),
            }
            return {"matched_type": "day_before_yesterday", "time_range": time_range,
                    "confidence": 0.9, "raw_match": raw}

        elif category == "time_period":
            period = m.group(1) if m.lastindex else m.group(0)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_map = {
                "凌晨": (0, 5), "早上": (6, 8), "上午": (8, 11),
                "中午": (11, 13), "下午": (13, 18), "晚上": (18, 23),
                "早": (6, 8), "晨": (6, 8),
                "夜间": (22, 23), "深夜": (22, 23),
            }
            h_start, h_end = period_map.get(period, (0, 23))

            # 判断是昨天还是今天：如果没有日期词默认今天
            if any(w in text for w in ["昨天", "昨日", "昨晚"]):
                ref_day = now - timedelta(days=1)
            elif any(w in text for w in ["前天"]):
                ref_day = now - timedelta(days=2)
            else:
                ref_day = now

            ref_start = ref_day.replace(hour=0, minute=0, second=0, microsecond=0)
            time_range = {
                "start": ref_start.replace(hour=h_start).isoformat(),
                "end": ref_start.replace(hour=h_end, minute=59).isoformat(),
            }
            return {"matched_type": "time_period", "time_range": time_range,
                    "confidence": 0.7, "raw_match": raw}

        elif category == "specific_time":
            h, m = int(m.group(1)), int(m.group(2))
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # 判断是哪一天
            if any(w in text for w in ["昨天", "昨日", "昨晚"]):
                ref_day = now - timedelta(days=1)
            elif any(w in text for w in ["前天"]):
                ref_day = now - timedelta(days=2)
            else:
                ref_day = now

            ref_start = ref_day.replace(hour=0, minute=0, second=0, microsecond=0)
            time_range = {
                "start": ref_start.replace(hour=h, minute=m).isoformat(),
                "end": ref_start.replace(hour=h, minute=m, second=59).isoformat(),
            }
            return {"matched_type": "specific_time", "time_range": time_range,
                    "confidence": 0.85, "raw_match": raw}

        elif category == "n_ago":
            n = int(m.group(1))
            unit = m.group(2)
            unit_map = {"分钟": "minutes", "小时": "hours", "天": "days",
                        "周": "weeks", "月": "days*30", "年": "days*365"}
            td_map = {
                "minutes": timedelta(minutes=n),
                "hours": timedelta(hours=n),
                "days": timedelta(days=n),
                "weeks": timedelta(weeks=n),
            }
            td = None
            for k, v in td_map.items():
                if unit in k:
                    td = v
                    break
            if unit in ("月",):
                td = timedelta(days=n * 30)
            elif unit in ("年",):
                td = timedelta(days=n * 365)

            if td:
                time_range = {
                    "start": (now - td).isoformat(),
                    "end": now.isoformat(),
                }
            return {"matched_type": "n_ago", "time_range": time_range,
                    "confidence": 0.85, "raw_match": raw}

        elif category == "previous":
            time_range = {
                "start": (now - timedelta(hours=2)).isoformat(),
                "end": now.isoformat(),
            }
            return {"matched_type": "previous", "time_range": time_range,
                    "confidence": 0.6, "raw_match": raw}

        elif category == "recent_n":
            n = int(m.group(2))
            unit = m.group(3)
            td_map = {"天": timedelta(days=n), "日": timedelta(days=n),
                      "周": timedelta(weeks=n), "小时": timedelta(hours=n),
                      "分钟": timedelta(minutes=n)}
            td = None
            for k, v in td_map.items():
                if unit in k:
                    td = v
                    break
            if td:
                time_range = {
                    "start": (now - td).isoformat(),
                    "end": now.isoformat(),
                }
            return {"matched_type": "recent_n", "time_range": time_range,
                    "confidence": 0.8, "raw_match": raw}

        elif category == "specific_turn":
            return {"matched_type": "specific_turn", "time_range": None,
                    "confidence": 0.5, "raw_match": raw}

    return {"matched_type": None, "time_range": None, "confidence": 0.0, "raw_match": None}


# ============================================================
# 规则2：记忆查询意图识别
# ============================================================

MEMORY_QUERY_PATTERNS = [
    # 回忆/查找类
    r"(上次|之前|以前|刚才|刚说)的.*(任务|事|问题|对话|记录|会话|聊天)",
    r"(记得|记住|回忆|回想|想起来|说说|聊聊).*(什么|怎么|吗|没|了|过)",
    r"(查|找|翻|看)[一下|一遍|一?下]?(昨天|前天|刚才|晚上|凌晨|早上|之前|以前|最近|历史)",
    r"(搞|做|弄|处理|完成)[完|好|了]?[了]?(没|吗|没有|怎么样|吗)",
    r"(任务|事情|问题)(搞|做)好[了]?[了]?(没|吗|没有|怎么样)",
    r"刚才.*(说|问|聊|提|讲)",
    r"(查|搜|找|翻).*(历史|记录|对话|会话|记忆)",
    r"(我|我们).*(说|聊|讨论|商量|商量过|提过)(过|的|了).*",
    r"(什么|怎么).*(刚才|刚才|之前|上次|昨天)",
    r"还记得.*吗",
    r"我们.*(有没有|是不是|有没有过|有没有说).*",
]

# 非记忆查询 —— 快速排除，减少误报
NON_MEMORY_PATTERNS = [
    r"^(早|你好|嗨|hi|hello|在吗|在不在|晚上好|下午好|中午好|早上好)$",
    r"^(好[的吧]?|嗯|嗯嗯|明白|懂了|行|可以|ok|okay|好的|收到|了解了)$",
    r"^(没|没有|不是|不对|不行|不要|别)$",
]


def _is_memory_query(text: str) -> Tuple[bool, float]:
    """判断文本是否包含记忆查询意图

    Returns:
      (is_query: bool, confidence: float)
    """
    # 快速排除：打招呼/简单确认
    for pat in NON_MEMORY_PATTERNS:
        if re.match(pat, text.strip(), re.IGNORECASE):
            return False, 0.0

    # 正向匹配
    max_conf = 0.0
    for pat in MEMORY_QUERY_PATTERNS:
        if re.search(pat, text):
            # 越长越精确的匹配给更高置信度
            conf = min(0.5 + len(pat) * 0.01, 0.95)
            max_conf = max(max_conf, conf)

    return max_conf > 0.3, max_conf


# ============================================================
# 核心：判定路由策略
# ============================================================

def _determine_strategy(keyword_result: dict, is_query: bool) -> Dict:
    """根据关键词解析结果决定路由策略

    Args:
      keyword_result: _detect_time_keywords() 的返回
      is_query: 是否为记忆查询

    Returns:
      策略字典
    """
    matched_type = keyword_result.get("matched_type")
    time_range = keyword_result.get("time_range")

    if not is_query or not matched_type:
        # 非记忆查询 → 走默认向量检索（轻量）
        return {
            "strategy": "vector",
            "time_range": None,
            "is_memory_query": False,
            "dag_search_params": None,
            "vector_search_params": {"depth": 5, "min_score": 0.4},
        }

    now = datetime.now(BEIJING_TZ)

    if matched_type == "just_now" or matched_type == "previous":
        # < 2小时 → 查 DAG + session 热RAM
        hours_back = 0.1 if matched_type == "just_now" else 2
        start = (now - timedelta(hours=hours_back)).isoformat()
        return {
            "strategy": "session",
            "time_range": {"start": start, "end": now.isoformat()},
            "is_memory_query": True,
            "dag_search_params": {
                "method": "time_range",
                "start": start,
                "end": now.isoformat(),
                "limit": 20,
            },
            "vector_search_params": {"depth": 3, "min_score": 0.5},
        }

    if matched_type in ("today", "yesterday", "day_before_yesterday",
                         "time_period", "specific_time", "n_ago", "recent_n"):
        # 有明确时间范围 → 查 DAG（精确时间范围）
        return {
            "strategy": "dag",
            "time_range": time_range,
            "is_memory_query": True,
            "dag_search_params": {
                "method": "time_range",
                "start": time_range["start"] if time_range else None,
                "end": time_range["end"] if time_range else None,
                "limit": 50,
            },
            "vector_search_params": None,  # 不用向量检索
        }

    # 无时间匹配但有记忆意图 → 向量检索（带时间衰减）
    return {
        "strategy": "vector",
        "time_range": None,
        "is_memory_query": True,
        "dag_search_params": {"method": "recent", "limit": 10},
        "vector_search_params": {"depth": 10, "min_score": 0.3},
    }


# ============================================================
# DAG 胶囊查询接口
# ============================================================

def query_dag(params: Dict) -> List[Dict]:
    """查询 DAG 胶囊数据库

    Args:
      params: {
        "method": "time_range" | "recent",
        "start": str (isoformat, time_range 模式),
        "end": str (isoformat, time_range 模式),
        "limit": int,
      }

    Returns:
      DAG 节点列表
    """
    if not os.path.exists(DAG_DB):
        return []

    import sqlite3
    try:
        conn = sqlite3.connect(DAG_DB)
        conn.row_factory = sqlite3.Row
        method = params.get("method", "recent")
        limit = params.get("limit", 20)

        if method == "time_range" and params.get("start") and params.get("end"):
            rows = conn.execute(
                "SELECT id, parent_id, turn_num, summary, message_preview, created_at "
                "FROM turns WHERE created_at >= ? AND created_at <= ? "
                "ORDER BY id ASC LIMIT ?",
                (params["start"], params["end"], limit)
            ).fetchall()
        else:  # recent
            rows = conn.execute(
                "SELECT id, parent_id, turn_num, summary, message_preview, created_at "
                "FROM turns ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "parent_id": r["parent_id"],
                "turn_num": r["turn_num"],
                "summary": r["summary"],
                "message_preview": r["message_preview"],
                "created_at": r["created_at"],
            })
        conn.close()
        return results
    except Exception as e:
        return []


def query_session_file_by_time(time_range: Dict, max_files: int = 3) -> List[Dict]:
    """按时间范围扫描原始 session 文件

    Args:
      time_range: {"start": iso_str, "end": iso_str}
      max_files: 最多翻的文件数

    Returns:
      匹配的 session 摘要列表
    """
    if not time_range:
        return []

    sessions_dir = os.path.join(
        os.environ.get("HOME", "/home/sandbox"),
        ".openclaw", "agents", "main", "sessions"
    )
    if not os.path.isdir(sessions_dir):
        return []

    try:
        start_ts = datetime.fromisoformat(time_range["start"]).timestamp()
        end_ts = datetime.fromisoformat(time_range["end"]).timestamp()
    except (ValueError, TypeError):
        return []

    results = []
    # 列出最近修改的 session 文件
    all_files = sorted(
        [f for f in os.listdir(sessions_dir) if f.endswith(".jsonl") and "lock" not in f],
        key=lambda f: os.path.getmtime(os.path.join(sessions_dir, f)),
        reverse=True
    )

    for fn in all_files[:max_files * 5]:  # 多取点以防 filter 后不够
        fp = os.path.join(sessions_dir, fn)
        mtime = os.path.getmtime(fp)
        if start_ts <= mtime <= end_ts:
            size_kb = os.path.getsize(fp) // 1024
            results.append({
                "filename": fn,
                "modified": datetime.fromtimestamp(mtime, tz=BEIJING_TZ).isoformat(),
                "size_kb": size_kb,
                "path": fp,
            })
        if len(results) >= max_files:
            break

    return results


# ============================================================
# Pipeline 阶段入口
# ============================================================

def run_stage57(result: dict, user_message: str) -> dict:
    """
    流水线阶段5.7：记忆路由

    在 stage6 (memory_align) 之前执行，提供精确的时间范围和路由策略。
    """
    t0 = time.monotonic()

    # 0. 前置过滤：打招呼/简单确认/通用问候 → 直接跳过低负荷向量
    stripped = user_message.strip()
    for pat in NON_MEMORY_PATTERNS:
        if re.match(pat, stripped, re.IGNORECASE):
            strategy = _determine_strategy(
                {"matched_type": None, "time_range": None, "confidence": 0.0, "raw_match": None},
                False
            )
            strategy["fallback_used"] = False
            strategy["keyword_match"] = {"matched_type": None, "time_range": None,
                                          "confidence": 0.0, "raw_match": None}
            strategy["query_confidence"] = 0.0
            strategy["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            strategy["greeting_skip"] = True
            strategy["dag_results"] = []
            strategy["dag_results_count"] = 0
            strategy["session_files"] = []
            result["memory_router"] = strategy
            return result

    # 1. 关键词降级检测
    keyword_result = _detect_time_keywords(user_message)

    # 2. 记忆查询意图检测
    is_query, query_confidence = _is_memory_query(user_message)

    # 3. 合并判断
    #    关键词置信度高（>=0.7）→ 以关键词为准
    #    关键词置信度低但有记忆意图 → 标记为记忆查询，走默认向量
    if keyword_result["confidence"] >= 0.7:
        use_fallback = True
        strategy = _determine_strategy(keyword_result, True)
        strategy["fallback_used"] = True
        strategy["keyword_match"] = keyword_result
    elif is_query:
        use_fallback = True
        strategy = _determine_strategy(keyword_result, True)
        strategy["fallback_used"] = True
        strategy["keyword_match"] = keyword_result
    else:
        # 正常对话，非记忆查询 → 走默认轻量向量
        use_fallback = False
        strategy = _determine_strategy(keyword_result, False)
        strategy["fallback_used"] = False
        strategy["keyword_match"] = keyword_result

    strategy["query_confidence"] = query_confidence
    strategy["elapsed_ms"] = int((time.monotonic() - t0) * 1000)

    # 4. 如果策略是 dag 或 session，预查询 DAG
    if strategy["strategy"] in ("dag", "session") and strategy.get("dag_search_params"):
        dag_results = query_dag(strategy["dag_search_params"])
        strategy["dag_results_count"] = len(dag_results)
        strategy["dag_results"] = dag_results[:10]  # 只保留前10条摘要
    else:
        strategy["dag_results_count"] = 0
        strategy["dag_results"] = []

    # 5. 如果策略是 session，查原始 session 文件
    if strategy["strategy"] == "session" and strategy.get("time_range"):
        session_files = query_session_file_by_time(strategy["time_range"])
        strategy["session_files"] = session_files
    else:
        strategy["session_files"] = []

    result["memory_router"] = strategy
    return result


# ============================================================
# 快速测试
# ============================================================

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
    test_cases = [
        "昨天的任务搞好了吗",
        "刚才我们聊什么了",
        "凌晨1点之后的事",
        "上周那件事怎么样了",
        "你还记得之前说的那个计划吗",
        "帮我查一下昨天凌晨的定时任务",
        "早上好",
        "5分钟前说的那个",
        "前天晚上处理的bug",
        "近3天的对话记录",
        "你好",
    ]
    for msg in test_cases:
        result = {"ts": datetime.now(BEIJING_TZ).isoformat()}
        result = run_stage57(result, msg)
        s = result["memory_router"]
        print(f"\n{'='*50}")
        print(f"输入: {msg}")
        print(f"  策略: {s['strategy']}")
        print(f"  时间范围: {s['time_range']}")
        print(f"  记忆查询: {s['is_memory_query']} (conf={s['query_confidence']:.2f})")
        print(f"  关键词匹配: {s['keyword_match']['matched_type']} (conf={s['keyword_match']['confidence']})")
        print(f"  降级: {s['fallback_used']}")
        print(f"  DAG 命中: {s['dag_results_count']} 条")
        print(f"  Session 文件: {len(s['session_files'])} 个")
