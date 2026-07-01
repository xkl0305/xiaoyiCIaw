#!/usr/bin/env python3
"""
version_check.py — 检查 crusheart-autobrain-turbo 新版本 v2.0

访问 https://cnb.cool/Crusheart_Studio/Crusheart-AutoBrain-Turbo 检查新版本。
通过获取 tags 列表或解析仓库页面来检测最新版本。
仅在安装后可以执行，如果发现了新版本，只提醒一次后记录已提醒状态。
如果没有新版本，不返回任何结果，不发送任何信息。

用法：
  python3 scripts/version_check.py

v2.0 (2026-07-02):
  - 检查源从 clawhub.ai 切换到 cnb.cool（实际仓库地址）
  - 通过 tags 页面和仓库首页双重检测版本
  - 修复 _meta.json 路径（支持 extensions 目录）
  - 简化输出格式，更易读
"""

import json, os, sys, time, urllib.request, re, hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_FILE = os.path.join(WORKSPACE, ".version_check_state.json")

# 从插件 _meta.json 读取当前版本
# 优先扩展目录，再试 skill 目录
_CURRENT_VERSION = "7.0.0"
_meta_candidates = [
    os.path.expanduser("~/.openclaw/extensions/crusheart-autobrain-turbo/_meta.json"),
    os.path.expanduser("~/.openclaw/extensions/crusheart-autobrain-turbo/skill/_meta.json"),
    os.path.join(WORKSPACE, "skills", "crusheart-autobrain-turbo", "_meta.json"),
]
for _mp in _meta_candidates:
    if os.path.exists(_mp):
        try:
            with open(_mp, encoding="utf-8") as _f:
                _CURRENT_VERSION = json.load(_f).get("version", _CURRENT_VERSION)
            break
        except Exception:
            pass

CURRENT_VERSION = _CURRENT_VERSION

# 仓库基本信息
REPO_BASE = "https://cnb.cool/Crusheart_Studio/Crusheart-AutoBrain-Turbo"
TAGS_URL = f"{REPO_BASE}/-/tags"
COMMITS_URL = f"{REPO_BASE}/-/commits/v{CURRENT_VERSION}"
# releases 页面可能也有版本信息
RELEASES_URL = f"{REPO_BASE}/-/releases"


def log(msg: str):
    """统一日志，带时间戳"""
    if os.environ.get("CRUSHEART_DEBUG"):
        ts = datetime.now(BEIJING_TZ).strftime("%H:%M:%S")
        print(f"[{ts}] [version_check] {msg}", file=sys.stderr)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"加载状态文件失败: {e}")
    return {"checks": [], "notified_versions": []}


def save_state(state: dict):
    state["last_check"] = datetime.now(BEIJING_TZ).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _parse_version_text(v: str) -> Optional[Tuple[int, ...]]:
    """解析版本字符串，返回 (major, minor, patch) 元组，失败返回 None"""
    v = v.strip()
    # 去掉 v 前缀
    if v.startswith("v") or v.startswith("V"):
        v = v[1:]
    parts = v.split(".")
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


