"""
CodeFlying 配额查询与校验
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_get

MEMBERSHIP_URL = "https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team"
APPS_URL = "https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps"
PICURL = "https://kuafuai.obs.cn-east-3.myhuaweicloud.com/codeflying/static/app_image/2026/04/13/20260413170213A091_20260413170213A092.png"

LOW_POINTS_THRESHOLD = 200  # 积分低于此值时视为"即将不足"


def get_tenant_rights(sender_id: str) -> dict:
    """查询租户配额信息（使用新接口）"""
    result = api_get("/pay/new_get_tenant_rights", {"sender_id": sender_id})
    if not result.get("success"):
        return {"success": False, "message": result.get("error", "查询配额失败")}

    data = result.get("data", {})
    return {"success": True, "data": data}


def check_quota(sender_id: str, is_new_app: bool = True) -> dict:
    """
    开发前配额校验。

    is_new_app=True  新建应用：检查 app_quota + 积分
    is_new_app=False 修改应用：只检查积分

    新接口字段说明：
      app_quota:          null=无应用数量限制, 0=已达上限
      daily_points:       每日免费积分
      monthly_points:     月度积分
      balance_points:     充值/赠送积分包
      三类积分 remaining 之和 > 0 即可开发

    返回:
        {"ok": True}
        {"ok": False, "card": {...}}   包含引导卡片信息
    """
    result = get_tenant_rights(sender_id)
    if not result["success"]:
        # 查询失败时放行，让后端兜底
        return {"ok": True}

    data = result["data"]

    # ── 应用数量检查（仅新建时） ──
    if is_new_app:
        app_quota = data.get("app_quota")   # null=无限制, 0=已达上限
        if app_quota is not None and isinstance(app_quota, dict):
            total = app_quota.get("total")
            try:
                app_list_result = api_get("app/get/",{
                    "page": 1,
                    "page_size": 1,
                    "sender_id": sender_id,
                })
                real_total = app_list_result.get("data",{}).get("rows",0)
                if total - real_total <= 0:
                    return {
                        "ok": False,
                        "card": {
                            "type": "app_quota_exceeded",
                            "title": "应用数量已达上限",
                            "body": "您当前可创建的应用数量已用完，升级会员可提升上限。",
                            "action_label": "管理应用",
                            "action_url": APPS_URL,
                        },
                    }
            except Exception :
                remaining = app_quota.get("remaining",0)
                if remaining <=0 :
                    return {
                        "ok": False,
                        "card": {
                            "type": "app_quota_exceeded",
                            "title": "应用数量已达上限",
                            "body": "您当前可创建的应用数量已用完，升级会员可提升上限。",
                            "action_label": "管理应用",
                            "action_url": APPS_URL,
                        },
                    }
        elif app_quota is not None and not isinstance(app_quota, list):
            return {
                "ok": False,
                "card": {
                    "type": "app_quota_exceeded",
                    "title": "应用数量已达上限",
                    "body": "您当前可创建的应用数量已用完，升级会员可提升上限。",
                    "action_label": "管理应用",
                    "action_url": APPS_URL,
                },
            }


    # ── 积分检查 ──
    daily_remaining   = (data.get("daily_points")   or {}).get("remaining", 0)
    monthly_remaining = (data.get("monthly_points") or {}).get("remaining", 0)
    balance_remaining = (data.get("balance_points") or {}).get("remaining", 0)
    invite_remaining  = (data.get("invite_points")  or {}).get("remaining", 0)
    total_points = daily_remaining + monthly_remaining + balance_remaining + invite_remaining

    if total_points <= 0:
        return {
            "ok": False,
            "card": {
                "type": "gen_quota_exceeded",
                "title": "开发积分已用完",
                "body": "您的每日积分、月度积分和余额积分均已耗尽，升级会员或充值可获得更多积分。",
                "action_label": "立即充值/升级会员",
                "action_url": MEMBERSHIP_URL,
            },
        }

    low_points = (total_points < LOW_POINTS_THRESHOLD)
    return {"ok": True, "low_points": low_points, "total_points": total_points}


def get_total_remaining_points(sender_id: str) -> int:
    """获取用户剩余总积分（日积分 + 月积分 + 余额积分 + 邀请积分），查询失败返回 -1"""
    result = get_tenant_rights(sender_id)
    if not result["success"]:
        return -1
    data = result["data"]
    daily_remaining   = (data.get("daily_points")   or {}).get("remaining", 0)
    monthly_remaining = (data.get("monthly_points") or {}).get("remaining", 0)
    balance_remaining = (data.get("balance_points") or {}).get("remaining", 0)
    invite_remaining  = (data.get("invite_points")  or {}).get("remaining", 0)
    return daily_remaining + monthly_remaining + balance_remaining + invite_remaining


def send_quota_card_wechat(sender_id: str, card: dict) -> bool:
    """
    wechatoa 渠道：直接调微信 API 发配额不足卡片，不经过 agent。
    sender_id 格式：wechatoa_{openid}
    返回是否发送成功。
    """
    if not sender_id.startswith("wechatoa_"):
        return False

    try:
        from codeflying_common.wechat import send_text, send_news_card
    except Exception as e:
        print(f"导入 wechat 模块失败: {e}")
        return False

    openid = sender_id[len("wechatoa_"):]
    card_type = card.get("type", "")

    try:
        if card_type == "app_quota_exceeded":
            send_text(openid, "😅 应用数量达到上限了，需要先删除一些不用的应用，或者升级会员～")
            send_news_card(
                openid,
                title="开通会员 · 提升应用上限",
                description="升级会员提升上限，或删除不用的应用可释放名额",
                url=MEMBERSHIP_URL,
                picurl=PICURL,
            )
        elif card_type == "gen_quota_exceeded":
            send_news_card(
                openid,
                title="开发积分已用完，充值/升级解锁更多",
                description="升级会员或充值积分，即可继续开发应用～",
                url=MEMBERSHIP_URL,
                picurl=PICURL,
            )
        else:
            return False
    except Exception as e:
        print(f"send_quota_card_wechat 发送失败: {e}")
        return False

    return True


def send_low_points_warning_wechat(sender_id: str, total_points: int) -> bool:
    """
    wechatoa 渠道：积分即将不足时发送预警卡片。
    返回是否发送成功。
    """
    if not sender_id.startswith("wechatoa_"):
        return False

    try:
        from codeflying_common.wechat import send_news_card
    except Exception as e:
        print(f"导入 wechat 模块失败: {e}")
        return False

    openid = sender_id[len("wechatoa_"):]
    try:
        send_news_card(
            openid,
            title=f"积分即将不足（剩余 {total_points} 分），建议及时充值",
            description="积分不足将无法继续开发，点击立即充值或升级会员～",
            url=MEMBERSHIP_URL,
            picurl=PICURL,
        )
    except Exception as e:
        print(f"send_low_points_warning_wechat 发送失败: {e}")
        return False

    return True


def print_quota_card(card: dict) -> None:
    """将配额不足信息以卡片格式输出，供 AI 读取后转发给用户"""
    print("QUOTA_CARD_START")
    print(f"TYPE:{card['type']}")
    print(f"TITLE:{card['title']}")
    print(f"BODY:{card['body']}")
    print(f"ACTION_LABEL:{card['action_label']}")
    print(f"ACTION_URL:{card['action_url']}")
    print("QUOTA_CARD_END")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CodeFlying 配额检查")
    parser.add_argument("--sender_id", required=True, help="用户 sender_id")
    parser.add_argument("--new-app", action="store_true", help="是否为新建应用（同时检查应用数量配额）")
    args = parser.parse_args()

    result = check_quota(args.sender_id, is_new_app=args.new_app)
    if not result["ok"]:
        card = result["card"]
        # wechatoa 渠道：直接发卡片，不依赖 agent
        sent = send_quota_card_wechat(args.sender_id, card)
        if sent:
            # 卡片已直接发出，告知 agent 停止，不要再 spawn
            print(f"QUOTA_CARD_SENT:{card['type']}")
        else:
            # 非 wechatoa 渠道：输出给 agent 处理
            print_quota_card(card)
    else:
        total = result.get("total_points", 0)
        # 积分充足，检查是否即将不足
        if result.get("low_points"):
            sent = send_low_points_warning_wechat(args.sender_id, total)
            if sent:
                print(f"LOW_POINTS_WARNING_SENT:{total}")
            else:
                print(f"LOW_POINTS_WARNING:{total}")
        # 始终输出剩余积分，供 SKILL.md 的非 wechatoa 渠道二次查询提取
        print(f"REMAINING_POINTS:{total}")
        print("QUOTA_OK")
