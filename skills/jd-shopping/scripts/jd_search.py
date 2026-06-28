#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JD Shopping Search — standalone script for product search.

Calls JD Assistant API directly. Zero external dependencies (stdlib only).

Usage:
    python jd_search.py --query "推荐华为手机"
"""

import argparse
import hashlib
import http.client
import json
import os
import sys


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------

def parse_sse_line(line):
    """Parse a single SSE line.

    Returns:
        dict with {type, data} or None if line should be skipped.
        type is one of: 'text', 'suggestion', 'card'
    """
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None

    data_str = line[5:].strip()
    if data_str == "[DONE]":
        return None

    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    msg_type = data.get("msg_type")
    content = data.get("content")

    # Text chunk
    if msg_type == 1 and isinstance(content, str):
        return {"type": "text", "data": content}

    # Suggestions
    if msg_type == 3 and isinstance(content, dict) and "data" in content:
        return {"type": "suggestion", "data": content["data"]}

    # Hotel / flight cards — skipped
    if msg_type == 35 and isinstance(content, dict):
        return None

    # Product cards (SKU list)
    if msg_type == 25 and isinstance(content, dict):
        return {"type": "product_card", "data": content}

    # Status messages (21=thinking, 27=planning, 24=action) — skip
    if msg_type in (21, 27, 24):
        return None

    # Other msg_types with text content
    if isinstance(content, str) and content:
        return {"type": "text", "data": content}

    return None


# ---------------------------------------------------------------------------
# Token management (OAuth2)
# ---------------------------------------------------------------------------

_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token.json")

_AUTH_URL = (
    "https://agentkits-a2a-auth.jd.com/auth/58E3B63D17A7779D13199F2D9FC1736C"
)


def _load_token():
    """Load token from .token.json. Returns dict or None."""
    if not os.path.exists(_TOKEN_FILE):
        return None
    with open(_TOKEN_FILE) as f:
        return json.load(f)


def _save_token(data):
    """Save token dict to .token.json."""
    with open(_TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _ensure_token():
    """Load token from .token.json. Returns access_token or None.

    When token is missing, prints auth instructions and returns None.
    """
    token_data = _load_token()
    if not token_data or not token_data.get("access_token"):
        _print_auth_needed()
        return None
    return token_data["access_token"]


def _print_auth_needed():
    """Print markdown auth link for agent/mobile display."""
    print("🔐 **需要京东授权登录**")
    print()
    print("请点击下方链接完成登录：")
    print()
    print(f"[👉 点击授权登录]({_AUTH_URL})")
    print()
    print("登录完成后页面会显示 **access_token**，请将其粘贴给我。")


def _do_login():
    """Interactive login flow: open auth URL, user pastes access_token."""
    print("请在浏览器中打开以下链接并完成登录：")
    print()
    print(f"  {_AUTH_URL}")
    print()
    print("登录完成后页面会显示 access_token，请将其粘贴到下方：")
    print()
    token = input("access_token= ").strip()
    if not token:
        print("未输入 access_token", file=sys.stderr)
        sys.exit(1)
    token_data = {
        "access_token": token,
    }
    _save_token(token_data)
    print(f"Token 已保存到 {_TOKEN_FILE}")


# ---------------------------------------------------------------------------
# JOS Gateway client
# ---------------------------------------------------------------------------

class JDAPIClient:
    """JD A2A Gateway client — stdlib only, no SDK dependency."""

    DOMAIN = "https://agentkits-a2a-gateway.jd.com"
    APP_KEY = "58E3B63D17A7779D13199F2D9FC1736C"

    def __init__(self, host=None):
        self.domain = host or self.DOMAIN
        self.ACCESS_TOKEN = _ensure_token()  # None if auth needed

    def search(self, query, pin=None, stream=False, conversation_id=None):
        import uuid
        import urllib.parse

        context_id = conversation_id or str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": message_id,
                    "contextId": context_id,
                    "role": "user",
                    "parts": [
                        {"kind": "text", "text": query}
                    ]
                },
                "metadata": {
                    "callerAgent": "huawei"
                }
            }
        }

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        parsed = urllib.parse.urlparse(self.domain)
        host = parsed.netloc

        conn = http.client.HTTPSConnection(host, timeout=30)
        conn.request("POST", "/agents/sku-search", body=body, headers={
            "Content-Type": "application/json",
            "X-A2A-Agent-Id": "sku-search",
            "app_key": self.APP_KEY,
            "access_token": self.ACCESS_TOKEN,
            "fuzzyid": request_id,
        })
        raw = conn.getresponse().read()
        conn.close()

        text = raw.decode("utf-8", errors="replace")
        resp = json.loads(text)
        return self._parse_response(resp)

    def _parse_response(self, resp):
        """Parse A2A gateway response into internal format.

        Actual response structure:
        {
          "jsonrpc": "2.0",
          "id": "...",
          "result": {
            "contextId": "...",
            "status": {
              "state": "completed",
              "message": { "role": "agent", "parts": [{"text": "...", "kind": "text"}], ... }
            },
            "artifacts": [{
              "parts": [{
                "data": {
                  "data": [ {skuId, skuName, shopName, imgPath, purchasePrice, ...}, ... ]
                }
              }]
            }]
          }
        }
        """
        data = json.loads(resp) if isinstance(resp, str) else resp

        # Handle JSON-RPC error
        if "error" in data:
            err = data["error"]
            err_msg = err.get("message", str(err))
            print(f"A2A Gateway Error: {err_msg}", file=sys.stderr)
            return {"text": err_msg, "cards": [], "product_cards": [], "suggestions": []}

        result = data.get("result", {})

        # Extract agent text from status.message.parts
        text_parts = []
        status_msg = result.get("status", {}).get("message", {})
        for part in status_msg.get("parts", []):
            if part.get("kind") == "text":
                text_parts.append(part.get("text", ""))

        # Extract SKU data from artifacts[].parts[].data.data[]
        sku_list = []
        for artifact in result.get("artifacts", []):
            for part in artifact.get("parts", []):
                part_data = part.get("data", {})
                items = part_data.get("data", [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    sku_id = str(item.get("skuId", ""))
                    shop_name = item.get("shopName", "")
                    img_path = item.get("imgPath", "")
                    if img_path and not img_path.startswith("http"):
                        img_path = "https://img14.360buyimg.com/n1/" + img_path
                    is_self = "1" if "自营" in shop_name else "0"
                    sku_list.append({
                        "sku_id": sku_id,
                        "product_name": item.get("skuName", ""),
                        "short_name": "",
                        "price": str(item.get("purchasePrice", "")),
                        "img_url_big": img_path,
                        "item_url": "https://item.jd.com/{}.html".format(sku_id) if sku_id else "",
                        "is_self": is_self,
                        "sales": "",
                        "sku_tags": [],
                        "shop_name": shop_name,
                        "commentcount_fuzzy": "",
                        "good": "",
                    })

        return {
            "text": "\n".join(text_parts),
            "cards": [],
            "product_cards": [{"data": [{"sku_list": sku_list}]}] if sku_list else [],
            "suggestions": [],
        }



# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_product_cards(product_cards):
    """Extract structured product info from msg_type=25 SKU lists."""
    formatted = []
    seen_skus = set()
    for card in product_cards:
        for tab in card.get("data", []):
            for sku in tab.get("sku_list", []):
                sku_id = sku.get("sku_id") or sku.get("item_url", "")
                if sku_id in seen_skus:
                    continue
                seen_skus.add(sku_id)

                # Extract tags from sku_tags (e.g. 包邮, 百亿补贴)
                tags = []
                for t in sku.get("sku_tags", []):
                    tid = t.get("trackId", "")
                    if tid:
                        tags.append(tid)

                # Check if self-operated (自营)
                is_self = str(sku.get("is_self", "0")) == "1"

                formatted.append({
                    "type": "product",
                    "name": sku.get("product_name", sku.get("full_name", "")),
                    "short_name": sku.get("short_name", ""),
                    "price": sku.get("price", ""),
                    "img_url_big": sku.get("img_url_big", ""),
                    "item_url": sku.get("item_url", ""),
                    "comment_count": sku.get("commentcount_fuzzy", ""),
                    "good_rate": sku.get("good", ""),
                    "is_self": is_self,
                    "sales": sku.get("sales", ""),
                    "tags": tags,
                    "shop_name": sku.get("shop_name", ""),
                })
    return formatted


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_product_markdown(card, index):
    """Render a single product card as markdown."""
    name = card.get("short_name") or card.get("name", "")
    price = card.get("price", "")
    img = card.get("img_url_big", "")
    url = card.get("item_url", "")
    is_self = card.get("is_self", False)
    sales = card.get("sales", "")
    comment_count = card.get("comment_count", "")
    tags = card.get("tags", [])

    sku_id = url.rstrip("/").split("/")[-1].replace(".html", "") if url else ""
    deep_link = (
        'openapp.jdmobile://virtual?params={"category":"jump","des":"productDetail","skuId":"' + sku_id + '"}'
    ) if sku_id else url

    tag_parts = []
    if is_self:
        tag_parts.append("🏷️自营")
    tag_parts.extend(tags)
    volume = ("销量" + sales) if sales else (comment_count + "评价" if comment_count else "")

    lines = ["---", "**{}**".format(name), ""]
    if img:
        lines.append("[![{}]({})]({})".format(name, img, deep_link))
        lines.append("")
    meta = " · ".join(tag_parts)
    if meta and volume:
        lines.append("{} · {}".format(meta, volume))
    elif meta:
        lines.append(meta)
    elif volume:
        lines.append(volume)
    lines.append("")
    lines.append("**¥{}** · [**立即购买 ›**]({})".format(price, url))
    return "\n".join(lines)


def render_markdown(result_text, all_cards, suggestions):
    """Render full markdown output with cards and footer."""
    parts = []

    idx = 1
    for card in all_cards:
        if card.get("type") == "product":
            parts.append(render_product_markdown(card, idx))
        parts.append("")
        idx += 1

    if suggestions:
        parts.append("💡 你可能还想问：")
        for s in suggestions:
            if isinstance(s, str):
                parts.append("- {}".format(s))
            elif isinstance(s, dict) and s.get("text"):
                parts.append("- {}".format(s["text"]))
        parts.append("")

    parts.append("---")
    parts.append("🛒 本信息由 [京东](https://www.jd.com) 提供")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="JD Shopping Search — product search"
    )
    parser.add_argument("--query", default=None, help="Search query")
    parser.add_argument("--login", action="store_true",
                        help="Start login flow (interactive)")
    parser.add_argument("--pin", default=None, help="JD user pin (pt_pin), optional")
    parser.add_argument("--stream", action="store_true",
                        help="Enable streaming output")
    parser.add_argument("--format", choices=["markdown", "json"],
                        default="markdown",
                        help="Output format: markdown (default) or json")
    parser.add_argument("--conversation-id", default=None,
                        help="Conversation ID for multi-turn")
    args = parser.parse_args()

    # --- OAuth commands ---
    if args.login:
        _do_login()
        return

    # --- Search requires --query ---
    if not args.query:
        parser.error("--query is required (or use --login)")

    intent = "product"
    client = JDAPIClient()

    # Token missing/expired — auth instructions already printed by _ensure_token
    if client.ACCESS_TOKEN is None:
        return

    try:
        result = client.search(
            query=args.query,
            pin=args.pin,
            stream=args.stream,
            conversation_id=args.conversation_id,
        )

        if not args.stream:
            conv_id = args.conversation_id or "jd_conv_{}".format(
                hashlib.md5(args.query.encode()).hexdigest()[:8]
            )
            all_cards = format_product_cards(result["product_cards"])

            if args.format == "markdown":
                md = render_markdown(result["text"], all_cards,
                                     result["suggestions"])
                print(md)
                # Print metadata as JSON comment at the end for multi-turn
                print("\n<!-- conversation_id: {} -->".format(conv_id))
            else:
                output = {
                    "intent": intent,
                    "text": result["text"],
                    "cards": all_cards,
                    "suggestions": result["suggestions"],
                    "conversation_id": conv_id,
                }
                print(json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
