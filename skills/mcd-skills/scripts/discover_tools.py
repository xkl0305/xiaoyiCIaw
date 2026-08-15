#!/usr/bin/env python3
"""
Discover available MCP tools from the live tools/list endpoint.

Usage:
    python discover_tools.py             # print a concise tool list
    python discover_tools.py --json      # print the full live tools JSON
    python discover_tools.py --refresh   # accepted for compatibility; no cache exists

Token source: 117797261_login_token from:
    /home/sandbox/.openclaw/.xiaoyienv
    ~/.openclaw/.xiaoyienv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    import urllib.error
    import urllib.request

    requests = None

MCD_MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")

TOKEN_FILE_CANDIDATES = [
    "/home/sandbox/.openclaw/.xiaoyienv",
    os.path.expanduser("~/.openclaw/.xiaoyienv"),
]


def _read_login_token(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("117797261_login_token="):
                return line.split("=", 1)[1].strip()
    return ""


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def fetch_tools_from_server() -> list[dict] | None:
    token = ""
    for token_file in TOKEN_FILE_CANDIDATES:
        token = _read_login_token(token_file)
        if token:
            break

    if not token:
        print(
            "错误: 117797261_login_token 为空或未设置，请刷新 Token",
            file=sys.stderr,
        )
        print('调用 HuaweiIDTool("mcd-skills", "117797261") 刷新', file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    try:
        if requests:
            resp = requests.post(MCD_MCP_URL, headers=headers, json=payload, timeout=10)
            if resp.status_code == 401:
                print("Token 无效或已过期，请刷新 Token", file=sys.stderr)
                print(
                    '调用 HuaweiIDTool("mcd-skills", "117797261") 刷新',
                    file=sys.stderr,
                )
                sys.exit(1)
            if resp.status_code == 429:
                print("请求过于频繁（限 600 次/分钟），请稍后重试", file=sys.stderr)
                sys.exit(1)
            resp.raise_for_status()
            result = resp.json()
        else:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                MCD_MCP_URL, data=data, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    print("Token 无效或已过期，请刷新 Token", file=sys.stderr)
                    print(
                        '调用 HuaweiIDTool("mcd-skills", "117797261") 刷新',
                        file=sys.stderr,
                    )
                    sys.exit(1)
                if e.code == 429:
                    print(
                        "请求过于频繁（限 600 次/分钟），请稍后重试",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                print(f"请求失败: HTTP {e.code}: {e.reason}", file=sys.stderr)
                return None

        tools = result.get("result", {}).get("tools")
        if isinstance(tools, list):
            return tools
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)

    return None


def print_tools(tools: list[dict]) -> None:
    print("=" * 50)
    print(f"麦当劳 MCP 可用工具（实时 tools/list，{today_str()}）")
    print("=" * 50)
    print()

    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        desc = str(tool.get("description", "")).split("\n")[0][:80]
        print(f"  {i:2d}. {name}")
        if desc:
            print(f"      {desc}")
    print()
    print(f"总计: {len(tools)} 个工具")
    print()
    print("需要完整 inputSchema 时，运行: bash scripts/discover_tools.sh --json")


def main() -> None:
    parser = argparse.ArgumentParser(description="发现麦当劳 MCP 工具")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="兼容旧参数；当前总是实时查询 tools/list",
    )
    parser.add_argument("--json", action="store_true", help="输出完整实时工具定义")
    args = parser.parse_args()

    tools = fetch_tools_from_server()
    if tools is None:
        print("错误: 无法获取工具列表，请检查网络和 Token", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        print_tools(tools)


if __name__ == "__main__":
    main()
