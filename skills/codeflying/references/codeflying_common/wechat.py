"""
微信公众号基础工具：access_token 获取与缓存
"""
import os
import json
import time
import requests
from pathlib import Path

_CACHE_PATH = os.path.expanduser("~/.nanobot-xiaofeifei/temp/wx_access_token.json")


def _wechatoa_config() -> dict:
    config_path = Path(__file__).parent.parent.parent.parent / "config.json"
    try:
        with open(config_path) as f:
            return json.load(f).get("channels", {}).get("wechatoa", {})
    except Exception:
        return {}


def get_access_token() -> str:
    """
    获取微信公众号 access_token，有效期内直接返回缓存值。
    token 有效期 7200s，提前 300s 刷新以留出余量。
    """
    # 读缓存
    try:
        with open(_CACHE_PATH) as f:
            cache = json.load(f)
        if time.time() < cache.get("expires_at", 0) - 300:
            return cache["access_token"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass

    # 从配置读 tokenUrl 和 apiKey
    cfg = _wechatoa_config()
    token_url = cfg.get("tokenUrl", "")
    api_key = cfg.get("apiKey", "")
    if not token_url or token_url == "hardcode":
        raise RuntimeError("未在 config.json channels.wechatoa.tokenUrl 中配置微信 token 获取地址")

    headers = {"X-API-KEY": api_key} if api_key else {}
    resp = requests.get(token_url, headers=headers, timeout=10)
    resp.raise_for_status()
    result = resp.json()

    token = result.get("access_token", "")
    if not token:
        raise RuntimeError(f"获取 access_token 失败: {result}")

    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w") as f:
        json.dump({"access_token": token, "expires_at": time.time() + 7200}, f)

    return token


WECHAT_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/custom/send"


def send_text(openid: str, content: str) -> bool:
    """向微信用户发送文字消息"""
    token = get_access_token()
    payload = {
        "touser": openid,
        "msgtype": "text",
        "text": {"content": content},
    }
    resp = requests.post(
        f"{WECHAT_SEND_URL}?access_token={token}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=10,
    )
    result = resp.json()
    if result.get("errcode") != 0:
        print(f"WeChatOA send_text failed: {result}")
        return False
    return True


def send_news_card(openid: str, title: str, description: str, url: str, picurl: str) -> bool:
    """向微信用户发送图文链接卡片"""
    token = get_access_token()
    payload = {
        "touser": openid,
        "msgtype": "news",
        "news": {
            "articles": [{
                "title": title,
                "description": description,
                "url": url,
                "picurl": picurl,
            }]
        },
    }
    resp = requests.post(
        f"{WECHAT_SEND_URL}?access_token={token}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=10,
    )
    result = resp.json()
    if result.get("errcode") != 0:
        print(f"WeChatOA send_news_card failed: {result}")
        return False
    return True

