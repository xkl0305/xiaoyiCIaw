#!/usr/bin/env python3
"""调用 Finance Hub API: hkTradingMainFundsHistory — 港股主力资金历史

Usage:
    python3 call_hkTradingMainFundsHistory.py --symbol 00700 --days 60

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/hkTradingMainFundsHistory"


def main():
    parser = argparse.ArgumentParser(description="调用 hkTradingMainFundsHistory — 港股主力资金历史")
    parser.add_argument("--symbol", required=True, help='港股代码，如 00700')
    parser.add_argument("--days", default="60", help='天数，默认60')
    args = parser.parse_args()

    qs = {"symbol": args.symbol, "days": args.days}
    url = BASE_URL + "?" + urllib.parse.urlencode(qs)
    try:
        from auth import get_auth_headers as _auth_get_auth_headers
        headers = _auth_get_auth_headers()
    except SystemExit:
        raise
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
