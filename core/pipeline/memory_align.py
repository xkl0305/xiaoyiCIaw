"""
Crusheart Agent OS — 流水线阶段6：记忆对齐
使用 AutoMemory + MemoryRouter 实现智能记忆检索

v7.1 升级：
  - 阶段5.7（MemoryRouter）提供路由策略后，本阶段按策略执行
  - 策略=session → 查 DAG + session 热RAM
  - 策略=dag → 直接查 DAG 胶囊
  - 策略=vector → 走向量检索（轻量）
  - 不再暴力搜索全量记忆
"""

import sys, os

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)


def run_stage6(result: dict, user_message: str) -> dict:
    """记忆对齐 — 根据 MemoryRouter 策略选择检索方式"""
    router = result.get("memory_router", {})

    # ── 问候/非记忆查询 → 跳过检索 ──
    if router.get("greeting_skip") or not router.get("is_memory_query", False):
        result["memory_alignment"] = {
            "status": "skipped",
            "reason": "非记忆查询，跳过检索",
            "strategy": router.get("strategy", "skip"),
        }
        return result

    strategy = router.get("strategy", "vector")

    # ── 策略1: session / dag — 直接从 DAG 摘结果 ──
    if strategy in ("session", "dag"):
        dag_results = router.get("dag_results", [])
        session_files = router.get("session_files", [])

        similar = []
        for d in dag_results:
            similar.append({
                "text": d.get("summary", "") or d.get("message_preview", ""),
                "score": 0.95,
                "source": "dag",
                "created_at": d.get("created_at", ""),
                "turn_num": d.get("turn_num", 0),
            })

        result["memory_alignment"] = {
            "status": "ready",
            "similar_found": len(similar),
            "strategy": strategy,
            "top_hit": similar[0].get("text", "")[:50] if similar else "",
            "session_files_found": len(session_files),
            "budget_tokens": 0,
            "depth": len(similar),
            "min_score": 0.9,
        }
        result["_memory_retrieval"] = {
            "results": similar,
            "source": strategy,
        }
        return result

    # ── 策略2: vector — 向量检索（轻量，受路由层预算控制） ──
    try:
        from core.engines.memory.auto_memory import AutoMemory
        mem = AutoMemory()

        # 路由层参数
        vector_params = router.get("vector_search_params", {})
        depth = vector_params.get("depth", 5)
        min_score = vector_params.get("min_score", 0.4)

        # 策略层参数（兼容旧配置）
        context_policy = result.get("context_policy", {})
        recall = context_policy.get("recall", {})
        budget_tokens = context_policy.get("budget_tokens", 400)
        load_core_anchor = recall.get("load_core_anchor", False)

        results = mem.search(
            user_message,
            budget_tokens=budget_tokens,
            load_core_anchor=load_core_anchor,
        )
        similar = [
            r for r in results
            if isinstance(r, dict) and r.get("score", 0) >= min_score
        ][:depth]

        result["memory_alignment"] = {
            "status": "ready",
            "similar_found": len(similar),
            "strategy": strategy,
            "top_hit": similar[0].get("text", "")[:50] if similar else "",
            "budget_tokens": budget_tokens,
            "depth": depth,
            "min_score": min_score,
        }
        result["_memory_retrieval"] = {
            "results": similar,
            "source": "vector",
        }
    except Exception as e:
        result["memory_alignment"] = {
            "status": "error",
            "strategy": strategy,
            "msg": str(e)[:80],
            "budget_tokens": 400,
        }

    return result
