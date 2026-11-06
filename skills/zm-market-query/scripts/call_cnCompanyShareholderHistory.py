#!/usr/bin/env python3
"""调用 Finance Hub API: cnCompanyShareholderHistory — A股公司股东人数

Usage:
    python3 call_cnCompanyShareholderHistory.py --Code 601127 --Type amount
    python3 call_cnCompanyShareholderHistory.py --Code 601127 --Type average

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/cnCompanyShareholderHistory"


def main():
    parser = argparse.ArgumentParser(description="调用 cnCompanyShareholderHistory — A股公司股东人数")
    parser.add_argument("--Code", required=True, help='不带前缀的A股代码，如 601127')
    parser.add_argument("--Type", required=True, help='数据类型: amount(股东总数) / average(平均持股数)')
    args = parser.parse_args()

    qs = {"Code": args.Code, "Type": args.Type}
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
