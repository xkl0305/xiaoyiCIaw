"""
Crusheart Agent OS — 核心 SQLite 存储引擎
替换 JSON 文件存储，提供事务安全 + FTS5 全文索引
"""

import os, json, sqlite3, hashlib, time, re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
DB_PATH = os.path.join(WORKSPACE, ".crusheart.db")


def _now() -> str:
    return datetime.now(BEIJING_TZ).isoformat()


def _id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


"""
TTL 缓存混合 — 避免频繁系统调用（移植自 Hermes Agent）
"""
import time
import threading

class TTLCacheMixin:
    """TTL 缓存 — 避免频繁系统调用"""
    def __init__(self, default_ttl=30.0):
        self._ttl = default_ttl
        self._c = {}
        self._lk = threading.Lock()

    def cache_get(self, k):
        with self._lk:
            e = self._c.get(k)
            if e is None:
                return None
            v, ex = e
            if time.monotonic() >= ex:
                del self._c[k]
                return None
            return v

    def cache_set(self, k, v, ttl=None):
        ttl = ttl or self._ttl
        with self._lk:
            self._c[k] = (v, time.monotonic() + ttl)

    def cache_cc(self, k, fn, ttl=None):
        """cache_cc = Cache-or-Compute"""
        c = self.cache_get(k)
        if c is not None:
            return c
        try:
            r = fn()
            self.cache_set(k, r, ttl)
            return r
        except Exception:
            return None

    def cache_inv(self, k=None):
        with self._lk:
            if k:
                self._c.pop(k, None)
            else:
                self._c.clear()

    def cache_size(self):
        with self._lk:
            return len(self._c)


