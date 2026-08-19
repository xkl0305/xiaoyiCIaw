#!/usr/bin/env python3
"""
获取 CodeFlying 当前用户信息
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_get


def get_current_user(sender_id) -> dict:
    """获取当前用户信息"""
    result = api_get("/user/current_user_info", {"sender_id": sender_id})

    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "获取用户信息失败")}

    return {"success": True, "data": result}


def get_points(sender_id) -> dict:
    """获取积分余额"""
    result = api_get("/pay/new_get_tenant_rights", {"sender_id": sender_id})
    if not result.get("success", True):
        return {"success": False}
    data = result.get("data", {})
    daily   = (data.get("daily_points")   or {}).get("remaining", 0)
    monthly = (data.get("monthly_points") or {}).get("remaining", 0)
    balance = (data.get("balance_points") or {}).get("remaining", 0)
    invite  = (data.get("invite_points")  or {}).get("remaining", 0)
    return {"success": True, "daily": daily, "monthly": monthly, "balance": balance, "invite": invite, "total": daily + monthly + balance + invite}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取当前用户信息")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("-s", "--sender_id", required=True, help="发送者ID")
    args = parser.parse_args()

    sender_id = args.sender_id

    result = get_current_user(sender_id)
    points = get_points(sender_id)

    if args.json:
        print(json.dumps({"user": result, "points": points}, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            data = result["data"].get("data", result["data"])
            user = data.get("user_info", {})
            tenant = data.get("tenant_info", {})
            print(f"👤 用户信息")
            print(f"   用户名: {user.get('username')}")
            print(f"   昵称: {user.get('show_name')}")
            print(f"\n🏢 租户信息")
            print(f"   会员类型: {tenant.get('billing_type')}")
            if points["success"]:
                print(f"\n💎 积分余额")
                print(f"   每日积分: {points['daily']}")
                print(f"   月度积分: {points['monthly']}")
                print(f"   充值积分: {points['balance']}")
                print(f"   邀请积分: {points['invite']}")
                print(f"   合计可用: {points['total']}")
        else:
            print(f"❌ 错误: {result.get('message')}")
