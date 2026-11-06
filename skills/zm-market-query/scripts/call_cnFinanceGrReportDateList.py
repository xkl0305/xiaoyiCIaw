#!/usr/bin/env python3
"""调用 Finance Hub API: cnFinanceGrReportDateList — A股公司主营构成报告日期列表

Usage:
    python3 call_cnFinanceGrReportDateList.py --paperCode sh688387

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/cnFinanceGrReportDateList"


def main():
    parser = argparse.ArgumentParser(description="调用 cnFinanceGrReportDateList — A股公司主营构成报告日期列表")
    parser.add_argument("--paperCode", required=True, help='股票代码，如 sh688387')
    args = parser.parse_args()

    qs = {"paperCode": args.paperCode}
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
