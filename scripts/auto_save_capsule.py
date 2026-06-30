#!/usr/bin/env python3
"""
auto_save_capsule.py — 自动保存会话胶囊 v2.0 (DAG化)

由 index.js 的 message:received 和 message:sent hooks 调用。
保存当前工作记忆到会话胶囊，确保进程重启后能恢复上下文。

v2.0 DAG化升级：
  - 新增 init_dag_db() — 初始化 SQLite DAG 存储
  - 新增 save_turn_dag() — 插入 DAG 节点
  - 新增 load_recent_dag() — 加载最近 N 条节点链
  - 修改 --context 模式：写入 flat 结构 + DAG 节点
  - 新增 --restore 参数：输出 DAG 链 JSON

用法：
  python3 scripts/auto_save_capsule.py                     # 保存
  python3 scripts/auto_save_capsule.py --context '...'     # 携带上下文保存
  python3 scripts/auto_save_capsule.py --load              # 读取胶囊（JSON 输出）
  python3 scripts/auto_save_capsule.py --restore [limit=5] # 读取 DAG 链
  python3 scripts/auto_save_capsule.py --status            # 状态检查
"""

import json, os, sys, sqlite3, hashlib, tempfile
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_ROOT = os.path.join(WORKSPACE, ".crusheart-state")
CAPSULE_FILE = os.path.join(STATE_ROOT, "context_capsule.json")
DAG_DB = os.path.join(STATE_ROOT, "context_capsule_dag.db")


# ── DAG 存储 ───────────────────────────────

