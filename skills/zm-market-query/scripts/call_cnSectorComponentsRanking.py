#!/usr/bin/env python3
"""调用 Finance Hub API: cnSectorComponentsRanking — A股指数和行业板块成分股

Usage:
    python3 call_cnSectorComponentsRanking.py --node sh000001
    python3 call_cnSectorComponentsRanking.py --node sh000001 --sort percent --asc 0 --num 20

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/cnSectorComponentsRanking"


def main():
    parser = argparse.ArgumentParser(description="调用 cnSectorComponentsRanking — A股指数和行业板块成分股")
    parser.add_argument("--node", required=True, help='指数或板块symbol，如 sh000001(上证指数)/diyu_150000(内蒙古)')
    parser.add_argument("--ret", default=None, help='自定义返回字段，逗号分隔')
    parser.add_argument("--sort", default=None, help='排序字段，默认 percent')
    parser.add_argument("--asc", default=None, help='排序方向: 0(倒序)/1(正序)')
    parser.add_argument("--page", default=None, help='页码')
    parser.add_argument("--num", default=None, help='每页数量')
    parser.add_argument("--hnew", default=None, help='含新股: 1(含)/0(不含)')
    parser.add_argument("--hcnew", default=None, help='含次新股: 1(含)/0(不含)')
    args = parser.parse_args()

    qs = {"node": args.node}
    for k in ("ret", "sort", "asc", "page", "num", "hnew", "hcnew"):
        v = getattr(args, k)
        if v is not None: qs[k] = v

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
