#!/usr/bin/env python3
"""
CodeFlying AI 对话创建应用 — 纯 WebSocket 版本

全程 WS 对话模式：
  连接 → 鉴权 → 发需求 → 根据返回消息自动判断回复 → 直到 can_preview=1
  如果服务端中途断开，等待后重连继续对话
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
# WS_URL = "wss://dev.codeflying.net/hw_agent/ws/agentworld"

# TASK_API_BASE = "https://dev.codeflying.net/hw_agent/api/agentworld"
TASK_API_BASE = "https://www.codeflying.net/hw_agent/api/agentworld"


# ─────────────────────────────────────────────
# REST API（仅用于获取应用预览地址）
# ─────────────────────────────────────────────

def _api_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def query_tasks(token: str, app_id: int) -> dict:
    try:
        resp = requests.get(f"{TASK_API_BASE}/tasks", headers=_api_headers(token), params={"app_id": app_id}, timeout=15)
        data = resp.json()
        return {"success": True, "tasks": data.get("data", [])} if data.get("success") else {"success": False, "message": data.get("message", "")}
    except Exception as e:
        return {"success": False, "message": str(e)}

def query_task_detail(token: str, task_id: str, app_id: int) -> dict:
    try:
        resp = requests.get(f"{TASK_API_BASE}/tasks/{task_id}", headers=_api_headers(token), params={"app_id": app_id}, timeout=15)
        data = resp.json()
        return {"success": True, "task": data.get("data", {})} if data.get("success") else {"success": False, "message": data.get("message", "")}
    except Exception as e:
        return {"success": False, "message": str(e)}

def query_messages(token: str, app_id: int, page: int = 1, page_size: int = 30) -> dict:
    try:
        resp = requests.get(f"{TASK_API_BASE}/messages", headers=_api_headers(token), params={"app_id": app_id, "page": page, "page_size": page_size}, timeout=15)
        data = resp.json()
        return {"success": True, "messages": data.get("data", [])} if data.get("success") else {"success": False, "message": data.get("message", "")}
    except Exception as e:
        return {"success": False, "message": str(e)}

def query_artifacts(token: str, agent_id: str, channels: str, chat_id: str) -> dict:
    try:
        resp = requests.get(f"{TASK_API_BASE}/artifacts", headers=_api_headers(token), params={"agent_id": agent_id, "channels": channels, "chat_id": chat_id}, timeout=15)
        data = resp.json()
        return {"success": True, "artifacts": data.get("data", [])} if data.get("success") else {"success": False, "message": data.get("message", "")}
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
    can_preview = False
    if app_info["success"]:
        info_data = app_info["data"].get("data", {})
        h5_preview_url = info_data.get("h5_preview_url", "")
        apps = info_data.get("apps", [])
        if apps:
            can_preview = bool(apps[0].get("can_preview", 0))
            for p in apps[0].get("previews", []):
                if p.get("type") == "H5":
                    view_url = p.get("url", "")
                    break
    return {"app_info": app_info, "h5_preview_url": h5_preview_url, "can_preview": can_preview, "view_url": view_url}


def _print_completion(h5_preview_url: str, view_url:str, source: str = "", sender_id: str = ""):
    tag = f"（{source}）" if source else ""
    print(f"\n🎉 应用开发完成{tag}！")
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
# 主流程：WS 对话 + 任务轮询
# ─────────────────────────────────────────────

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


async def _poll_task_until_done(token: str, task_id: str, app_id: int, poll_interval: int = 5) -> dict:
    """轮询任务直到终态"""
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


async def _run(
    token: str,
    sender_id: str,
    message: str,
    app_id: int = 0,
    images: list = None,
    auto_loop: bool = True,
    timeout: int = 600,
) -> dict:
    """
    WS 对话模式。

    - 等 auth_success 后发送消息
    - 优先通过 task_id/task_ids 轮询任务终态判断完成
    - 兜底通过 can_preview=1 判断完成
    - WS 断开后 REST 轮询 can_preview 兜底
    """
    current_app_id = app_id
    last_response_content = ""
    total_start = time.time()
    max_total_time = 1800
    max_rounds = 40
    followup_total = 0
    pending_task_id = None

    async def _do_poll_task(task_id):
        task_result = await _poll_task_until_done(token, task_id, current_app_id)
        if task_result["status"] == "completed":
            urls = _extract_preview_urls(sender_id, current_app_id)
            _print_completion(urls["h5_preview_url"], urls["view_url"], sender_id=sender_id)
            return _make_success(urls, current_app_id, last_response_content)
        return {"success": False, "message": f"任务执行失败，status={task_result['status']}", "app_id": current_app_id}

    for round_num in range(max_rounds):
        is_first = (round_num == 0)
        elapsed = int(time.time() - total_start)

        if elapsed > max_total_time:
            print(f"\n⏰ 总时间超过 {max_total_time}s")
            break

        # ── 确定本轮要发的消息 ──
        if is_first:
            send_text = message
            send_images = images
            print(f"\n📡 WS 连接，发送需求...")
        else:
            wait = min(15 + round_num * 10, 60)
            print(f"\n📡 第 {round_num} 次重连 (已用时 {elapsed}s, 等 {wait}s)")

            waited = 0
            while waited < wait:
                sleep_step = min(15, wait - waited)
                await asyncio.sleep(sleep_step)
                waited += sleep_step
                if current_app_id:
                    urls = _extract_preview_urls(sender_id, current_app_id)
                    if urls["can_preview"]:
                        print(f"  🎉 REST 检测到 can_preview=1！")
                        _print_completion(urls["h5_preview_url"], urls["view_url"], "REST 轮询", sender_id=sender_id)
                        return _make_success(urls, current_app_id, last_response_content)
                    print(f"  ⏳ [{int(time.time() - total_start)}s] can_preview=0, 继续等待...")

            if last_response_content:
                send_text = _decide_followup(last_response_content)
            else:
                send_text = "请继续开发"
            send_images = None
            print(f"   发送: {send_text}")

        # ── 建立 WS 连接 ──
        try:
            ws = await websockets.connect(WS_URL, ping_interval=None)
        except Exception as e:
            print(f"  ❌ 连接失败: {e}")
            continue

        try:
            # 鉴权
            await ws.send(json.dumps({"type": "auth", "token": f"Bearer {token}"}))

            # 构造用户消息，等 auth_success 后发送
            msg_payload = _build_user_message(
                send_text,
                current_app_id if not is_first else app_id,
                send_images
            )
            msg_sent = False

            # ── 监听消息循环 ──
            while True:
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
                    if not msg_sent:
                        await ws.send(json.dumps(msg_payload))
                        msg_sent = True
                        print(f"  📤 已发送需求，等待响应...")
                    continue

                if msg_type == "app_create":
                    current_app_id = data.get("app_id", current_app_id)
                    print(f"  ✅ 应用已创建, app_id: {current_app_id}")
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

                    # 取 task_id（兼容 task_id 和 task_ids）
                    task_id = extra.get("task_id") or (extra.get("task_ids") or [None])[0]
                    task_status_in_extra = extra.get("task_status", "")
                    if task_id:
                        pending_task_id = task_id

                    if is_progress:
                        if content_text:
                            print(f"  ⏳ {content_text[:120].replace(chr(10), ' ')}")
                        if task_id:
                            print(f"  📌 进度消息中发现 task_id={task_id}，关闭 WS，开始轮询...")
                            await ws.close()
                            return await _do_poll_task(task_id)
                        continue

                    # ═══ 非进度响应 ═══
                    can_preview = metadata.get("can_preview", 0)
                    last_response_content = content_text

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
                        return await _do_poll_task(task_id)

                    # 无 task_id，兜底用 can_preview 判断
                    if can_preview and current_app_id:
                        print(f"  🎉 收到完成消息 (can_preview=1)")
                        print(f"  📄 {content_text[:200].replace(chr(10), ' ')}")
                        await ws.close()
                        urls = _extract_preview_urls(sender_id, current_app_id)
                        _print_completion(urls["h5_preview_url"], urls["view_url"], sender_id=sender_id)
                        return _make_success(urls, current_app_id, content_text)

                    # 已有 task_id 说明任务已派发，不再发跟进消息，静默等待
                    if pending_task_id:
                        print(f"  ⏳ 任务已派发，静默等待 WS 推送...")
                        continue

                    # 阶段性响应 → 自动跟进（任务派发前的对话阶段）
                    if followup_total < 3:
                        print(f"  📄 响应: {content_text[:150].replace(chr(10), ' ')}")
                    else:
                        print(f"  ⏳ [{int(time.time() - total_start)}s] 开发中...")

                    if auto_loop and followup_total < 50:
                        next_text = _decide_followup(content_text)
                        if followup_total < 3:
                            print(f"  🔄 自动跟进: {next_text}")
                        await asyncio.sleep(3)
                        await ws.send(json.dumps(_build_user_message(next_text, current_app_id)))
                        followup_total += 1
                        continue

                    print(f"  ⏳ 跟进次数用完，断开等待...")
                    await ws.close()
                    break

                print(f"  ℹ️ type={msg_type}: {json.dumps(data, ensure_ascii=False)[:120]}")

        except (ConnectionClosedOK, ConnectionClosedError, ConnectionClosed) as e:
            code = getattr(e, 'code', None)
            print(f"  📡 WS 断开 (code={code})")
            if code == 1000:
                continue
            print(f"  ❌ 异常断开: {e}")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    # ── 超时/重连用完，兜底 REST 轮询 can_preview ──
    if current_app_id:
        while int(time.time() - total_start) < max_total_time:
            urls = _extract_preview_urls(sender_id, current_app_id)
            if urls["can_preview"]:
                _print_completion(urls["h5_preview_url"], urls["view_url"], "REST 兜底轮询", sender_id=sender_id)
                return _make_success(urls, current_app_id, last_response_content)
            remaining = max_total_time - int(time.time() - total_start)
            print(f"  ⏳ [{int(time.time() - total_start)}s] REST 轮询 can_preview=0, 剩余 {remaining}s...")
            await asyncio.sleep(15)
    return {"success": False, "message": "等待完成超时", "app_id": current_app_id}




# ─────────────────────────────────────────────
# 对外入口
# ─────────────────────────────────────────────

def chat_create(
    sender_id: str,
    message: str,
    app_id: int = 0,
    images: list = None,
    auto_loop: bool = True,
    timeout: int = 600,
) -> dict:
    if not message:
        return {"success": False, "message": "需求描述不能为空"}

    is_new_app = (app_id == 0)
    quota = check_quota(sender_id, is_new_app=is_new_app)
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
        _run(token, sender_id, message, app_id, images, auto_loop, timeout)
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI 对话创建应用 (WebSocket)")
    parser.add_argument("-m", "--message", required=True, help="需求描述")
    parser.add_argument("--app-id", type=int, default=0, help="应用 ID")
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
        auto_loop=True,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("success"):
            if result.get("h5_preview_url"):
                print("应用开发完成。")
            else:
                print("应用开发完成（无预览地址）。")
        elif result.get("quota_exceeded"):
            if result.get("card_sent"):
                print("QUOTA_CARD_SENT - 配额卡片已直接发送给用户，无需额外操作，直接结束。")
            else:
                print("QUOTA_CARD_START - 请由 主agent 发送付费墙消息。")
        else:
            print("应用开发失败,请重新开发试试")