def init_dag_db():
    """初始化 DAG 数据库（turns 表）"""
    os.makedirs(os.path.dirname(DAG_DB), exist_ok=True)
    db = sqlite3.connect(DAG_DB)
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                turn_num INTEGER NOT NULL DEFAULT 0,
                summary TEXT DEFAULT '',
                message_preview TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_turns_created_at
            ON turns(created_at DESC)
        """)
        db.commit()
    finally:
        db.close()


def save_turn_dag(parent_id, turn_num, summary="", preview=""):
    """插入一条 DAG 节点

    Args:
        parent_id: 父节点 ID（None 或 0 表示根节点）
        turn_num: 轮次编号
        summary: 节点摘要
        preview: 消息预览

    Returns:
        新节点的 ID
    """
    init_dag_db()
    db = sqlite3.connect(DAG_DB)
    try:
        cur = db.execute(
            "INSERT INTO turns (parent_id, turn_num, summary, message_preview, created_at) VALUES (?, ?, ?, ?, ?)",
            (parent_id, turn_num, (summary or "")[:500], (preview or "")[:200],
             datetime.now(BEIJING_TZ).isoformat())
        )
        node_id = cur.lastrowid
        db.commit()
        return node_id
    finally:
        db.close()


def load_recent_dag(limit=5):
    """加载最近 N 条节点链（按时间倒序）

    Args:
        limit: 最多返回条数

    Returns:
        节点列表 [{id, parent_id, turn_num, summary, message_preview, created_at}, ...]
    """
    init_dag_db()
    db = sqlite3.connect(DAG_DB)
    try:
        rows = db.execute(
            "SELECT id, parent_id, turn_num, summary, message_preview, created_at "
            "FROM turns ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "parent_id": row[1],
                "turn_num": row[2],
                "summary": row[3],
                "message_preview": row[4],
                "created_at": row[5],
            })
        return results
    finally:
        db.close()


def cleanup_dag_old(max_age_days=30):
    """清理超过指定天数的 DAG 节点

    Args:
        max_age_days: 保留天数（默认 30 天）
    """
    init_dag_db()
    db = sqlite3.connect(DAG_DB)
    try:
        cutoff = (datetime.now(BEIJING_TZ) - timedelta(days=max_age_days)).isoformat()
        db.execute("DELETE FROM turns WHERE created_at < ?", (cutoff,))
        db.commit()
    finally:
        db.close()


# ── 胶囊存储（flat 结构，兼容旧版）─────────

def load_capsule() -> dict:
    """读取胶囊内容，返回 dict（不存在则返回空字典）"""
    if not os.path.exists(CAPSULE_FILE):
        return {}
    try:
        with open(CAPSULE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_capsule(context: dict = None):
    """保存当前上下文快照 + DAG 节点

    保存内容：
      - 最后保存时间
      - 消息计数（从传入的 context 或上次状态继承）
      - 当前活跃主题
      - 活跃待办
      - 会话摘要
      - 同步写入 DAG 节点

    Args:
        context: 可选的上下文信息
    """
    os.makedirs(os.path.dirname(CAPSULE_FILE), exist_ok=True)

    # 读取上次胶囊
    existing = load_capsule()
    turn_count = existing.get("turn_count", 0) + 1
    last_node_id = existing.get("last_dag_node_id")

    # 提取摘要
    summary = ""
    preview = ""
    if context:
        summary = context.get("summary", "")
        if not summary and context.get("user_message"):
            summary = context["user_message"][:100]
        preview = context.get("turn_preview", "")
        if not preview and context.get("assistant_message"):
            preview = context["assistant_message"][:100]

    # 写入 DAG 节点
    dag_node_id = save_turn_dag(parent_id=last_node_id, turn_num=turn_count,
                                 summary=summary, preview=preview)

    # 当前胶囊内容
    topic = context.get("topic", "") if context else existing.get("topic", "")
    if not topic:
        # 尝试从消息提取主题
        user_msg = context.get("user_message", "") if context else ""
        preview_msg = preview or user_msg
        if preview_msg:
            topic = preview_msg[:60]
        else:
            topic = existing.get("topic", "general")

    capsule = {
        "last_saved": datetime.now(BEIJING_TZ).isoformat(),
        "turn_count": turn_count,
        "topic": (topic or "")[:120],
        "active_tasks": context.get("active_tasks", []) if context else existing.get("active_tasks", []),
        "summary": (summary or existing.get("summary", ""))[:1000],
        "last_dag_node_id": dag_node_id,
        "dag_db": DAG_DB,
    }

    with open(CAPSULE_FILE, "w", encoding="utf-8") as f:
        json.dump(capsule, f, indent=2, ensure_ascii=False)


# ── CLI 入口 ────────────────────────────

if __name__ == "__main__":
    if "--load" in sys.argv:
        capsule = load_capsule()
        print(json.dumps(capsule, indent=2, ensure_ascii=False) if capsule else json.dumps({"status": "empty"}))
        sys.exit(0)

    if "--restore" in sys.argv:
        limit = 5
        try:
            idx = sys.argv.index("--restore")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        except (ValueError, IndexError):
            pass
        dag_chain = load_recent_dag(limit=limit)
        print(json.dumps({"dag_chain": dag_chain, "source": DAG_DB}, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--status" in sys.argv:
        capsule = load_capsule()
        if capsule:
            print(f"📦 会话胶囊: 上次保存 {capsule.get('last_saved', '?')[:19]}")
            print(f"  消息轮次: {capsule.get('turn_count', 0)}")
            print(f"  活跃主题: {capsule.get('topic', '无')}")
            print(f"  最后 DAG 节点: {capsule.get('last_dag_node_id', '无')}")
            if capsule.get("active_tasks"):
                print(f"  待办: {len(capsule['active_tasks'])} 项")
        else:
            print("📦 会话胶囊: 空")
        sys.exit(0)

    # 支持 --context 参数传递 JSON 上下文
    context = None
    if "--context" in sys.argv:
        idx = sys.argv.index("--context") + 1
        if idx < len(sys.argv):
            try:
                context = json.loads(sys.argv[idx])
            except (json.JSONDecodeError, IndexError):
                pass

    save_capsule(context)
