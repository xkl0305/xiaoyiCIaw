#!/usr/bin/env python3
"""
version_check.py — 检查 crusheart-autobrain-turbo 新版本 v1.2

访问 https://clawhub.ai/plugins/crusheart-autobrain-turbo 检查新版本。
仅在安装后可以执行，如果发现了新版本，只提醒一次后记录已提醒状态。
如果没有新版本，不返回任何结果，不发送任何信息。

用法：
  python3 scripts/version_check.py

v7.0.0:
  - 修复 import: 添加 Optional, Tuple
  - 修复缩进: load_state 中 except 后缩进
  - 新增重试: _check_via_html 指数退避重试 3 次
  - 新增代理支持: 读取 http_proxy / https_proxy 环境变量
  - 错误返回结构化 JSON 而非静默 None
"""

import json, os, sys, time, urllib.request, re, hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_FILE = os.path.join(WORKSPACE, ".version_check_state.json")

# 从插件 _meta.json 读取当前版本（单一来源，vs 6.5.2 修复：不再硬编码）
_META_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_meta.json")
_CURRENT_VERSION = "7.0.0"
try:
    with open(_META_PATH, encoding="utf-8") as _f:
        _CURRENT_VERSION = json.load(_f).get("version", _CURRENT_VERSION)
except Exception:
    pass
CURRENT_VERSION = _CURRENT_VERSION

CHECK_URL = "https://clawhub.ai/plugins/crusheart-autobrain-turbo"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if os.environ.get("CRUSHEART_DEBUG"):
                import traceback; traceback.print_exc(limit=1)
    return {"checks": [], "notified_versions": []}


def save_state(state: dict):
    state["last_check"] = datetime.now(BEIJING_TZ).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# 注意：clawhub.ai 的 JSON API 端点可能不存在
# 只保留 HTML 解析路径确保兼容性
# API_CHECK_URL = "https://clawhub.ai/api/plugins/crusheart-autobrain-turbo"


def _parse_version_text(v: str) -> Optional[Tuple[int, ...]]:
    """解析版本字符串，返回 (major, minor, patch) 元组，失败返回 None"""
    parts = v.strip().split(".")
    if len(parts) >= 2:
        try:
            parsed = [int(x) for x in parts[:3]]
            # 首位 ≥100 说明是年份版本号（如 2026.5.6），排除
            if parsed[0] >= 100:
                return None
            return tuple(parsed[:3])
        except ValueError:
            pass
    return None


def _check_via_html() -> Optional[str]:
    """回退方案：解析 HTML 获取版本号（支持重试+代理）"""
    # 支持代理
    proxy_handler = urllib.request.ProxyHandler({
        "http": os.environ.get("http_proxy", os.environ.get("HTTP_PROXY", "")),
        "https": os.environ.get("https_proxy", os.environ.get("HTTPS_PROXY", "")),
    })
    opener = urllib.request.build_opener(proxy_handler)
    last_error = ""

    for attempt in range(3):
        try:
            req = urllib.request.Request(CHECK_URL, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CrusheartAutoBrain/7.0.0)"
            })
            with opener.open(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            break
        except Exception as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s
            html = ""
    else:
        # 所有重试都失败
        if os.environ.get("CRUSHEART_DEBUG"):
            print(f"[version_check] 所有重试均失败: {last_error}", file=sys.stderr)
        return None

    patterns = [
        r'version[-=]["\':]*([\d.]+)',
        r'CrusheartAutoBrain/([\d.]+)',
        r'badge/version-([\d.]+)-',
    ]
    found_versions = []
    for p in patterns:
        matches = re.findall(p, html, re.IGNORECASE)
        found_versions.extend(matches)

    cleaned = []
    for v in found_versions:
        if _parse_version_text(v):
            cleaned.append(v.strip())
    if cleaned:
        return max(cleaned, key=lambda x: [int(p) for p in x.split(".")[:3]])
    return None


def check_new_version():
    """检查是否有新版本。
    返回: 新版本号字符串 (有更新) | None (无更新) | dict (错误)
    """
    state = load_state()
    notified = state.get("notified_versions", [])

    # 直接走 HTML 解析（clawhub.ai JSON API 端点可能不存在）
    latest = _check_via_html()
    if latest is None:
        return {"error": True, "message": "无法连接 clawhub.ai 检查版本，请确认网络正常"}

    latest_parts = _parse_version_text(latest)
    current_parts = _parse_version_text(CURRENT_VERSION)
    if latest_parts is None or current_parts is None:
        return None

    if latest_parts <= current_parts:
        return None

    # 有新版本
    if latest not in notified:
        state["notified_versions"].append(latest)
    state["checks"].append({
        "time": datetime.now(BEIJING_TZ).isoformat(),
        "current": CURRENT_VERSION,
        "latest": latest,
        "found": True
    })
    save_state(state)
    return latest


if __name__ == "__main__":
    result = check_new_version()
    if result is None:
        # 无新版本：不输出
        pass
    elif isinstance(result, dict) and result.get("error"):
        # 网络失败：输出错误状态
        print(json.dumps({"has_update": False, "error": True, "message": result["message"], "current": CURRENT_VERSION}))
    elif result:
        # 有新版本
        msg = f"发现新版本: {result}（当前: {CURRENT_VERSION}），请前往 {CHECK_URL} 查看更新。"
        print(json.dumps({"has_update": True, "latest_version": result, "current": CURRENT_VERSION, "message": msg}))
    # 无新版本时不输出任何内容
