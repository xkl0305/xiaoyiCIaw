#!/usr/bin/env python3
"""
memory_pipeline.py — 记忆全自动流水线传动轴 v1.0

职责：
  串联现有记忆组件（DAG / AutoMemory / VectorMemory / MemoryRouter），
  实现「对话→采集→分级→提炼→清理→搜索」全链路自动化。

记忆层级（全自动流水线）：
  L0 会话热RAM          OpenClaw 原生 session/jsonl（只读，不写）
  L1 DAG 胶囊节点        dag_context_manager.db（只读，不写）
  L2 短期记忆            AutoMemory（1~30天，到期自动评估）
  L3 长期记忆            AutoMemory（30~90天，高分巩固）
  L4 精华概要            AutoMemory（90天+，精简长存）
  🗑️ 删除                噪音/低分/过期

工作模式：
  run_incremental()    每 1h 或每次对话后调用，增量采集L0→L2
  run_maintenance()    每日凌晨调用，全链路整理+L2→L3→L4→清理

用法：
  from scripts.memory_pipeline import run_incremental, run_maintenance, search
"""

import json, os, sys, re, glob, hashlib, time, logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

logger = logging.getLogger("memory_pipeline")

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
AGENTS_DIR = os.environ.get("HOME", "/home/sandbox") + "/.openclaw/agents/main/sessions"

# ── Pipeline 自身状态 ──
STATE_ROOT = os.path.join(WORKSPACE, ".crusheart-state")
STATE_FILE = os.path.join(STATE_ROOT, "memory_pipeline_state.json")
DEFAULT_STATE = {
    "last_incremental": "",
    "last_maintenance": "",
    "processed_files": {},       # {filename: {"mtime": t, "count": n}}
    "total_collected": 0,        # 累计采集条数
    "total_pruned": 0,           # 累计清理条数
    "total_consolidated": 0,     # 累计巩固条数
}

# ── 评分/Pipeline 参数 ──
PRUNE_AGE_DAYS = 90             # 超过90天且低评分 → 删除
CONSOLIDATE_AGE_DAYS = 14       # 超过14天高分 → 巩固到长期
LOW_SCORE_THRESHOLD = 0.3       # 低于这个分的条目会被衰减
HIGH_SCORE_THRESHOLD = 0.7      # 高于这个分的条目入长期


SKIP_ROLES = {"toolResult", "tool", "system", "function"}

# ── 导入现有组件 ──
sys.path.insert(0, WORKSPACE)

_AUTOMEMORY = None
def _get_am():
    global _AUTOMEMORY
    if _AUTOMEMORY is None:
        from core.engines.memory.auto_memory import AutoMemory
        _AUTOMEMORY = AutoMemory()
    return _AUTOMEMORY

_DAG_MGR = None
def _get_dag():
    global _DAG_MGR
    if _DAG_MGR is None:
        from core.engines.memory.dag_context_manager import DAGContextManager
        _DAG_MGR = DAGContextManager(
            db_path=os.path.join(STATE_ROOT, "context_capsule_dag.db")
        )
    return _DAG_MGR


# ================================================================
# 状态管理
# ================================================================
def _load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_STATE)


def _save_state(state: Dict):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ================================================================
# 工具函数
# ================================================================
def _is_noise(content: str) -> bool:
    """判断是否为噪音内容（工具结果、系统日志等）"""
    if not content or not content.strip():
        return True
    text = content.strip()
    # JSON 工具结果
    stripped = text.strip()
    if (stripped.startswith("{") and "results" in stripped[:100]) or \
       (stripped.startswith("[") and len(stripped) > 200):
        return True
    # Python traceback / 代码内容
    if "Traceback (most recent call last)" in stripped:
        return True
    # SQL 查询结果/数据库内容
    if stripped.startswith("(") and "rows" in stripped[:80]:
        return True
    return False


