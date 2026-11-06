#!/usr/bin/env python3
"""通过 globalStockSearchSymbols 搜索金融标的 symbol，供用户确认后使用。

支持范围：
    股票（A股/港股/美股）、基金、ETF、指数、债券等多种金融标的。
    虽然接口名称含 "Stock"，但实际可搜索各类证券代码。

使用场景：
    当用户提供的标的信息不明确时（公司名、基金简称、指数名称、拼音等），
    先运行本脚本获取候选 symbol 列表，展示给用户确认，
    再将确认的 symbol 传入业务接口。

Usage:
    python3 suggest_symbol.py --keyword <关键词>
    python3 suggest_symbol.py --keyword 茅台
    python3 suggest_symbol.py --keyword 沪深300
    python3 suggest_symbol.py --keyword AAPL
    python3 suggest_symbol.py --keyword 华夏基金 --json   # 输出原始 JSON

Authentication:
    华为 loginToken（由 auth 模块从 .xiaoyienv 读取）经 xy_exchange_token 换取 MCP token；
    业务请求头统一 X-Auth-Token
"""
import sys, json, argparse, urllib.request, urllib.parse, urllib.error

SUGGEST_URL = "https://mcp.finance.sina.com.cn/api-call/globalStockSearchSymbols"


def _decode_body(raw: bytes) -> str:
    """接口 Header 标注 UTF-8 但实际返回 GBK 编码文本，依次尝试解码。"""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def search_symbol(keyword: str) -> list:
    qs  = urllib.parse.urlencode({"type": "11,12,31", "key": keyword, "format": "text", "num": "4"})
    url = f"{SUGGEST_URL}?{qs}"
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
            raw = resp.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(2)

    text = _decode_body(raw).strip()
    # 兼容 JSON 响应（data/list/results/items/symbols 任一列表字段）
    if text.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for d in (data, data.get("result") if isinstance(data.get("result"), dict) else None):
                if not isinstance(d, dict):
                    continue
                for key in ("data", "list", "results", "items", "symbols"):
                    if key in d and isinstance(d[key], list):
                        return d[key]
        return []

    # format=text 实测返回逗号分隔文本（每行一条：名称,类型,代码,symbol,...）
    items = []
    for line in text.splitlines():
        fields = [f.strip() for f in line.split(",")]
        if len(fields) >= 4:
            items.append({
                "name": fields[0],
                "type": fields[1],
                "code": fields[2],
                "symbol": fields[3],
                "raw": line,
            })
    return items


def format_results(items: list) -> str:
    if not items:
        return "（未找到匹配结果）"
    lines = ["# 搜索结果（请与用户确认后再使用）"]
    for i, item in enumerate(items, 1):
        symbol = item.get("symbol") or item.get("code") or item.get("ticker") or ""
        name   = item.get("name") or item.get("short_name") or item.get("companyName") or ""
        market = item.get("market") or item.get("exchange") or item.get("market_name") or ""
        lines.append(f"{i:2d}.  {symbol:<15}  {name:<20}  {market}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="搜索金融标的 Symbol（调用 globalStockSearchSymbols，支持股票/基金/ETF/指数/债券等）"
    )
    parser.add_argument("--keyword", required=True, help="标的关键词（公司名、基金名、指数名、代码等）")
    parser.add_argument("--json",    action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    items = search_symbol(args.keyword)

    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(format_results(items))


if __name__ == "__main__":
    main()
