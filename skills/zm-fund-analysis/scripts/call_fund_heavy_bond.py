#!/usr/bin/env python3
"""基金重仓债券 - fund_heavy_bond
用法: python3 call_fund_heavy_bond.py <symbol> [page=1] [num=10]
示例: python3 call_fund_heavy_bond.py 002207
"""
import sys, json, urllib.request, urllib.parse

def main():
    if len(sys.argv) < 2:
        print("用法: python3 call_fund_heavy_bond.py <symbol> [page=1] [num=10]")
        sys.exit(1)

    p = {"symbol": sys.argv[1]}
    if len(sys.argv) > 2:
        p["page"] = sys.argv[2]
    if len(sys.argv) > 3:
        p["num"] = sys.argv[3]

    params = urllib.parse.urlencode(p)
    url = f"https://mcp.finance.sina.com.cn/api-call/fund_heavy_bond?{params}"
    try:
        from auth import get_auth_headers as _auth_get_auth_headers
        headers = _auth_get_auth_headers()
    except SystemExit:
        raise
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