class CrusheartDB(TTLCacheMixin):
    """
    四表存储引擎：
    - memories + memories_fts: 记忆条目 + FTS5全文索引
    - sessions: 会话记录
    - evolution_log: 进化日志
    - implicit_preferences: 隐式偏好
    """

    def __init__(self, db_path: str = DB_PATH):
        super().__init__()
        self.db_path = db_path
        self._conn = None
        self._init_schema()

    # ---------- 连接管理 ----------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")  # 5s 等待防 SQLITE_BUSY
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ---------- 建表 ----------

    SCHEMA_VERSION = 1  # 当前 Schema 版本号

    def _init_schema(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                scene TEXT DEFAULT '',
                weight REAL DEFAULT 1.0,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, tags, scene,
                tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                summary TEXT DEFAULT '',
                message_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evolution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                trigger_type TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                reward REAL DEFAULT 0.0,
                context TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS implicit_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                signal TEXT NOT NULL,
                context TEXT DEFAULT '',
                user_response TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS background_tasks (
                task_id TEXT PRIMARY KEY,
                label TEXT DEFAULT '',
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                subagent_session_id TEXT DEFAULT '',
                task_type TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                heartbeat_at TEXT NOT NULL,
                completed_at TEXT DEFAULT NULL,
                result TEXT DEFAULT '{}',
                error TEXT DEFAULT ''
            );
        """)
        self.conn.commit()
        self._run_migrations()

    def _get_schema_version(self) -> int:
        """获取当前数据库 Schema 版本号"""
        try:
            row = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row:
                return int(row["value"])
        except Exception:
            pass
        return 0

    def _set_schema_version(self, version: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (str(version),)
        )
        self.conn.commit()

    def _run_migrations(self):
        """按版本号增量执行 Schema 迁移"""
        current = self._get_schema_version()
        c = self.conn

        # 迁移 0 → 1: 初始版本，无需操作
        if current < 1:
            # v1 没有额外变更
            self._set_schema_version(1)
            current = 1

        # 未来版本示例：
        # if current < 2:
        #     c.execute("ALTER TABLE memories ADD COLUMN ...")
        #     self._set_schema_version(2)

    # ---------- 记忆 CRUD ----------

    def save_memory(self, content: str, tags: List[str] = None,
                    scene: str = "", weight: float = 1.0,
                    metadata: dict = None,
                    mid: str = None,
                    _auto_commit: bool = True) -> str:
        if mid is None:
            mid = _id(content)
        now = _now()
        tags_str = ",".join(tags) if tags else ""
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        self.conn.execute(
            "INSERT OR REPLACE INTO memories (id, content, tags, scene, weight, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, content, tags_str, scene, weight, meta_str, now, now)
        )
        # 同步 FTS（独立表）
        self.conn.execute(
            "INSERT OR REPLACE INTO memories_fts(rowid, content, tags, scene) "
            "VALUES ((SELECT rowid FROM memories WHERE id = ?), ?, ?, ?)",
            (mid, content, tags_str, scene)
        )
        if _auto_commit:
            self.conn.commit()
        return mid

    def get_memory(self, mid: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (mid,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def update_memory(self, mid: str, **kwargs):
        fields = []
        vals = []
        for k, v in kwargs.items():
            if k in ("content", "tags", "scene", "weight", "metadata"):
                fields.append(f"{k} = ?")
                if k == "tags" and isinstance(v, list):
                    v = ",".join(v)
                vals.append(v)
        if not fields:
            return
        vals.append(_now())
        self.conn.execute(
            f"UPDATE memories SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
            (*vals, mid)
        )
        # 同步 FTS
        if "content" in kwargs or "tags" in kwargs or "scene" in kwargs:
            m = self.get_memory(mid)
            if m:
                self.conn.execute(
                    "INSERT OR REPLACE INTO memories_fts(rowid, content, tags, scene) "
                    "VALUES ((SELECT rowid FROM memories WHERE id = ?), ?, ?, ?)",
                    (mid, m["content"], m["tags"], m["scene"])
                )
        self.conn.commit()

    def remove_memory(self, mid: str) -> bool:
        row = self.conn.execute("SELECT rowid FROM memories WHERE id = ?", (mid,)).fetchone()
        if row:
            self.conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (row["rowid"],))
        c = self.conn.execute("DELETE FROM memories WHERE id = ?", (mid,))
        self.conn.commit()
        return c.rowcount > 0

    def list_memories(self, limit: int = 100, offset: int = 0) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]

    def memory_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()
        return row["c"] if row else 0

    # ---------- FTS5 全文搜索 ----------

    def search_memories(self, query: str, top_n: int = 10) -> List[dict]:
        """
        FTS5 全文搜索（中文优化版）。
        返回按 BM25/LIKE 排序的记忆条目。
        """
        if not query.strip():
            return []

        has_cjk = bool(re.search(r'[\u4e00-\u9fff]', query))

        if has_cjk:
            # 中文：拆分成多个词语各自 LIKE 匹配，取并集
            # 按空格拆分，无空格则拆成2字以上词条
            terms = [t.strip() for t in query.replace(',', ' ').split() if len(t.strip()) >= 2]
            if not terms:
                # 无分隔符时把连续中文拆成2字滑动窗口
                cjk_text = ''.join(re.findall(r'[\u4e00-\u9fff]+', query))
                terms = set()
                for i in range(len(cjk_text) - 1):
                    terms.add(cjk_text[i:i+2])
                terms = [t for t in terms if len(t) >= 2]
            if not terms:
                terms = [query[:4]]

            # 构建多条件 OR 查询，转义 LIKE 通配符
            conditions = ' OR '.join(['content LIKE ?'] * len(terms))
            params = [f'%{re.escape(t)}%' for t in terms]
            sql = f"SELECT DISTINCT m.* FROM memories m WHERE {conditions} ORDER BY m.weight DESC LIMIT ?"
            params.append(top_n)
            try:
                rows = self.conn.execute(sql, params).fetchall()
            except Exception:
                like_q = f"%{query}%"
                rows = self.conn.execute(
                    "SELECT * FROM memories WHERE content LIKE ? OR tags LIKE ? OR scene LIKE ? LIMIT ?",
                    (like_q, like_q, like_q, top_n)
                ).fetchall()
        else:
            # 英文/数字：走 FTS5 BM25
            sql = """
                SELECT m.*, rank
                FROM memories_fts f
                JOIN memories m ON f.rowid = m.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            try:
                fts_query = query if len(query.split()) <= 1 else " OR ".join(query.split())
                rows = self.conn.execute(sql, (fts_query, top_n)).fetchall()
            except sqlite3.OperationalError:
                like_q = f"%{query}%"
                rows = self.conn.execute(
                    "SELECT * FROM memories WHERE content LIKE ? OR tags LIKE ? OR scene LIKE ? LIMIT ?",
                    (like_q, like_q, like_q, top_n)
                ).fetchall()
        return [dict(r) for r in rows]

    def _sync_fts(self):
        """
        重建 FTS5 索引（增量同步用 INSERT OR REPLACE，但 FTS5 content sync 需要重建）
        这里用 DELETE+INSERT，小数据量可以接受
        """
        self.conn.execute("DELETE FROM memories_fts")
        self.conn.execute("""
            INSERT INTO memories_fts(rowid, content, tags, scene)
            SELECT rowid, content, tags, scene FROM memories
        """)

    # ---------- 会话 ----------

    def save_session(self, session_id: str, summary: str = "", count: int = 1):
        now = _now()
        existing = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE sessions SET summary = ?, message_count = message_count + ?, updated_at = ? WHERE session_id = ?",
                (summary or existing["summary"], count, now, session_id)
            )
        else:
            self.conn.execute(
                "INSERT INTO sessions (session_id, summary, message_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, summary, count, now, now)
            )
        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    # ---------- 进化日志 ----------

    def save_evolution(self, trigger_type: str, status: str = "pending",
                       reward: float = 0.0, context: str = "",
                       metadata: dict = None) -> int:
        c = self.conn.execute(
            "INSERT INTO evolution_log (timestamp, trigger_type, status, reward, context, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), trigger_type, status, reward, context,
             json.dumps(metadata or {}, ensure_ascii=False))
        )
        self.conn.commit()
        return c.lastrowid

    def list_evolution(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM evolution_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def evolution_stats(self) -> dict:
        row = self.conn.execute("""
            SELECT COUNT(*) as total,
                   AVG(reward) as avg_reward,
                   SUM(CASE WHEN status='applied' THEN 1 ELSE 0 END) as applied_count
            FROM evolution_log
        """).fetchone()
        return dict(row) if row else {"total": 0, "avg_reward": 0.0, "applied_count": 0}

    # ---------- 隐式偏好 ----------

    def save_preference(self, signal: str, context: str = "", user_response: str = ""):
        self.conn.execute(
            "INSERT INTO implicit_preferences (timestamp, signal, context, user_response) VALUES (?, ?, ?, ?)",
            (_now(), signal, context[:200], user_response[:200])
        )
        self.conn.commit()

    def list_preferences(self, limit: int = 10) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM implicit_preferences ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 维护 ----------

    def optimize(self):
        """定期维护：重建索引、vacuum"""
        self.conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        self.conn.execute("PRAGMA optimize")
        self.conn.commit()

    def stats(self) -> dict:
        return {
            "memories": self.memory_count(),
            "sessions": self.conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"],
            "evolution_logs": self.conn.execute("SELECT COUNT(*) as c FROM evolution_log").fetchone()["c"],
            "preferences": self.conn.execute("SELECT COUNT(*) as c FROM implicit_preferences").fetchone()["c"],
            "db_size_kb": os.path.getsize(self.db_path) / 1024 if os.path.exists(self.db_path) else 0,
        }

    # ---------- 迁移：从 JSON 导入 ----------

    def migrate_from_json(self, json_path: str, table: str = "memories") -> int:
        """
        从 JSON 文件导入记忆数据。
        json_path: JSON 文件路径
        table: "memories" / "evolution_log"
        返回导入条数
        """
        if not os.path.exists(json_path):
            return 0
        with open(json_path) as f:
            data = json.load(f)
        count = 0

        if table == "memories":
            entries = data.get("entries", data.get("data", data.get("memories", [])))
            if isinstance(entries, list):
                for ent in entries:
                    content = ent.get("content") or ent.get("text") or ""
                    if not content:
                        continue
                    self.save_memory(
                        content=content,
                        tags=ent.get("tags", []),
                        scene=ent.get("scene", ""),
                        weight=ent.get("weight", 1.0),
                        metadata=ent.get("metadata", {})
                    )
                    count += 1
        elif table == "evolution_log":
            learnings = data.get("learnings", []) + data.get("experiences", [])
            for l in learnings:
                self.save_evolution(
                    trigger_type=",".join(l.get("triggered_by", [])),
                    status=l.get("status", "pending"),
                    reward=l.get("reward", 0.0),
                    context=l.get("context", "")[:200],
                    metadata=l
                )
                count += 1

        return count

    def cleanup_background_tasks(self, max_age_days: int = 30) -> int:
        """清理已完成超过 max_age_days 天的后台任务记录"""
        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        cursor = self.conn.execute(
            "DELETE FROM background_tasks WHERE completed_at IS NOT NULL AND completed_at < ?",
            (cutoff,)
        )
        self.conn.commit()
        return cursor.rowcount


# ---------- 单例 ----------

def get_db() -> CrusheartDB:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(CrusheartDB)

def migrate_all():
    """从现有 JSON 文件迁移全部数据"""
    db = get_db()
    total = 0
    # 记忆数据
    mem_path = os.path.join(WORKSPACE, ".memory_store.json")
    n = db.migrate_from_json(mem_path, "memories")
    print(f"  迁移记忆: {n} 条")
    total += n
    # 进化日志
    ev_path = os.path.join(WORKSPACE, ".evolution_log.json")
    n = db.migrate_from_json(ev_path, "evolution_log")
    print(f"  迁移进化日志: {n} 条")
    total += n
    print(f"  总计迁移: {total} 条")
    return total