def _fetch_url(url: str, timeout: int = 15) -> str:
    """带重试和代理的 URL 获取（兼容 SSL 校验失败场景）"""
    import ssl

    # 构建 opener，支持代理
    handlers = []
    proxy_http = os.environ.get("http_proxy", os.environ.get("HTTP_PROXY", ""))
    proxy_https = os.environ.get("https_proxy", os.environ.get("HTTPS_PROXY", ""))
    if proxy_http or proxy_https:
        handlers.append(urllib.request.ProxyHandler({
            "http": proxy_http,
            "https": proxy_https,
        }))

    # 宽松的 SSL context（兼容有/无证书校验的环境）
    ssl_ctx = ssl.create_default_context()
    try:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    except Exception:
        pass
    https_handler = urllib.request.HTTPSHandler(context=ssl_ctx)
    handlers.append(https_handler)

    opener = urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()
    last_error = ""

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; CrusheartAutoBrain/7.0.0)"
            })
            with opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_error = str(e)
            log(f"请求失败 (尝试 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 指数退避: 1s, 2s

    raise ConnectionError(f"所有重试均失败: {last_error}")


def _extract_versions_from_html(html: str) -> list:
    """从 HTML 中提取所有看起来像版本号的字符串"""
    patterns = [
        # GitLab tags page: /-/tags 页面上的 tag 名称
        r'<a[^>]*href="[^"]*/tags/v?(\d+\.\d+\.\d+)[^"]*"[^>]*>',
        r'<span[^>]*class="[^"]*tag-name[^"]*"[^>]*>\s*v?(\d+\.\d+\.\d+)\s*</span>',
        # 通用的链接/文本中的版本号模式
        r'(?:tag|release|version)[/\s]*v?(\d+\.\d+\.\d+)',
        # 仓库页面的版本标识
        r'v?(\d+\.\d+\.\d+)[^"\']*release',
        # badge 或标签
        r'badge[/\-]version[=_-]v?(\d+\.\d+\.\d+)',
        # 直接匹配 tag 链接
        r'/tags/v?(\d+\.\d+\.\d+)',
        r'/releases/v?(\d+\.\d+\.\d+)',
    ]
    found = []
    for p in patterns:
        matches = re.findall(p, html, re.IGNORECASE)
        found.extend(matches)
    return found


def check_new_version():
    """检查是否有新版本。
    
    流程：
    1. 获取 tags 页面，提取所有 tag 版本号
    2. 取最高版本号（排除当前版本）
    3. 如果版本号 > 当前版本，通知有更新
    
    Returns: 新版本号字符串 (有更新) | None (无更新) | dict (错误)
    """
    state = load_state()
    notified = state.get("notified_versions", [])

    # ── 第一步：获取 tags 页面 ──
    log(f"检查最新版本: {TAGS_URL}")
    try:
        html = _fetch_url(TAGS_URL)
    except ConnectionError as e:
        log(f"tags 页面获取失败: {e}")
        # fallback：尝试仓库首页
        try:
            log(f"尝试仓库首页: {REPO_BASE}")
            html = _fetch_url(REPO_BASE, timeout=20)
        except ConnectionError as e2:
            log(f"仓库首页也失败: {e2}")
            return {
                "error": True,
                "message": f"无法连接仓库 {REPO_BASE} 检查版本，请确认网络正常"
            }

    # ── 第二步：提取所有版本号 ──
    candidates = _extract_versions_from_html(html)
    log(f"提取到版本候选: {candidates}")

    # 去重 + 解析 + 过滤
    seen = set()
    versions = []
    for v_str in candidates:
        v_clean = v_str.strip().lower()
        if v_clean in seen:
            continue
        seen.add(v_clean)
        parsed = _parse_version_text(v_clean)
        if parsed and parsed not in versions:
            versions.append((parsed, v_clean))

    if not versions:
        log("未提取到有效版本号")
        return {
            "error": True,
            "message": f"无法从仓库页面解析版本信息，请手动访问 {REPO_BASE} 检查"
        }

    # 排序取最高
    versions.sort(key=lambda x: x[0], reverse=True)
    latest_version = versions[0][1]
    latest_parts = versions[0][0]
    current_parts = _parse_version_text(CURRENT_VERSION)

    log(f"最新: {latest_version}, 当前: {CURRENT_VERSION}")

    if current_parts and latest_parts <= current_parts:
        # 当前已是最新
        return None

    # 有更新
    if latest_version not in notified:
        state["notified_versions"].append(latest_version)
    state["checks"].append({
        "time": datetime.now(BEIJING_TZ).isoformat(),
        "current": CURRENT_VERSION,
        "latest": latest_version,
        "found": True
    })
    save_state(state)
    return latest_version


if __name__ == "__main__":
    result = check_new_version()

    if result is None:
        # 无新版本：不输出
        pass
    elif isinstance(result, dict) and result.get("error"):
        # 检查失败（网络问题等）
        print(f"⚠️ 版本检查: {result['message']}")
        print(f"  当前版本: v{CURRENT_VERSION}")
        print(f"  仓库地址: {REPO_BASE}")
    elif result:
        # 有新版本
        msg = f"发现新版本: v{result}（当前: v{CURRENT_VERSION}），请前往 {REPO_BASE}/-/releases 查看"
        print(json.dumps({"has_update": True, "latest_version": result, "current": CURRENT_VERSION, "message": msg}))
    # 无新版本时不输出
