#!/usr/bin/env python3
"""基金公司旗下基金经理 - fund_company_managers
用法: python3 call_fund_company_managers.py <compcode> [page=1] [num=20]
示例: python3 call_fund_company_managers.py 80000223
"""
import sys, json, urllib.request, urllib.parse

def main():
    if len(sys.argv) < 2:
        print("用法: python3 call_fund_company_managers.py <compcode> [page=1] [num=20]")
        sys.exit(1)

    p = {
        "compcode": sys.argv[1],
        "page": sys.argv[2] if len(sys.argv) > 2 else "1",
        "num": sys.argv[3] if len(sys.argv) > 3 else "20",
    }

    params = urllib.parse.urlencode(p)
    url = f"https://mcp.finance.sina.com.cn/api-call/fund_company_managers?{params}"
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
