#!/usr/bin/env python3
"""调用 Finance Hub API: hkSectorQuotesList — 港股板块行情列表

Usage:
    python3 call_hkSectorQuotesList.py --type hk_plate_rise
    python3 call_hkSectorQuotesList.py --type hk_plate_fall

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/hkSectorQuotesList"


def main():
    parser = argparse.ArgumentParser(description="调用 hkSectorQuotesList — 港股板块行情列表")
    parser.add_argument("--type", required=True, help='板块类型: hk_plate_rise(领涨)/hk_plate_fall(领跌)/AHG(AH溢价)/ggt(港股通)/rmbk(热门)')
    args = parser.parse_args()

    qs = {"type": args.type}
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
