#!/usr/bin/env python3
"""调用 Finance Hub API: globalStockSearchSymbols — 全市场股票代码搜索

Usage:
    python3 call_globalStockSearchSymbols.py --type 11 --key 茅台
    python3 call_globalStockSearchSymbols.py --type 11,31 --key 苹果

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

BASE_URL = "https://mcp.finance.sina.com.cn/api-call/globalStockSearchSymbols"


def _decode_body(raw: bytes) -> str:
    """接口 Header 标注 UTF-8 但实际返回 GBK 编码文本，依次尝试解码。"""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="调用 globalStockSearchSymbols — 全市场股票代码搜索")
    parser.add_argument("--type", required=True, help='市场类型: 11(A股)/12(B股)/31(港股股票)等，多市场逗号分隔')
    parser.add_argument("--key", required=True, help='搜索关键词')
    parser.add_argument("--format", default="text", help='返回格式，固定text')
    parser.add_argument("--num", default="4", help='返回数量，固定4')
    args = parser.parse_args()

    qs = {"type": args.type, "key": args.key, "format": args.format, "num": args.num}
    url = BASE_URL + "?" + urllib.parse.urlencode(qs)
    try:
        from auth import get_auth_headers as _auth_get_auth_headers
        headers = _auth_get_auth_headers()
    except SystemExit:
        raise
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(2)

    # format=text 时接口返回逗号分隔文本（GBK 编码）；为 JSON 时美化输出
    text = _decode_body(raw).strip()
    if text.startswith(("{", "[")):
        try:
            print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
