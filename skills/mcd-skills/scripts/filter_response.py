#!/usr/bin/env python3
"""
MCP 响应过滤器 - 将 --extract 输出的业务 JSON 转为精简文本

使用方式:
  bash scripts/call_tool.sh --extract query-meals '...' | python3 scripts/filter_response.py meals
  bash scripts/call_tool.sh --extract query-meals '...' | python3 scripts/filter_response.py meals --search 汉堡
  bash scripts/call_tool.sh --extract calculate-price '...' | python3 scripts/filter_response.py price
"""

import json
import sys


def filter_meals(data, search=None):
    meals = data.get("meals", {})
    categories = data.get("categories", [])
    if not categories or not meals:
        print("暂无可售餐品")
        return
    for cat in categories:
        items = []
        for mc in cat.get("meals", []):
            code = mc.get("code", "")
            if code in meals:
                m = meals[code]
                name = m.get("name", "")
                if search and search not in name:
                    continue
                items.append((code, name, m.get("currentPrice", "")))
        if items:
            print(f"\n[{cat.get('name', '')}]")
            for code, name, price in items:
                print(f"  {name} ¥{price} code:{code}")


def filter_price(data):
    products = data.get("products", [])
    if products:
        print("商品明细:")
        for p in products:
            name = p.get("productName", "")
            qty = p.get("quantity", 1)
            subtotal = p.get("subtotal", 0)
            print(f"  {name} x{qty} ¥{int(subtotal)/100:.2f}")
    price = data.get("price", 0)
    discount = data.get("discount", 0)
    delivery = data.get("deliveryPrice", 0)
    packing = data.get("packingPrice", 0)
    print(f"\n优惠: -¥{int(discount)/100:.2f}")
    if delivery:
        print(f"外送费: ¥{int(delivery)/100:.2f}")
    if packing:
        print(f"打包费: ¥{int(packing)/100:.2f}")
    print(f"应付总额: ¥{int(price)/100:.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    search = None
    if "--search" in sys.argv:
        idx = sys.argv.index("--search")
        if idx + 1 < len(sys.argv):
            search = sys.argv[idx + 1]

    raw = sys.stdin.read()
    if not raw.strip():
        print("错误: 未收到数据，上游调用可能失败", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("错误: 上游返回非 JSON 数据，可能是接口调用失败", file=sys.stderr)
        for line in raw.strip().splitlines()[:5]:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                print(f"  {stripped}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict) and data.get("success") is False:
        msg = data.get("message", "未知错误")
        code = data.get("code", "")
        print(f"接口错误: {msg} (code={code})", file=sys.stderr)
        sys.exit(1)

    if mode == "meals":
        filter_meals(data, search)
    elif mode == "price":
        filter_price(data)
    else:
        print(f"未知模式: {mode}", file=sys.stderr)
        print("支持: meals, price", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
