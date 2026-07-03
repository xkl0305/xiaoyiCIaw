#!/usr/bin/env python3
"""
migrate_yaoyao_to_celia.py — 将 yaoyao 存量数据迁移到 celia 数据库
迁移内容：
  1. yaoyao_meta 手动记忆 → celia mem_record
  2. chunks(source='memory') 文件分块 → celia mem_record
  3. chunks(source='sessions') 会话分块 → celia mem_record
"""
import json, os, sqlite3, sys, hashlib, time
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
TENANT_ID = "default"
USER_ID = "default"

YAOYAO_DB = os.path.expanduser("~/.openclaw/memory/main.sqlite")
CELIA_DB = os.path.join(WORKSPACE, "memory", "celia_memory", "celia_memory.db")

now_ms = int(time.time() * 1000)
stats = {"meta": 0, "memory_chunks": 0, "session_chunks": 0, "skipped": 0, "errors": 0}

def hash_content(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def insert_mem_record(cur, content, occurred_at_ms, memory_type=4, category=0, scene_tag=""):
    """插入一条记忆到 celia mem_record"""
    ch = hash_content(content)
    # 去重检查
    existing = cur.execute(
        "SELECT id FROM mem_record WHERE content_hash = ? AND user_id = ? AND deleted_at_ms = 0 LIMIT 1",
        (ch, USER_ID)
    ).fetchone()
    if existing:
        return False  # 已存在，跳过
    
    cur.execute("""
        INSERT INTO mem_record 
        (tenant_id, user_id, agent_id, agent_type, session_id, scope, category, 
         memory_type, confidence, content, extract_meta, scene_tag, slot_key,
         created_at_ms, updated_at_ms, occurred_at_ms, occurred_at_source,
         content_hash, ingest_source, stable_candidate, superseded_by,
         deleted_at_ms, delete_reason, row_version, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        TENANT_ID, USER_ID, "main", "system", None, 0, category,
        memory_type, 0.5, content, None, scene_tag, None,
        occurred_at_ms, now_ms, occurred_at_ms, 0,
        ch, 2, 1, None,  # ingest_source=2 (迁移)
        0, None, 0, 0
    ))
    return True

def migrate():
    # 连接 yaoyao 和 celia
    yaoyao = sqlite3.connect(YAOYAO_DB)
    yaoyao.row_factory = sqlite3.Row
    celia = sqlite3.connect(CELIA_DB)
    cur = celia.cursor()
    
    # 1. 迁移 yaoyao_meta（手动记忆，去除 ws: 开头的文件索引条目）
    rows = yaoyao.execute("""
        SELECT id, date, user_text, asst_text, importance, created_at
        FROM yaoyao_meta
        WHERE json_extract(meta, '$.superseded_by') IS NULL
          AND (user_text NOT LIKE '[ws:%' OR user_text IS NULL)
        ORDER BY id
    """).fetchall()
    
    for row in rows:
        try:
            content = (row["user_text"] or "") if row["user_text"] else (row["asst_text"] or "")
            if not content or len(content) < 10:
                stats["skipped"] += 1
                continue
            
            date_str = row["date"]
            occurred_at = int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ).timestamp() * 1000) if date_str else now_ms
            
            if insert_mem_record(cur, content, occurred_at, memory_type=4):
                stats["meta"] += 1
            else:
                stats["skipped"] += 1
        except Exception as e:
            print(f"  [ERROR] meta {row['id']}: {e}", file=sys.stderr)
            stats["errors"] += 1
    
    # 2. 迁移 chunks(source='memory') 文件分块
    rows = yaoyao.execute("""
        SELECT id, path, text, start_line, end_line
        FROM chunks
        WHERE source = 'memory'
        ORDER BY path, start_line
    """).fetchall()
    
    for row in rows:
        try:
            text = row["text"]
            if not text or len(text) < 20:
                stats["skipped"] += 1
                continue
            
            content = f"[来自 {row['path']} 第{row['start_line']}-{row['end_line']}行]\n{text}"
            occurred_at = now_ms
            
            if insert_mem_record(cur, content, occurred_at, memory_type=2, category=2, scene_tag="workspace_file"):
                stats["memory_chunks"] += 1
            else:
                stats["skipped"] += 1
        except Exception as e:
            print(f"  [ERROR] memory chunk {row['id']}: {e}", file=sys.stderr)
            stats["errors"] += 1
    
    # 3. 迁移 chunks(source='sessions') 会话分块
    rows = yaoyao.execute("""
        SELECT id, path, text
        FROM chunks
        WHERE source = 'sessions'
        ORDER BY id
    """).fetchall()
    
    for row in rows:
        try:
            text = row["text"]
            if not text or len(text) < 30:
                stats["skipped"] += 1
                continue
            
            content = text
            occurred_at = now_ms
            
            if insert_mem_record(cur, content, occurred_at, memory_type=1, category=1, scene_tag="conversation"):
                stats["session_chunks"] += 1
            else:
                stats["skipped"] += 1
        except Exception as e:
            print(f"  [ERROR] session chunk {row['id']}: {e}", file=sys.stderr)
            stats["errors"] += 1
    
    celia.commit()
    yaoyao.close()
    celia.close()
    
    print(f"\n✅ 迁移完成")
    print(f"   手动记忆: {stats['meta']} 条")
    print(f"   文件分块: {stats['memory_chunks']} 条")
    print(f"   会话分块: {stats['session_chunks']} 条")
    print(f"   跳过(重复/过短): {stats['skipped']} 条")
    print(f"   错误: {stats['errors']} 条")
    print(f"   总计入库: {stats['meta'] + stats['memory_chunks'] + stats['session_chunks']} 条")

if __name__ == "__main__":
    migrate()
