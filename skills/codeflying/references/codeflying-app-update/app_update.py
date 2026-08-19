#!/usr/bin/env python3
"""
CodeFlying AI 对话修改应用 — WebSocket 版本

流程：
  连接 → 鉴权 → 发需求 → 自动跟进对话
  → 当 response extra 中出现 task_id（非进度消息）→ 关闭 WS，轮询任务直到终态
  → 任务 completed → 获取预览地址返回；failed/cancelled → 返回失败
  → 若 WS 断开时已有 pending task_id → 直接轮询，不重连
"""
import json
import sys
import os
import time
import asyncio
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError
except ImportError:
    print("❌ 缺少 websockets 库，请先安装: pip3 install websockets")
    sys.exit(1)

from codeflying_common.config import _get_token, api_get
from codeflying_common.quota import check_quota, print_quota_card, send_quota_card_wechat, get_total_remaining_points, send_low_points_warning_wechat, LOW_POINTS_THRESHOLD

WS_URL = "wss://www.codeflying.net/hw_agent/ws/agentworld"
TASK_API_BASE = "https://www.codeflying.net/hw_agent/api/agentworld"

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


# ─────────────────────────────────────────────
# REST API
# ─────────────────────────────────────────────

def _api_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def query_task_detail(token: str, task_id: str, app_id: int) -> dict:
    """查询单个 task 状态"""
    try:
        resp = requests.get(
            f"{TASK_API_BASE}/tasks/{task_id}",
            headers=_api_headers(token),
            params={"app_id": app_id},
            timeout=15,
        )
        data = resp.json()
        if data.get("success"):
            return {"success": True, "task": data.get("data", {})}
        return {"success": False, "message": data.get("message", "")}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_app_info(sender_id: str, app_id: int) -> dict:
    if not app_id:
        return {"success": False, "message": "app_id 不能为空"}
    result = api_get("/app/get", {"app_id": app_id, "page": 1, "page_size": 1, "sender_id": sender_id})
    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "获取应用信息失败")}
    return {"success": True, "data": result}


def _extract_preview_urls(sender_id: str, app_id: int) -> dict:
    app_info = get_app_info(sender_id, app_id)
    h5_preview_url = ""
    view_url = ""
    if app_info["success"]:
        info_data = app_info["data"].get("data", {})
        h5_preview_url = info_data.get("h5_preview_url", "")
        apps = info_data.get("apps", [])
        if apps:
            for p in apps[0].get("previews", []):
                if p.get("type") == "H5":
                    view_url = p.get("url", "")
                    break
    return {"app_info": app_info, "h5_preview_url": h5_preview_url, "view_url": view_url}


def _print_completion(h5_preview_url: str, view_url: str, sender_id: str = ""):
    print(f"\n🎉 应用修改完成！")
    print(f"   应用管理地址: https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps")
    print(f"   分享地址: {h5_preview_url or '无'}")
    print(f"   应用预览地址: {view_url or '无'}")

    if sender_id:
        time.sleep(35)
        remaining = get_total_remaining_points(sender_id)
        if remaining >= 0:
            print(f"REMAINING_POINTS:{remaining}")
            if 0 < remaining < LOW_POINTS_THRESHOLD:
                sent = send_low_points_warning_wechat(sender_id, remaining)
                if sent:
                    print(f"LOW_POINTS_WARNING_SENT:{remaining}")
                else:
                    print(f"LOW_POINTS_WARNING:{remaining}")


def _make_success(urls: dict, app_id: int, content: str = "") -> dict:
    return {
        "success": True,
        "data": urls["app_info"].get("data", {}),
        "app_id": app_id,
        "h5_preview_url": urls["h5_preview_url"],
        "view_url": urls["view_url"],
        "content": content,
    }


# ─────────────────────────────────────────────
# WS 消息构造 & 智能回复
# ─────────────────────────────────────────────

def _build_user_message(text: str, app_id: int = 0, images: list = None) -> dict:
    content = {"text": text}
    if images:
        content["images"] = images
    msg = {"type": "user_message", "data": {"content": content}}
    if app_id:
        msg["data"]["metadata"] = {"app_id": app_id}
    return msg


def _decide_followup(content: str) -> str:
    """根据服务端消息内容，智能决定跟进回复"""
    c = content.strip()
    for kw in ["？", "请问", "您觉得", "你觉得", "选择", "哪个", "哪种",
               "需要您", "需要你", "请确认", "请选择", "告诉我", "能否",
               "是否需要", "有什么要求", "有什么想法", "偏好"]:
        if kw in c:
            return "你来帮我决定就好，我没有特别的要求，按你的专业判断来"
    for kw in ["确认", "方案如下", "计划如下", "以下是", "我打算",
               "准备开始", "是否满意", "满意吗", "可以吗", "没问题吧",
               "您看", "你看看"]:
        if kw in c:
            return "满意，没问题，直接开始吧"
    for kw in ["已完成", "完成了", "搞定", "分析好了", "设计好了",
               "开发好了", "部署好了", "上线了", "发布了"]:
        if kw in c:
            return "好的，请继续下一步"
    return "好的，继续"


