#!/usr/bin/env python3
import argparse
import os
import sys
import time
import requests
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from codeflying_common.config import BASE_URL


def _user_dir():
    return os.path.expanduser("~/.nanobot-xiaofeifei/workspace/users")


def phone_auto_login(sender_id: str, phone: str) -> bool:
    """手机号签名自动登录（无验证码），调用 auto_login_by_phone"""
    from codeflying_common.auto_login import auto_login_by_phone
    success = auto_login_by_phone(sender_id, phone)
    if success:
        token_path = os.path.join(_user_dir(), sender_id)
        print(f"AUTO_LOGIN_SUCCESS:{token_path}")
        print(f"手机号 {phone} 自动登录成功，token 已保存。")
    else:
        print(f"AUTO_LOGIN_FAILED:手机号签名登录失败，请检查配置或改用验证码登录")
    return success


def get_auth_query(phone: str = "", sender_id: str = "") -> str:
    """
    生成手机号自动登录参数串，返回 ep=...&ts=...&sign=...
    phone 优先；未传时从 {sender_id}.phone 文件读；都没有则从 API 查 real_phone_number。
    """
    from codeflying_common.auto_login import get_auth_query as _get_auth_query

    # 1. 直接传了手机号
    if not phone and sender_id:
        # 2. 从本地文件读
        phone_path = os.path.join(_user_dir(), f"{sender_id}.phone")
        if os.path.exists(phone_path):
            with open(phone_path) as f:
                phone = f.read().strip()

    if not phone and sender_id:
        # 3. 从 API 查 real_phone_number
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from codeflying_common.config import api_get
            result = api_get("/user/current_user_info", {"sender_id": sender_id})
            data = result.get("data", result)
            phone = (data.get("user_info") or {}).get("real_phone_number", "")
            # 查到后写入本地文件缓存
            if phone:
                phone_path = os.path.join(_user_dir(), f"{sender_id}.phone")
                os.makedirs(_user_dir(), exist_ok=True)
                with open(phone_path, "w") as f:
                    f.write(phone)
        except Exception:
            pass

    if not phone:
        return ""
    return _get_auth_query(phone)


