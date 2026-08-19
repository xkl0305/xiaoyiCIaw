"""
微信公众号用户无感自动登录 & 手机号签名自动登录
"""
import os
import time
import hmac
import hashlib
import base64
import json
import requests
from pathlib import Path


def _load_config() -> dict:
    """读取项目根目录 config.json 中的 codeflying 节点"""
    config_path = Path(__file__).parent.parent.parent.parent / "config.json"
    try:
        with open(config_path) as f:
            return json.load(f).get("codeflying", {})
    except Exception:
        return {}


def _get(key: str, env_var: str, default: str = "") -> str:
    cfg = _load_config()
    return cfg.get(key) or os.environ.get(env_var) or default


def auto_login_wechatoa(sender_id: str) -> bool:
    """
    用 openid + HMAC-SHA256 签名调用 login_by_openid 接口，
    获取 token 并写入本地文件，实现微信公众号用户无感登录。

    sender_id 格式：wechatoa_{openid}
    """
    if not sender_id.startswith("wechatoa_"):
        return False

    nanobot_secret = _get("nanobotSecret", "NANOBOT_SECRET")
    if not nanobot_secret:
        print("未配置 nanobotSecret，无法自动登录")
        return False

    login_url = _get("loginUrl", "CODEFLYING_LOGIN_URL", "https://www.codeflying.net/api")

    open_id = sender_id[len("wechatoa_"):]
    timestamp = str(int(time.time()))
    sign = hmac.new(
        nanobot_secret.encode(),
        f"{open_id}{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()

    try:
        resp = requests.post(
            f"{login_url}/wxlogin/login_by_openid",
            json={"openid": open_id, "timestamp": timestamp, "sign": sign},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token = (data.get("data") or {}).get("token") or data.get("token")
        if not token:
            print(f"auto_login_wechatoa 未获取到 token，响应：{data}")
            return False

        # 存到 config.json 同级的 workspace/users 目录
        workspace_dir = Path(__file__).parent.parent.parent / "users"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        with open(workspace_dir / sender_id, "w") as f:
            f.write(token)

        return True

    except Exception as e:
        print(f"auto_login_wechatoa 失败: {e}")
        return False


def _encrypt_phone(phone: str, secret: str, timestamp: str) -> str:
    """
    加密手机号：
      key   = HMAC-SHA256(secret, ts)
      enc   = phone_bytes[i] XOR key[i % 32]
      return base64_urlsafe(enc).rstrip('=')
    """
    key = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).digest()
    enc = bytes(b ^ key[i % 32] for i, b in enumerate(phone.encode()))
    return base64.urlsafe_b64encode(enc).rstrip(b"=").decode()


def get_auth_query(phone: str) -> str:
    """
    给手机号生成自动登录 URL 参数串，可直接拼接到任意地址后面。

    返回示例：ep=dGVzdA&ts=1751414400&sign=a3f2...
    失败返回空字符串。
    """
    secret = _get("nanobotSecret", "NANOBOT_SECRET", "ovZvDN9iLr0JrQHkLRnU2ufli9saXe")
    if not secret:
        return ""
    ts = str(int(time.time()))
    ep = _encrypt_phone(phone, secret, ts)
    sign = hmac.new(secret.encode(), (ep + ts).encode(), hashlib.sha256).hexdigest()
    return f"ep={ep}&ts={ts}&sign={sign}"