# ─────────────────────────────────────────────
# 任务轮询
# ─────────────────────────────────────────────

async def _poll_task_until_done(token: str, task_id: str, app_id: int, poll_interval: int = 5) -> dict:
    """
    轮询任务直到终态，返回最终状态。
    终止条件：
      - status 为 completed / failed / cancelled
      - data 为空（视为已完成）
    """
    print(f"  🔄 轮询任务 task_id={task_id}...")
    while True:
        result = query_task_detail(token, task_id, app_id)
        if not result["success"]:
            print(f"  ⚠️ 查询失败: {result.get('message')}，{poll_interval}s 后重试...")
            await asyncio.sleep(poll_interval)
            continue

        task = result.get("task", {})
        if not task:
            print(f"  ✅ task data 为空，视为已完成")
            return {"status": "completed", "task": {}}

        status = task.get("status", "")
        print(f"  ⏳ task_id={task_id} status={status}")

        if status in TERMINAL_STATUSES:
            print(f"  ✅ 任务终止 status={status}")
            return {"status": status, "task": task}

        await asyncio.sleep(poll_interval)


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

async def _run(
    token: str,
    sender_id: str,
    message: str,
    app_id: int = 0,
    images: list = None,
    timeout: int = 600,
) -> dict:
    """
    WS 对话 → 任务轮询模式（静默等待）。

    - 只发一次修改需求，不发任何跟进消息
    - 静默监听 WS，收到含 task_id 的非进度响应 → 关闭 WS，轮询任务
    - 进度消息含 task_id → 记录，WS 断开后直接轮询
    - 任务 completed → 获取预览地址返回
    - 任务 failed/cancelled → 返回失败
    """
    current_app_id = app_id
    last_response_content = ""
    total_start = time.time()
    max_total_time = 1800

    async def _do_poll(task_id):
        task_result = await _poll_task_until_done(token, task_id, current_app_id)
        if task_result["status"] == "completed":
            urls = _extract_preview_urls(sender_id, current_app_id)
            _print_completion(urls["h5_preview_url"], urls["view_url"], sender_id=sender_id)
            return _make_success(urls, current_app_id, last_response_content)
        return {"success": False, "message": f"任务执行失败，status={task_result['status']}", "app_id": current_app_id}

    try:
        ws = await websockets.connect(WS_URL, ping_interval=None)
    except Exception as e:
        return {"success": False, "message": f"WS 连接失败: {e}"}

    try:
        # 鉴权
        await ws.send(json.dumps({"type": "auth", "token": f"Bearer {token}"}))
        print(f"  📡 已发送鉴权，等待 auth_success 后发送修改需求...")

        # 构造用户消息（等 auth_success 后才发送）
        content = {"text": message}
        if images:
            content["images"] = images
        msg_payload = {"type": "user_message", "data": {"content": content}}
        if current_app_id:
            msg_payload["data"]["metadata"] = {"app_id": current_app_id}

        msg_sent = False  # 标记用户消息是否已发送

        # 静默监听，不发任何跟进消息
        while True:
            elapsed = int(time.time() - total_start)
            if elapsed > max_total_time:
                print(f"  ⏰ 超过 {max_total_time}s，放弃")
                break

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"  ⏰ {timeout}s 无消息")
                break

            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws.send(json.dumps({"type": "pong", "data": {}}))
                continue

            if msg_type == "auth_success":
                print(f"  ✅ 鉴权成功 (user_id={data.get('user_id', '?')})")
                # 鉴权完成后立即发送用户消息
                if not msg_sent:
                    await ws.send(json.dumps(msg_payload))
                    msg_sent = True
                    print(f"  📤 已发送修改需求，静默等待 task_id...")
                continue

            if msg_type == "app_create":
                current_app_id = data.get("app_id", current_app_id)
                print(f"  ✅ 应用 app_id: {current_app_id}")
                continue

            if msg_type == "insufficient_balance":
                err = data.get("message", "余额不足")
                print(f"  ⚠️ {err}")
                await ws.close()
                card = {
                    "type": "gen_quota_exceeded",
                    "title": "开发积分已用完",
                    "body": "您的积分余额不足，升级会员或充值可获得更多积分。",
                    "action_label": "升级会员",
                    "action_url": "https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team",
                }
                sent = send_quota_card_wechat(sender_id, card)
                if sent:
                    print("QUOTA_CARD_SENT - 配额卡片已直接发送给用户，无需额外操作，直接结束。")
                else:
                    print_quota_card(card)
                return {"success": False, "message": err, "quota_exceeded": True, "card_sent": sent}

            if msg_type == "response":
                is_progress = data.get("is_progress", False)
                content_text = data.get("content", "")
                metadata = data.get("metadata", {})
                extra = data.get("extra", {}) or {}

                if metadata.get("app_id"):
                    current_app_id = metadata["app_id"]

                for ui in metadata.get("render_ui", []):
                    print(f"  📋 {ui.get('summary', '')} [{ui.get('status', '')}]")

                task_id = extra.get("task_id") or (extra.get("task_ids") or [None])[0]
                task_status_in_extra = extra.get("task_status", "")

                if is_progress:
                    if content_text:
                        print(f"  ⏳ {content_text[:120].replace(chr(10), ' ')}")
                    task_id_prog = extra.get("task_id") or (extra.get("task_ids") or [None])[0]
                    if task_id_prog:
                        print(f"  📌 进度消息中发现 task_id={task_id_prog}，关闭 WS，开始轮询...")
                        await ws.close()
                        return await _do_poll(task_id_prog)
                    continue

                # 非进度响应
                last_response_content = content_text
                print(f"  📄 {content_text[:150].replace(chr(10), ' ')}")

                if task_id:
                    print(f"  📌 发现 task_id={task_id} task_status={task_status_in_extra or '未知'}，关闭 WS，开始轮询...")
                    await ws.close()
                    if task_status_in_extra in TERMINAL_STATUSES:
                        print(f"  ✅ WS 消息中已确认终态 {task_status_in_extra}")
                        if task_status_in_extra == "completed":
                            urls = _extract_preview_urls(sender_id, current_app_id)
                            _print_completion(urls["h5_preview_url"], urls["view_url"], sender_id=sender_id)
                            return _make_success(urls, current_app_id, content_text)
                        return {"success": False, "message": f"任务执行失败，status={task_status_in_extra}", "app_id": current_app_id}
                    return await _do_poll(task_id)

                # 无 task_id：静默等待，不发任何消息
                continue

            print(f"  ℹ️ type={msg_type}: {json.dumps(data, ensure_ascii=False)[:120]}")

    except (ConnectionClosedOK, ConnectionClosedError, ConnectionClosed) as e:
        print(f"  📡 WS 断开 (code={getattr(e, 'code', None)})")
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    finally:
        try:
            await ws.close()
        except Exception:
            pass

    return {"success": False, "message": "未收到任务，修改可能仍在进行中", "app_id": current_app_id}


