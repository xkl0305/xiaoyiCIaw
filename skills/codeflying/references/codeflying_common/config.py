"""
CodeFlying API 公共配置
"""
import os
import requests

from codeflying_common.auto_login import auto_login_wechatoa

# API 配置
BASE_URL = "https://www.codeflying.net/api"
# BASE_URL = "https://dev.codeflying.net/codeflying_backend"


def _get_token(sender_id: str) -> str:
    """读取用户 token；仅 wechatoa 渠道未登录时自动登录，其他渠道需手机号登录"""
    file_path = os.path.expanduser(f"~/.nanobot-xiaofeifei/workspace/users/{sender_id}")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            token = f.read().strip()
        if token:
            return token

    # 仅 wechatoa 渠道支持自动登录
    if sender_id.startswith("wechatoa_") and auto_login_wechatoa(sender_id):
        try:
            with open(file_path, "r") as f:
                return f.read().strip()
        except Exception:
            pass

    print("用户还没有登录，使用登录skills引导用户登录")
    exit(0)


def api_get(endpoint: str, params: dict = None) -> dict:
    """发起 GET 请求"""
    url = f"{BASE_URL}{endpoint}"
    token = _get_token(params["sender_id"]) if params and params.get("sender_id") else ""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.get(url, headers=headers, params=params or {})
    return response.json()


def api_post(endpoint: str, data: dict = None) -> dict:
    """发起 POST 请求"""
    url = f"{BASE_URL}{endpoint}"
    token = _get_token(data["sender_id"]) if data and data.get("sender_id") else ""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=data or {})
    return response.json()
