#!/usr/bin/env python3
"""基金搜索 - globalStockSearchSymbols
用法: python3 search_fund.py <关键词> [数量=4]
"""
import sys, urllib.request, urllib.parse

def main():
    if len(sys.argv) < 2:
        print("用法: python3 search_fund.py <关键词> [数量=4]")
        sys.exit(1)

    key = sys.argv[1]
    num = sys.argv[2] if len(sys.argv) > 2 else "4"

    params = urllib.parse.urlencode({
        "type": "21,202,203,204,205",
        "key": key,
        "format": "text",
        "num": num,
    })
    url = f"https://mcp.finance.sina.com.cn/api-call/globalStockSearchSymbols?{params}"
    try:
        from auth import get_auth_headers as _auth_get_auth_headers
        headers = _auth_get_auth_headers()
    except SystemExit:
        raise
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    # 接口 Header 标注 UTF-8 但实际返回 GBK 编码文本
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace").strip()

    if not text:
        print("未找到匹配的基金")
        return

    print(f"搜索「{key}」的基金结果：")
    print(f"{'代码':<12} {'名称':<20} {'状态'}")
    print("-" * 45)
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) >= 9:
            code = parts[2].strip()
            name = parts[4].strip()
            status = "上市" if parts[8].strip() == "1" else "退市"
            print(f"{code:<12} {name:<20} {status}")

if __name__ == "__main__":
    main()