def _extract_user_text(content: Any) -> str:
    """从 message content 中提取纯文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "toolUse":
                    # 跳过工具调用请求
                    continue
                elif item.get("type") == "toolResult":
                    continue
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts)
    return str(content)


def _score_content(text: str, role: str = "user") -> float:
    """给一段对话内容打分，决定它的记忆价值 (0~1)"""
    if not text or not text.strip():
        return 0.0
    score = 0.3  # 基础分

    # 用户说的话比机器人回复更有记忆价值
    if role == "user":
        score += 0.1

    # 长度加分（超过 20 字说明不是简单应答）
    length = len(text.strip())
    if length > 20:
        score += 0.1
    if length > 100:
        score += 0.1
    if length > 300:
        score += 0.1

    # 包含决策/指令/偏好关键词 → 重要
    importance_keywords = [
        "记住", "记一下", "我喜欢", "我不喜欢", "我要",
        "以后", "经常", "习惯", "不要", "必须", "记得",
        "我的名字", "我叫", "我是", "家住", "生日",
        "remember", "important", "note that", "my name",
    ]
    text_lower = text.lower()
    for kw in importance_keywords:
        if kw in text_lower:
            score += 0.2
            break

    # 包含问题/复杂内容 → 有点价值
    if "?" in text or "？" in text:
        score += 0.05
    if any(kw in text for kw in ["为什么", "怎么", "是什么", "啥", "哪个"]):
        score += 0.05

    # 纯工具结果/系统消息 → 低分
    if _is_noise(text):
        score = max(score, 0.1)

    return min(score, 1.0)


# ================================================================
# L0 → L1：从会话文件采集
# ================================================================
def collect_from_sessions(state: Dict, max_files: int = 10) -> Tuple[List[Dict], Dict]:
    """增量从 session jsonl 中读取新对话，返回消息列表"""
    if not os.path.isdir(AGENTS_DIR):
        return [], state

    all_files = sorted(
        [f for f in os.listdir(AGENTS_DIR) if f.endswith(".jsonl") and "lock" not in f
         and "reset" not in f and "trajectory" not in f],
        key=lambda f: os.path.getmtime(os.path.join(AGENTS_DIR, f)),
        reverse=True
    )

    processed = state.get("processed_files", {})
    messages = []

    for fn in all_files[:max_files]:
        fp = os.path.join(AGENTS_DIR, fn)
        mtime = os.path.getmtime(fp)
        cached = processed.get(fn)

        # 增量检查：文件名+mtime 没变就跳过
        if cached and cached.get("mtime") == mtime:
            continue

        # 文件太大跳过（超过 10MB 的文件不太适合全文解析）
        if os.path.getsize(fp) > 10 * 1024 * 1024:
            continue

        count = 0
        with open(fp, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 只处理 message 类型
                if entry.get("type") != "message":
                    continue
                msg = entry.get("message", {})
                role = msg.get("role", "")
                content = _extract_user_text(msg.get("content", ""))
                if not content or not content.strip():
                    continue
                if _is_noise(content):
                    continue

                ts = entry.get("timestamp", "")
                # 组装
                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": ts,
                    "session_file": fn,
                    "msg_id": entry.get("id", ""),
                })
                count += 1

        processed[fn] = {"mtime": mtime, "count": count}

    state["processed_files"] = processed
    return messages, state


# ================================================================
# L1 → L2：从 DAG 胶囊采集
# ================================================================
def collect_from_dag(state: Dict, session_key: str = "main") -> List[Dict]:
    """从 DAG 胶囊中读取待处理节点"""
    messages = []
    try:
        dag = _get_dag()
        # 获取最近的节点
        nodes = dag._get_session_nodes(session_key)
        if not nodes:
            return messages
        # 取最近 50 个节点
        for node in nodes[-50:]:
            if not node.content or not node.content.strip():
                continue
            if _is_noise(node.content):
                continue
            messages.append({
                "role": node.role,
                "content": node.content,
                "timestamp": "",  # DAG节点不一定有时间戳
                "session_file": "dag",
                "msg_id": node.node_id,
            })
    except Exception as e:
        logger.warning(f"DAG collection failed: {e}")
    return messages


# ================================================================
# L2 写入 AutoMemory（自动去重/固化）
# ================================================================
def integrate_to_short_term(messages: List[Dict]) -> Dict:
    """将采集到的消息写入 AutoMemory（L2），返回统计"""
    if not messages:
        return {"ingested": 0, "skipped": 0, "errors": 0}
    am = _get_am()
    stats = {"ingested": 0, "skipped": 0, "errors": 0}

    for msg in messages:
        try:
            # 跳过工具结果等角色
            if msg["role"] in SKIP_ROLES:
                stats["skipped"] += 1
                continue
            # 打分
            score = _score_content(msg["content"], msg["role"])
            # 低分内容跳过
            if score < 0.15:
                stats["skipped"] += 1
                continue
            # 生成标签
            tags = ["auto_collect", msg["role"]]
            today_tag = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
            tags.append(today_tag)

            scene = "对话记录"
            if msg["role"] == "assistant":
                scene = "助手回复"

            # 调用 AutoMemory.save() — 自带去重/固化逻辑
            am.save(
                text=msg["content"],
                tags=tags,
                scene=scene,
                metadata={
                    "source": "memory_pipeline",
                    "session_file": msg.get("session_file", ""),
                    "score": score,
                    "timestamp": msg.get("timestamp", ""),
                }
            )
            stats["ingested"] += 1
        except Exception as e:
            logger.error(f"ingest error: {e}")
            stats["errors"] += 1

    return stats


# ================================================================
# L2 → L3：蒸馏巩固
# ================================================================
def distill(state: Dict, max_process: int = 100) -> Dict:
    """
    评分蒸馏：
    高分条目 → 巩固到长期（L3）
    低分条目 → 衰减标记（L2内降权）
    过期清理 → 删除（L4+）
    """
    am = _get_am()
    stats = {"promoted": 0, "decayed": 0, "pruned": 0, "errors": 0}

    try:
        # 取所有记忆条目
        entries = am.list_all()
        if not entries:
            return stats

        now = datetime.now(BEIJING_TZ)
        cutoff_long = now - timedelta(days=CONSOLIDATE_AGE_DAYS)
        cutoff_prune = now - timedelta(days=PRUNE_AGE_DAYS)

        for entry in entries[:max_process]:
            mid = entry.get("id") or entry.get("mid")
            if not mid:
                continue
            try:
                # 解析时间
                created_raw = entry.get("created_at", entry.get("created", ""))
                if created_raw:
                    try:
                        created = datetime.fromisoformat(created_raw)
                    except (ValueError, TypeError):
                        created = now
                else:
                    created = now
                age_days = (now - created).days

                # 获取权重/评分
                weight = entry.get("weight", 1.0) or 1.0
                if isinstance(weight, str):
                    weight = float(weight)
                tags_raw = entry.get("tags", "[]")
                if isinstance(tags_raw, str):
                    tags = json.loads(tags_raw) if tags_raw.startswith("[") else []
                else:
                    tags = tags_raw or []
                tags_set = set(tags) if isinstance(tags, list) else set()

                # 系统/自动标记的条目跳过（不主动删除）
                if "system" in tags_set or "core_anchor" in tags_set:
                    continue

                # 高评分 + 够老 → 巩固到长期
                if weight >= HIGH_SCORE_THRESHOLD and age_days >= 7:
                    am.force_consolidate(mid, "long_term")
                    stats["promoted"] += 1
                    continue

                # 超久远 + 低分 → 删除
                if age_days >= PRUNE_AGE_DAYS and weight < LOW_SCORE_THRESHOLD:
                    am.remove(mid)
                    stats["pruned"] += 1
                    continue

                # 低分 + 够老 → 衰减
                if age_days >= CONSOLIDATE_AGE_DAYS and weight < LOW_SCORE_THRESHOLD:
                    am.decay_policy(age_days, is_anchor=False)
                    stats["decayed"] += 1

            except Exception as e:
                logger.warning(f"distill entry {mid[:12]}: {e}")
                stats["errors"] += 1

    except Exception as e:
        logger.error(f"distill error: {e}")

    return stats


# ================================================================
# 联合搜索（时间+关键词精准路由）
# ================================================================
def search(query: str, time_range: Optional[Dict] = None,
           top_k: int = 10) -> List[Dict]:
    """
    智能搜索：根据时间范围自动路由到对应层级

    Args:
      query: 搜索关键词
      time_range: {"start": iso_str, "end": iso_str} | None
      top_k: 最大返回数

    Returns:
      搜索结果列表，按相关性排序
    """
    am = _get_am()

    # 有时间范围 → 先用 timeline 搜索
    if time_range:
        try:
            result = am.search_with_timeline(query)
            if isinstance(result, dict) and "timeline" in result:
                # 过滤时间范围
                filtered = []
                for item in result.get("timeline", []):
                    ts = item.get("timestamp", "")
                    if ts:
                        try:
                            t = datetime.fromisoformat(ts)
                            start = datetime.fromisoformat(time_range["start"])
                            end = datetime.fromisoformat(time_range["end"])
                            if start <= t <= end:
                                filtered.append(item)
                        except (ValueError, KeyError):
                            filtered.append(item)
                    else:
                        filtered.append(item)
                return filtered[:top_k]
        except Exception:
            pass

    # 无时间范围或 timeline 失败 → 语义搜索
    try:
        results = am.search(query, budget_tokens=200)
        if isinstance(results, list):
            return results[:top_k]
    except Exception:
        pass

    return []


# ================================================================
# 增量采集（对话后或每小时调用）
# ================================================================
def run_incremental(max_files: int = 5) -> Dict:
    """增量采集 L0→L2，适合每小时或每次对话后调用"""
    state = _load_state()
    report = {"status": "ok", "steps": {}}

    # Step 1: 从 session 文件采集
    session_msgs, state = collect_from_sessions(state, max_files=max_files)
    report["steps"]["session_collect"] = {
        "files_scanned": len(state.get("processed_files", {})),
        "messages_found": len(session_msgs),
    }

    # Step 2: 从 DAG 采集
    dag_msgs = collect_from_dag(state)
    report["steps"]["dag_collect"] = {"messages_found": len(dag_msgs)}

    # Step 3: 合并写入 L2
    all_msgs = session_msgs + dag_msgs
    ingested = integrate_to_short_term(all_msgs)
    report["steps"]["integrate"] = ingested

    # 更新总计数
    state["total_collected"] = state.get("total_collected", 0) + ingested.get("ingested", 0)
    state["last_incremental"] = datetime.now(BEIJING_TZ).isoformat()
    _save_state(state)

    if all_msgs:
        report["summary"] = f"采集 {len(all_msgs)} 条对话，ingest {ingested['ingested']} 条"
    else:
        report["summary"] = "无新对话需要采集"
    return report


# ================================================================
# 全链路维护（每日凌晨）
# ================================================================
def run_maintenance() -> Dict:
    """全链路整理：采集 + 蒸馏 + 巩固 + 清理 + 统计"""
    state = _load_state()
    report = {"status": "ok", "steps": {}}

    # 1. 先增量采集
    inc = run_incremental(max_files=20)
    report["steps"]["incremental"] = inc

    # 2. 蒸馏巩固
    dist = distill(state, max_process=500)
    report["steps"]["distill"] = dist

    # 更新总计数
    state["total_consolidated"] = state.get("total_consolidated", 0) + dist.get("promoted", 0)
    state["total_pruned"] = state.get("total_pruned", 0) + dist.get("pruned", 0)
    state["last_maintenance"] = datetime.now(BEIJING_TZ).isoformat()
    _save_state(state)

    # 输出摘要
    summary_parts = []
    if inc.get("steps", {}).get("integrate", {}).get("ingested", 0):
        summary_parts.append(f"采集 {inc['steps']['integrate']['ingested']} 条")
    else:
        summary_parts.append("无新对话")
    if dist.get("promoted"):
        summary_parts.append(f"巩固 {dist['promoted']} 条到长期")
    if dist.get("pruned"):
        summary_parts.append(f"清理 {dist['pruned']} 条过期记忆")
    if dist.get("decayed"):
        summary_parts.append(f"衰减 {dist['decayed']} 条低分记忆")
    report["summary"] = " | ".join(summary_parts)

    # 系统记忆状态快照
    try:
        am = _get_am()
        s = am.stats()
        report["memory_stats"] = {
            "total": s.get("total", 0),
            "db_size_kb": s.get("db_size_kb", 0),
        }
    except Exception:
        pass

    report["status"] = "completed"
    return report


# ================================================================
# 状态查询
# ================================================================
def get_status() -> Dict:
    """获取 Pipeline 状态摘要"""
    state = _load_state()
    try:
        am = _get_am()
        mem_stats = am.stats()
    except Exception:
        mem_stats = {}

    return {
        "pipeline": {
            "last_incremental": state.get("last_incremental", "从未"),
            "last_maintenance": state.get("last_maintenance", "从未"),
            "total_collected": state.get("total_collected", 0),
            "total_pruned": state.get("total_pruned", 0),
            "total_consolidated": state.get("total_consolidated", 0),
        },
        "memory_db": {
            "total_entries": mem_stats.get("total", 0),
            "size_kb": mem_stats.get("db_size_kb", 0),
        },
        "processed_files": len(state.get("processed_files", {})),
    }


# ================================================================
# CLI
# ================================================================
if __name__ == "__main__":
    import sys
    if "--inc" in sys.argv or "--incremental" in sys.argv:
        report = run_incremental()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif "--full" in sys.argv or "--maintenance" in sys.argv:
        report = run_maintenance()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif "--status" in sys.argv:
        st = get_status()
        print(json.dumps(st, indent=2, ensure_ascii=False))
    elif "--search" in sys.argv:
        q = sys.argv[sys.argv.index("--search") + 1] if "--search" in sys.argv else ""
        results = search(q)
        for r in results[:5]:
            print(f"  [{r.get('id','?')[:12]}] {str(r.get('content',''))[:100]}")
    else:
        print("用法:")
        print("  python3 scripts/memory_pipeline.py --inc          # 增量采集")
        print("  python3 scripts/memory_pipeline.py --full         # 全链路维护")
        print("  python3 scripts/memory_pipeline.py --status       # 状态查询")
        print("  python3 scripts/memory_pipeline.py --search <q>   # 搜索")
