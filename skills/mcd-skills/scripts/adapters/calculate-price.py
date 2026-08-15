"""
calculate-price adapter: structural mapping + display strings for genui paths.
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
    yuan_parts_from_cents,
)


def _format_product(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {
            "productName": "",
            "quantity": "x1",
            "gap": "",
            "subtotalSymbol": "",
            "subtotalValue": "",
        }
    name = sanitize_text(row.get("productName"))
    qty = row.get("quantity", 1)
    sub = row.get("subtotal")
    if sub is None:
        sub = row.get("originalSubtotal")
    parts = yuan_parts_from_cents(sub)
    return {
        "productName": name,
        "quantity": quantity_display(qty),
        "gap": "",
        "subtotalSymbol": parts["symbol"],
        "subtotalValue": parts["value"],
    }


def adapt(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    product_list = data.get("productList")
    if not isinstance(product_list, list):
        product_list = []

    price = data.get("price")
    if price is None:
        price = data.get("originalPrice")

    discount = data.get("discount")
    show_discount = key_present(data, "discount") and amount_positive(discount)
    show_delivery = key_present(data, "deliveryPrice", "deliveryOriginalPrice")
    show_packing = key_present(data, "packingPrice", "packingOriginalPrice")
    show_fees_col = show_delivery or show_packing or show_discount

    price_parts = yuan_parts_from_cents(price if price is not None else 0)
    delivery_parts = yuan_parts_from_cents(
        pick_amount(data, "deliveryPrice", "deliveryOriginalPrice")
    )
    packing_parts = yuan_parts_from_cents(
        pick_amount(data, "packingPrice", "packingOriginalPrice")
    )
    discount_parts = (
        yuan_parts_from_cents(discount) if show_discount else {"symbol": "", "value": ""}
    )

    return {
        "productList": [_format_product(p) for p in product_list],
        "priceSymbol": price_parts["symbol"],
        "priceValue": price_parts["value"],
        "flags": {
            "showDelivery": visibility_if(show_delivery),
            "showPacking": visibility_if(show_packing),
            "showDiscount": visibility_if(show_discount),
            "showFeesCol": visibility_if(show_fees_col),
        },
        "deliveryPriceSymbol": delivery_parts["symbol"],
        "deliveryPriceValue": delivery_parts["value"],
        "packingPriceSymbol": packing_parts["symbol"],
        "packingPriceValue": packing_parts["value"],
        "discountNegative": "-" if show_discount else "",
        "discountSymbol": discount_parts["symbol"],
        "discountValue": discount_parts["value"],
    }


def validate(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("productList"), list):
        return False
    value = data.get("priceValue")
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None
