"""
基础 SQLite 持久化层，提供会话记忆、键值存储、事件日志。
所有文件读写使用 UTF-8 编码。
"""
import sqlite3
import json
import time
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent / 'data'
DB_PATH = DB_DIR / 'pigeonking.db'


def _ensure_db():
    """获取数据库连接，启用 WAL 模式。"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def init():
    """初始化数据库表结构。

    创建以下表（不存在则新建）：

    - kv_store: 通用键值存储
    - session_log: 事件日志（增删改查审计）
    - context_capsules: 上下文胶囊持久化
    - run_state: 运行时状态记录
    """
    conn = _ensure_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_data TEXT,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS context_capsules (
            session_id TEXT PRIMARY KEY,
            capsule TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
    ''')
    conn.commit()
    conn.close()


# ── 键值存储 ──────────────────────────────────────────────────────


def kv_get(key, default=None):
    """获取键值存储中的值。

    Args:
        key: 键名。
        default: 键不存在时的默认值。

    Returns:
        解析后的 Python 对象，或 default。
    """
    conn = _ensure_db()
    cur = conn.execute('SELECT value FROM kv_store WHERE key=?', (key,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else default


def kv_set(key, value):
    """设置键值存储中的值（插入或替换）。

    Args:
        key: 键名。
        value: 可 JSON 序列化的值。
    """
    conn = _ensure_db()
    conn.execute('INSERT OR REPLACE INTO kv_store VALUES (?,?,?)',
                 (key, json.dumps(value, ensure_ascii=False), time.time()))
    conn.commit()
    conn.close()


# ── 事件日志 ──────────────────────────────────────────────────────


def log_event(event_type, event_data=None):
    """记录一个事件到 session_log 表。

    Args:
        event_type: 事件类型标识（如 'goal_complete', 'error', 'model_switch'）。
        event_data: 可选的附加数据（字典或列表等可 JSON 序列化对象）。
    """
    conn = _ensure_db()
    conn.execute('INSERT INTO session_log (event_type, event_data, created_at) VALUES (?,?,?)',
                 (event_type, json.dumps(event_data, ensure_ascii=False) if event_data is not None else None, time.time()))
    conn.commit()
    conn.close()


def recent_events(limit=20):
    """获取最近的 N 条事件日志。

    Args:
        limit: 返回的最大条目数，默认 20。

    Returns:
        dict 列表，每条包含 id, type, data, time 字段。
    """
    conn = _ensure_db()
    cur = conn.execute(
        'SELECT id, event_type, event_data, created_at FROM session_log ORDER BY id DESC LIMIT ?',
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            'id': r[0],
            'type': r[1],
            'data': json.loads(r[2]) if r[2] else None,
            'time': r[3],
        }
        for r in rows
    ]


# ── 上下文胶囊 ────────────────────────────────────────────────────


def save_capsule(session_id, capsule):
    """保存上下文胶囊（插入或替换）。

    Args:
        session_id: 会话标识符。
        capsule: 可 JSON 序列化的胶囊数据（字典）。
    """
    conn = _ensure_db()
    now = time.time()
    conn.execute(
        'INSERT OR REPLACE INTO context_capsules VALUES (?,?,?,?)',
        (session_id, json.dumps(capsule, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()


def load_capsule(session_id):
    """加载指定会话的上下文胶囊。

    Args:
        session_id: 会话标识符。

    Returns:
        胶囊数据字典，或 None（不存在时）。
    """
    conn = _ensure_db()
    cur = conn.execute('SELECT capsule FROM context_capsules WHERE session_id=?', (session_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None