# ─────────────────────────────────────────────
# 对外入口
# ─────────────────────────────────────────────

def chat_create(
    sender_id: str,
    message: str,
    app_id: int = 0,
    images: list = None,
    timeout: int = 600,
) -> dict:
    if not message:
        return {"success": False, "message": "需求描述不能为空"}

    quota = check_quota(sender_id, is_new_app=False)
    if not quota["ok"]:
        card = quota["card"]
        sent = send_quota_card_wechat(sender_id, card)
        if sent:
            print("QUOTA_CARD_SENT - 配额卡片已直接发送给用户，无需额外操作，直接结束。")
        else:
            print_quota_card(card)
        return {
            "success": False,
            "message": card["body"],
            "quota_exceeded": True,
            "card_sent": sent,
            "membership_url": card.get("action_url", ""),
        }

    token = _get_token(sender_id)
    return asyncio.run(
        _run(token, sender_id, message, app_id, images, timeout)
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI 对话修改应用 (WebSocket)")
    parser.add_argument("-m", "--message", required=True, help="需求描述")
    parser.add_argument("--app-id", type=int, default=0, help="应用 ID")
    parser.add_argument("--requirement-id", type=int, default=0, help="需求 ID（兼容旧参数，暂未使用）")
    parser.add_argument("--pre-memory-id", type=int, default=0, help="上次对话 ID（兼容旧参数，暂未使用）")
    parser.add_argument("--action", help="指定动作（兼容旧参数，暂未使用）")
    parser.add_argument("--sender_id", required=True, help="发送者ID")
    parser.add_argument("--images", nargs="*", help="图片URL列表")
    parser.add_argument("--timeout", type=int, default=600, help="消息超时(秒)")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = chat_create(
        sender_id=args.sender_id,
        message=args.message,
        app_id=args.app_id,
        images=args.images,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("success"):
            if result.get("h5_preview_url"):
                print("应用修改完成。")
            else:
                print("应用修改完成（无预览地址）。")
        elif result.get("quota_exceeded"):
            if result.get("card_sent"):
                print("QUOTA_CARD_SENT - 配额卡片已直接发送给用户，无需额外操作，直接结束。")
            else:
                print("QUOTA_CARD_START - 请由 主agent 发送付费墙消息。")
        else:
            print("应用修改失败,请重新试试")
