"""
create-order adapter: structural mapping only.

Flattens orderDetail to top-level fields; optional blocks use flags + visibility.
"""

from __future__ import annotations

from typing import Any, List

from _util import (
    amount_positive,
    key_present,
    pick_amount,
    quantity_display,
    sanitize_text,
    visibility_if,
    yuan_parts_from_yuan,
)


def _amount_parts(amount: Any) -> dict[str, str]:
    return yuan_parts_from_yuan(amount)


def _compact_amount(amount: Any) -> str:
    parts = _amount_parts(amount)
    if not parts["symbol"] or not parts["value"]:
        return ""
    value = parts["value"]
    if value.endswith(".00"):
        value = value[:-3]
    return f"{parts['symbol']} {value}"


def _unwrap_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("orderDetail"), dict):
        return data
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("orderDetail"), dict):
        return inner
    return data


def _product_items(order_product_list: Any) -> List[dict[str, str]]:
    items: List[dict[str, str]] = []
    if not isinstance(order_product_list, list):
        return items
    for p in order_product_list:
        if not isinstance(p, dict):
            continue
        combo_items = p.get("comboItemList")
        if isinstance(combo_items, list) and combo_items:
            for c in combo_items:
                if not isinstance(c, dict):
                    continue
                name = sanitize_text(c.get("itemName"))
                if not name:
                    continue
                items.append(
                    {
                        "itemName": name,
                        "quantity": quantity_display(c.get("itemQuantity")),
                    }
                )
            continue
        name = sanitize_text(p.get("productName"))
        if not name:
            continue
        items.append(
            {
                "itemName": name,
                "quantity": quantity_display(p.get("quantity")),
            }
        )
    return items


def _delivery_info(delivery_info: Any) -> dict[str, str]:
    empty = {
        "deliveryAddress": "",
        "customerNickname": "",
        "mobilePhone": "",
        "expectDeliveryTime": "",
        "customerLine": "",
        "addressLine": "",
        "expectLine": "",
    }
    if not isinstance(delivery_info, dict):
        return empty
    address = sanitize_text(
        delivery_info.get("deliveryAddress")
        or delivery_info.get("addressDetail")
        or ""
    )
    customer = sanitize_text(delivery_info.get("customerNickname"))
    phone = sanitize_text(delivery_info.get("mobilePhone"))
    expect = sanitize_text(delivery_info.get("expectDeliveryTime"))
    customer_line = " ".join(part for part in (customer, phone) if part)
    return {
        "deliveryAddress": address,
        "customerNickname": customer,
        "mobilePhone": phone,
        "expectDeliveryTime": expect,
        "customerLine": customer_line,
        "addressLine": address,
        "expectLine": f"预计{expect}送达" if expect else "",
    }


def _has_delivery(delivery_info: dict[str, str]) -> bool:
    return any(delivery_info.get(k) for k in delivery_info)


def _take_way_display(raw_take_way: Any, *, has_delivery: bool) -> str:
    raw = sanitize_text(raw_take_way)
    if not raw:
        return "外送" if has_delivery else ""
    if "外送" in raw or "配送" in raw:
        return "外送"
    if "外带" in raw:
        return "外带"
    if "堂食" in raw or "自提" in raw or "到店" in raw:
        return "堂食"
    return "外送" if has_delivery else raw


def _fee_summary(detail: dict[str, Any]) -> str:
    parts: List[str] = []
    packing = pick_amount(detail, "realPackingFeeTotalPrice", "packingPrice")
    delivery = pick_amount(detail, "realDeliveryPrice", "deliveryPrice")
    tableware = pick_amount(detail, "tablewarePrice")
    if amount_positive(packing):
        parts.append(f"打包费 {_compact_amount(packing)}")
    if amount_positive(delivery):
        parts.append(f"外送费 {_compact_amount(delivery)}")
    if amount_positive(tableware):
        parts.append(f"餐具费 {_compact_amount(tableware)}")
    return f"含{'，'.join(parts)}" if parts else ""


def adapt(data: Any) -> Any:
    root = _unwrap_data(data)
    detail = root.get("orderDetail")
    if not isinstance(detail, dict):
        return data

    order_id = sanitize_text(root.get("orderId") or detail.get("orderId"))
    pay_url = sanitize_text(root.get("payH5Url"))
    product_items = _product_items(detail.get("orderProductList"))
    delivery_info = _delivery_info(detail.get("deliveryInfo"))

    discount_raw = detail.get("totalDiscountAmount")
    show_discount = key_present(detail, "totalDiscountAmount") and amount_positive(
        discount_raw
    )
    show_delivery = key_present(detail, "deliveryInfo") and _has_delivery(delivery_info)
    take_way = _take_way_display(detail.get("takeWay"), has_delivery=show_delivery)
    show_products = len(product_items) > 0
    show_pay = bool(pay_url)
    fee_summary = _fee_summary(detail)
    show_fee_summary = bool(fee_summary)
    show_take_way = bool(take_way)

    real_parts = yuan_parts_from_yuan(pick_amount(detail, "realTotalAmount"))
    discount_parts = (
        yuan_parts_from_yuan(discount_raw)
        if show_discount
        else {"symbol": "", "value": ""}
    )

    return {
        "orderId": order_id,
        "payH5Url": pay_url,
        "storeName": sanitize_text(detail.get("storeName")),
        "orderStatus": sanitize_text(detail.get("orderStatus")),
        "createTime": sanitize_text(detail.get("createTime")),
        "takeWayDisplay": take_way,
        "feeSummaryLine": fee_summary,
        "discountNegative": "-" if show_discount else "",
        "discountSymbol": discount_parts["symbol"],
        "discountValue": discount_parts["value"],
        "realTotalSymbol": real_parts["symbol"],
        "realTotalValue": real_parts["value"],
        "payButtonSymbol": real_parts["symbol"] if show_pay else "",
        "payButtonValue": real_parts["value"] if show_pay else "",
        "productItems": product_items,
        "deliveryInfo": delivery_info,
        "flags": {
            "showDelivery": visibility_if(show_delivery),
            "showDiscount": visibility_if(show_discount),
            "showFeeSummary": visibility_if(show_fee_summary),
            "showProducts": visibility_if(show_products),
            "showTakeWay": visibility_if(show_take_way),
            "showPay": visibility_if(show_pay),
        },
    }


def validate(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return bool(sanitize_text(data.get("orderId")))
