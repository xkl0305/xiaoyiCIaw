#!/usr/bin/env python3
"""调用 Finance Hub API: globalStockQuoteRealtime — 股票实时行情（A港美）

Usage:
    python3 call_globalStockQuoteRealtime.py --market cn --symbol sh688001
    python3 call_globalStockQuoteRealtime.py --market hk --symbol 00700
    python3 call_globalStockQuoteRealtime.py --market us --symbol AAPL

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/globalStockQuoteRealtime"


def main():
    parser = argparse.ArgumentParser(description="调用 globalStockQuoteRealtime — 股票实时行情")
    parser.add_argument("--market", required=True, help='市场代码: cn(沪深)/hk(港股)/us(美股)/gi(全球指数)')
    parser.add_argument("--symbol", required=True, help='股票代码，如 sh688001 / 00700 / AAPL')
    args = parser.parse_args()

    qs = {"market": args.market, "symbol": args.symbol}
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
