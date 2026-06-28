"""
轻量运行时持久化：JSON 文件存储，支持读写当前会话上下文胶囊和用户偏好。

所有文件读写均使用 UTF-8 编码，JSON 写入使用 indent=2, ensure_ascii=False。
"""

import json
import os
from typing import Any, Optional

# ── 路径常量 ──────────────────────────────────────────────
_CONTEXT_STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".context_state",
)

_CAPSULE_PATH = os.path.join(_CONTEXT_STATE_DIR, "latest_capsule.json")
_PREFERENCES_PATH = os.path.join(_CONTEXT_STATE_DIR, "user_preferences.json")
_CONTINUITY_PATH = os.path.join(_CONTEXT_STATE_DIR, "session_continuity.json")

_JSON_KWARGS = {"indent": 2, "ensure_ascii": False}


# ── 内部工具 ──────────────────────────────────────────────
def _ensure_dir():
    os.makedirs(_CONTEXT_STATE_DIR, exist_ok=True)


def _read_json(path: str) -> dict:
    """读取 JSON 文件，不存在或损坏时返回空字典。"""
    _ensure_dir()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _read_json_list(path: str) -> list:
    """读取 JSON 数组文件，不存在或损坏时返回空列表。"""
    _ensure_dir()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_json(path: str, data: Any):
    """写入 JSON 文件。"""
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, **_JSON_KWARGS)


# ── 上下文胶囊 ────────────────────────────────────────────────────


def save_context_capsule(capsule: dict):
    """保存当前会话上下文胶囊到 latest_capsule.json。

    Args:
        capsule: 上下文胶囊字典，应包含 session_id、last_goal、user_preferences 等字段。
    """
    _write_json(_CAPSULE_PATH, capsule)


def load_context_capsule() -> dict:
    """加载当前会话上下文胶囊。

    Returns:
        上下文胶囊字典；如果文件不存在或损坏，返回空字典。
    """
    return _read_json(_CAPSULE_PATH)


# ── 用户偏好 ──────────────────────────────────────────────────────


def save_user_preference(key: str, value: Any):
    """保存或更新一条用户偏好。

    Args:
        key: 偏好键名。
        value: 偏好值（必须可 JSON 序列化）。
    """
    prefs = _read_json(_PREFERENCES_PATH)
    prefs[key] = value
    _write_json(_PREFERENCES_PATH, prefs)


def load_user_preferences() -> dict:
    """加载所有用户偏好。

    Returns:
        用户偏好字典；如果文件不存在或损坏，返回空字典。
    """
    return _read_json(_PREFERENCES_PATH)


# ── 会话连续性日志 ────────────────────────────────────────────────


def append_session_log(event: dict):
    """向会话连续性日志追加一条事件记录。

    Args:
        event: 事件字典，应包含至少一个 "event" 键和 "timestamp"。
    """
    events = _read_json_list(_CONTINUITY_PATH)
    events.append(event)
    _write_json(_CONTINUITY_PATH, events)


def get_recent_sessions(count: int = 5) -> list:
    """获取最近的 N 条会话日志条目。

    Args:
        count: 返回的最大条目数。

    Returns:
        最近的会话日志列表（按写入顺序，最新的在末尾）。
    """
    events = _read_json_list(_CONTINUITY_PATH)
    return events[-count:] if count > 0 else []


# ── convenience ────────────────────────────────────────────────────


def get_all_session_logs() -> list:
    """获取完整的会话连续性日志。"""
    return _read_json_list(_CONTINUITY_PATH)


def try_sync_to_db():
    """尝试将 JSON 持久化数据同步到 SQLite 数据库。

    当 storage 模块可用时，将当前上下文胶囊和用户偏好写入 SQLite。
    静默失败（模块未安装或导入错误时不抛出异常）。

    Returns:
        bool: 同步成功返回 True，否则返回 False。
    """
    try:
        from storage.db import kv_set, save_capsule  # type: ignore

        capsule = load_context_capsule()
        if capsule:
            save_capsule(capsule.get('session_id', 'default'), capsule)

        prefs = load_user_preferences()
        if prefs:
            kv_set('user_preferences', prefs)

        return True
    except Exception:
        return False
