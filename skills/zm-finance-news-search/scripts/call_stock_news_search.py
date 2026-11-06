#!/usr/bin/env python3
"""调用 Finance Hub API: stockNewsSearch（个股新闻搜索）

查询指定股票的相关新闻，支持沪深、港股、美股。
当用户明确要查某只股票的新闻时使用此脚本。

Usage:
    python3 call_stock_news_search.py --market cn --symbol sh600519 [--page 1] [--num 10]
    python3 call_stock_news_search.py --market hk --symbol 00700
    python3 call_stock_news_search.py --market us --symbol AAPL

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/stockNewsSearch"


def main():
    parser = argparse.ArgumentParser(description="查询个股新闻（stockNewsSearch API）")
    parser.add_argument("--market", required=True, choices=["cn", "hk", "us"],
                        help="市场代码：cn=沪深，hk=港股，us=美股")
    parser.add_argument("--symbol", required=True,
                        help="股票代码。沪深需带前缀，如 sh600519 / sz000002；港股如 00700；美股如 AAPL")
    parser.add_argument("--page", default="1",
                        help="页码，默认 1，最大 100")
    parser.add_argument("--num", default="10",
                        help="每页条数，默认 10，最大 20")
    args = parser.parse_args()

    qs = {
        "market": args.market,
        "symbol": args.symbol,
        "page": args.page,
        "num": args.num,
    }

    url = BASE_URL + "?" + urllib.parse.urlencode(qs)
    try:
        from auth import get_auth_headers as _auth_get_auth_headers
        headers = _auth_get_auth_headers()
    except SystemExit:
        raise
    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
