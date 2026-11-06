#!/usr/bin/env python3
"""调用 Finance Hub API: cnStockKLine — A股股票分钟K线

Usage:
    python3 call_cnStockKLine.py --symbol sh600519 --scale 5 --datalen 100
    python3 call_cnStockKLine.py --symbol sz000002 --scale 1 --datalen 200

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/cnStockKLine"


def main():
    parser = argparse.ArgumentParser(description="调用 cnStockKLine — A股股票分钟K线")
    parser.add_argument("--symbol", required=True, help='股票代码，如 sh600519')
    parser.add_argument("--scale", required=True, help='分钟维度: 1/3/5/10/15/30/60')
    parser.add_argument("--datalen", default="100", help='数据长度，正整数，默认100')
    args = parser.parse_args()

    qs = {"symbol": args.symbol, "scale": args.scale, "datalen": args.datalen}
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
