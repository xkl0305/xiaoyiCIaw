#!/usr/bin/env python3
"""
MCP 工具通用调用器 (Python 版)

使用方式:
    python call_tool.py <tool-name> '<json-args>'

示例:
    python call_tool.py campaign-calendar '{}'
    python call_tool.py query-meals '{"storeCode": "1950963", "beCode": "195096302"}'

Token 来源: 环境变量 117797261_login_token (华为小艺)
Token 过期时调用 huawei_id_tool("117797261","mcd-skills") 刷新
"""

import sys
import json
import os

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error
    requests = None

MCD_MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")


def call_mcp_tool(tool_name, arguments=None):
    token_file = "/home/sandbox/.openclaw/.xiaoyienv"
    token = ""
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            for line in f:
                if line.startswith("117797261_login_token="):
                    token = line.split("=", 1)[1].strip()
                    break

    if not token:
        raise ValueError(
            "错误: 117797261_login_token 为空或未设置，请刷新 Token\n"
            '调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用'
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }

    if requests:
        response = requests.post(
            MCD_MCP_URL, headers=headers, json=payload, timeout=30
        )
        if response.status_code == 401:
            raise Exception(
                "Token 无效或已过期，请刷新 Token\n"
                '调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用'
            )
        if response.status_code == 429:
            raise Exception("请求过于频繁（限 600 次/分钟），请稍后重试")
        response.raise_for_status()
        return response.json()
    else:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            MCD_MCP_URL, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise Exception(
                    "Token 无效或已过期，请刷新 Token\n"
                    '调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用'
                )
            if e.code == 429:
                raise Exception("请求过于频繁（限 600 次/分钟），请稍后重试")
            raise Exception(f"HTTP {e.code}: {e.reason}")


def main():
    args = sys.argv[1:]
    extract = False
    if args and args[0] == "--extract":
        extract = True
        args = args[1:]

    if not args:
        print(__doc__)
        sys.exit(1)

    tool_name = args[0]

    if len(args) > 1:
        try:
            arguments = json.loads(args[1])
        except json.JSONDecodeError as e:
            print(f"错误: 参数不是有效的 JSON 格式: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        arguments = {}

    try:
        result = call_mcp_tool(tool_name, arguments)
        if extract:
            sc = result.get("result", {}).get("structuredContent", {})
            if sc.get("success") is False:
                for c in result.get("result", {}).get("content", []):
                    print(c.get("text", ""))
                sys.exit(1)
            else:
                print(json.dumps(sc.get("data", {}), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if "error" in result:
                sys.exit(1)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