def send_code(phone: str) -> bool:
    """调用发送验证码接口，向手机号发送短信验证码"""
    try:
        resp = requests.post(
            f"{BASE_URL}/user/send_launch_code_no_captcha",
            json={"phone": phone, "code_type": "register_and_login"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            print(f"SEND_CODE_SUCCESS:{phone}")
            print(f"验证码已发送到手机 {phone}，请提示用户查收短信。")
            return True
        else:
            err = data.get("error") or data.get("msg") or str(data)
            print(f"SEND_CODE_FAILED:{err}")
            return False
    except Exception as e:
        print(f"SEND_CODE_ERROR:{e}")
        return False


def phone_login(sender_id: str, phone: str, launch_code: str) -> bool:
    """用手机号+验证码登录/注册，成功后保存 token 和手机号"""
    try:
        payload = {
            "phone": phone,
            "launch_code": launch_code,
            "language": "zh",
            "regist_without_phone": 0,
            "invite_code": "",
            "user_invite_code": "",
            "app_invite_code": "",
            "app_id": "",
            "signup_code": "",
            "invite_user_id": None,
            "source": "xiaoyi_claw",
        }
        resp = requests.post(
            f"{BASE_URL}/wxlogin/bind",
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        token = (data.get("data") or {}).get("token") or data.get("token")
        # /wxlogin/bind 直接在顶层返回 token
        if not token:
            token = data.get("token")
        if not token and isinstance(data, dict):
            # 兼容 {"success": true, "token": "..."} 结构
            token = data.get("token")

        if not token:
            err = data.get("error") or data.get("msg") or str(data)
            print(f"LOGIN_FAILED:{err}")
            return False

        user_dir = _user_dir()
        os.makedirs(user_dir, exist_ok=True)
        token_path = os.path.join(user_dir, sender_id)
        with open(token_path, "w") as f:
            f.write(token)

        # 同时保存手机号，供后续 get_auth_query 使用
        phone_path = os.path.join(user_dir, f"{sender_id}.phone")
        with open(phone_path, "w") as f:
            f.write(phone)

        print(f"LOGIN_SUCCESS:{token_path}")
        is_register = data.get("is_register", False)
        print(f"登录成功！{'新用户注册' if is_register else '已有账号登录'}，token 已保存。")
        return True

    except Exception as e:
        print(f"LOGIN_ERROR:{e}")
        return False


def check_login(sender_id: str) -> bool:
    """检查本地 token 文件是否存在（快速确认是否已登录）"""
    user_dir = _user_dir()
    token_path = os.path.join(user_dir, sender_id)
    if os.path.exists(token_path):
        print(f"LOGIN_SUCCESS:{token_path}")
        print("用户已登录（token 文件已存在）")
        return True
    print("NOT_LOGGED_IN")
    print("未找到登录记录，请先完成手机号登录。")
    return False


def cleanup_temp_files(sender_id: str):
    """清理临时文件（兼容保留）"""
    temp_dir = os.path.expanduser("~/.nanobot-xiaofeifei/temp")
    for fname in [f"login_{sender_id}.json", f"qr_{sender_id}.png"]:
        fpath = os.path.join(temp_dir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="码上飞手机号登录工具")
    parser.add_argument("--sender_id", required=True, help="用户的 sender ID")
    parser.add_argument(
        "--action",
        required=True,
        choices=["send_code", "phone_login", "check_login", "cleanup", "auto_login", "phone_auto_login", "get_auth_query"],
        help=(
            "操作类型: "
            "send_code(发送短信验证码), "
            "phone_login(手机号+验证码登录), "
            "check_login(检查本地登录状态), "
            "cleanup(清理临时文件), "
            "auto_login(wechatoa 无感登录), "
            "phone_auto_login(手机号签名自动登录，无需验证码), "
            "get_auth_query(生成手机号加密参数串，用于拼接到 URL)"
        ),
    )
    parser.add_argument("--phone", help="手机号（send_code / phone_login 时必填）")
    parser.add_argument("--code", help="短信验证码（phone_login 时必填）")

    args = parser.parse_args()

    success = False

    if args.action == "send_code":
        if not args.phone:
            print("错误：send_code 操作需要 --phone 参数")
            sys.exit(1)
        success = send_code(args.phone)

    elif args.action == "phone_login":
        if not args.phone or not args.code:
            print("错误：phone_login 操作需要 --phone 和 --code 参数")
            sys.exit(1)
        success = phone_login(args.sender_id, args.phone, args.code)

    elif args.action == "check_login":
        success = check_login(args.sender_id)

    elif args.action == "cleanup":
        cleanup_temp_files(args.sender_id)
        print(f"已清理临时文件：sender_id={args.sender_id}")
        sys.exit(0)

    elif args.action == "auto_login":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from codeflying_common.auto_login import auto_login_wechatoa
        success = auto_login_wechatoa(args.sender_id)
        if success:
            print("AUTO_LOGIN_SUCCESS")
        else:
            print("AUTO_LOGIN_FAILED")

    elif args.action == "phone_auto_login":
        if not args.phone:
            print("错误：phone_auto_login 操作需要 --phone 参数")
            sys.exit(1)
        success = phone_auto_login(args.sender_id, args.phone)

    elif args.action == "get_auth_query":
        query = get_auth_query(phone=args.phone or "", sender_id=args.sender_id)
        if query:
            print(f"AUTH_QUERY:{query}")
        else:
            print("AUTH_QUERY_FAILED:无法获取手机号，请确认已登录或传入 --phone 参数")
            sys.exit(1)

    if not success:
        sys.exit(1)
