#!/usr/bin/env python3
"""
MCP 工具发现 (Python 版)

通过 tools/list 接口动态发现可用工具，按天缓存到本地文件。

缓存策略：
  - 缓存路径：scripts/cache/tools_YYYY-MM-DD.json
  - 运行时自动检查当天缓存是否存在，不存在则拉取并写入
  - 写入新缓存时自动删除前一天及更早的缓存文件

使用方式:
    python discover_tools.py             # 显示工具列表（优先读当天缓存）
    python discover_tools.py --refresh   # 强制刷新当天缓存
    python discover_tools.py --json      # JSON 格式输出

Token 来源: 环境变量 117797261_login_token (华为小艺)
Token 过期时调用 huawei_id_tool("117797261","mcd-skills") 刷新
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error
    requests = None

MCD_MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def cache_path(date_str=None):
    return os.path.join(CACHE_DIR, f"tools_{date_str or today_str()}.json")


def cleanup_old_caches():
    today = today_str()
    for f in glob.glob(os.path.join(CACHE_DIR, "tools_*.json")):
        basename = os.path.basename(f)
        date_part = basename.replace("tools_", "").replace(".json", "")
        if date_part != today:
            os.remove(f)
            print(f"已清理旧缓存: {basename}", file=sys.stderr)


def fetch_tools_from_server():
	token_file = "/home/sandbox/.openclaw/.xiaoyienv"
    token = ""
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            for line in f:
                if line.startswith("117797261_login_token="):
                    token = line.split("=", 1)[1].strip()
                    break
    if not token:
        print("错误: 117797261_login_token 为空或未设置，请刷新 Token", file=sys.stderr)
        print('调用 调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用', file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    try:
        if requests:
            resp = requests.post(MCD_MCP_URL, headers=headers, json=payload, timeout=10)
            result = resp.json()
        else:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(MCD_MCP_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))

        if "result" in result and "tools" in result["result"]:
            return result["result"]["tools"]
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)

    return None


def load_cache():
    path = cache_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_cache(tools):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = cache_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)
    print(f"工具列表已缓存到: {path}", file=sys.stderr)
    cleanup_old_caches()


def print_tools(tools):
    print("=" * 50)
    print(f"麦当劳 MCP 可用工具 ({today_str()})")
    print("=" * 50)
    print()

    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        desc = tool.get("description", "").split("\n")[0][:60]
        print(f"  {i:2d}. {name}")
        if desc:
            print(f"      {desc}")
    print()
    print(f"总计: {len(tools)} 个工具")
    print(f"缓存文件: {cache_path()}")
    print()
    print("Agent 可直接读取缓存文件查看完整参数定义（inputSchema）")


def main():
    parser = argparse.ArgumentParser(description="发现麦当劳 MCP 工具")
    parser.add_argument("--refresh", action="store_true", help="强制刷新当天缓存")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if not args.refresh:
        tools = load_cache()
        if tools:
            if args.json:
                print(json.dumps(tools, ensure_ascii=False, indent=2))
            else:
                print_tools(tools)
            return

    print("正在从 MCP 服务器获取工具列表...", file=sys.stderr)
    tools = fetch_tools_from_server()
    if tools is None:
        print("错误: 无法获取工具列表，请检查网络和 Token", file=sys.stderr)
        sys.exit(1)

    save_cache(tools)

    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
    else:
        print_tools(tools)


if __name__ == "__main__":
    main()
