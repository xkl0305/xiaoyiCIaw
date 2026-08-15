"""
query-order adapter: API data -> GenUI view model for order status card.

Maps orderStatus to status label/color and footer variant (pay / hint / order id / locker).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List

from _util import (
    pick_amount,
    sanitize_text,
    visibility_if,
    yuan_parts_from_yuan,
)

_STATUS_RED = "#FFD9121B"
_STATUS_GRAY = "#99000000"
_CANCEL_HINT = "您的订单由于超时未支付被取消"
_DEFAULT_PRODUCT_IMAGE = "https://img.mcd.cn/mini/main/images/default.png"

# 接口 orderStatus 语义键（码值见 _STATUS_BY_CODE；现网返回值为中文，见 _STATUS_BY_LABEL）
STATUS_PENDING_PAY = "pending_pay"  # 10 待支付
STATUS_PAID = "paid"  # 20 已支付
STATUS_PAY_FAILED = "pay_failed"  # 21 支付失败
STATUS_STORE_CONFIRMED = "store_confirmed"  # 30 餐厅已确认
STATUS_RESTAURANT_CATERING = "restaurant_catering"  # 31/33 餐厅配餐中
STATUS_DELIVERY = "delivery"  # 32 订单配送中
STATUS_MEAL_SERVED = "meal_served"  # 34 待取餐
STATUS_CATERING_COMPLETED = "catering_completed"  # 35 配餐完成
STATUS_COMPLETED = "completed"  # 40 订单已完成
STATUS_CANCELLED = "cancelled"  # 60 订单已取消
STATUS_CANCEL_CHECKING = "cancel_checking"  # 61 取消审核中
STATUS_PART_REFUND = "part_refund"  # 70 部分退款
STATUS_ALL_REFUND = "all_refund"  # 80 整单退款
STATUS_REFUNDING = "refunding"  # 90 退款中

# 码值 string → 语义键（兜底；现网 orderStatus 以中文为准）
_STATUS_BY_CODE: dict[str, str] = {
    "10": STATUS_PENDING_PAY,
    "20": STATUS_PAID,
    "21": STATUS_PAY_FAILED,
    "30": STATUS_STORE_CONFIRMED,
    "31": STATUS_RESTAURANT_CATERING,
    "32": STATUS_DELIVERY,
    "33": STATUS_RESTAURANT_CATERING,
    "34": STATUS_MEAL_SERVED,
    "35": STATUS_CATERING_COMPLETED,
    "40": STATUS_COMPLETED,
    "60": STATUS_CANCELLED,
    "61": STATUS_CANCEL_CHECKING,
    "70": STATUS_PART_REFUND,
    "80": STATUS_ALL_REFUND,
    "90": STATUS_REFUNDING,
}

# 接口 orderStatus 真实返回值（中文）→ 语义键
_STATUS_BY_LABEL: dict[str, str] = {
    "待支付": STATUS_PENDING_PAY,
    "已支付": STATUS_PAID,
    "支付失败": STATUS_PAY_FAILED,
    "餐厅已确认": STATUS_STORE_CONFIRMED,
    "餐厅配餐中": STATUS_RESTAURANT_CATERING,
    "订单配送中": STATUS_DELIVERY,
    "待取餐": STATUS_MEAL_SERVED,
    "配餐完成": STATUS_CATERING_COMPLETED,
    "订单已完成": STATUS_COMPLETED,
    "订单已取消": STATUS_CANCELLED,
    "取消审核中": STATUS_CANCEL_CHECKING,
    "部分退款": STATUS_PART_REFUND,
    "整单退款": STATUS_ALL_REFUND,
    "退款中": STATUS_REFUNDING,
}

_STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    STATUS_PENDING_PAY: ("订单待支付", _STATUS_RED),
    STATUS_PAID: ("订单已支付", _STATUS_RED),
    STATUS_PAY_FAILED: ("支付失败", _STATUS_RED),
    STATUS_STORE_CONFIRMED: ("餐厅已确认", _STATUS_RED),
    STATUS_RESTAURANT_CATERING: ("餐厅配餐中", _STATUS_RED),
    STATUS_DELIVERY: ("配送中", _STATUS_RED),
    STATUS_MEAL_SERVED: ("待取餐", _STATUS_RED),
    STATUS_CATERING_COMPLETED: ("配餐完成", _STATUS_RED),
    STATUS_COMPLETED: ("订单已完成", _STATUS_GRAY),
    STATUS_CANCELLED: ("订单已取消", _STATUS_GRAY),
    STATUS_CANCEL_CHECKING: ("取消审核中", _STATUS_RED),
    STATUS_PART_REFUND: ("订单已退款(部分)", _STATUS_GRAY),
    STATUS_ALL_REFUND: ("订单已退款", _STATUS_GRAY),
    STATUS_REFUNDING: ("退款中", _STATUS_RED),
}

_STATUS_GRAY_KEYS = frozenset(
    {
        STATUS_COMPLETED,
        STATUS_CANCELLED,
        STATUS_PART_REFUND,
        STATUS_ALL_REFUND,
    }
)

_WAIT_HINT = "请耐心等待..."
_REFUND_HINT = "订单正在退款处理中，请耐心等待..."
_CANCEL_CHECKING_HINT = "订单取消请求正在审核中，请耐心等待..."
_PART_REFUND_HINT = "订单已完成部分退款"
_ALL_REFUND_HINT = "订单已完成退款"
_STORE_CONFIRMED_HINT = "餐厅已确认，正在等待配餐"
_PAID_WAIT_HINT = "请等待餐厅接单..."
_MEAL_READY_HINT = "餐品已备好，请取餐"
_CATERING_COMPLETED_HINT = "配餐已完成，请耐心等待..."


def _normalize_order_status(raw: str) -> str:
    s = sanitize_text(raw)
    if not s:
        return ""
    if s in _STATUS_BY_LABEL:
        return _STATUS_BY_LABEL[s]
    if s in _STATUS_BY_CODE:
        return _STATUS_BY_CODE[s]
    return s


def _unwrap_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("orderDetail"), dict):
        return data
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("orderDetail"), dict):
        return inner
    return data


def _order_context(root: dict[str, Any]) -> dict[str, Any]:
    """合并 data 顶层与 orderDetail，供状态/footer 逻辑读取。"""
    detail = root.get("orderDetail")
    if not isinstance(detail, dict):
        return root
    ctx = dict(detail)
    ctx["orderId"] = sanitize_text(root.get("orderId") or detail.get("orderId"))
    pay_url = sanitize_text(root.get("payH5Url"))
    if pay_url:
        ctx["payH5Url"] = pay_url
    return ctx


def _parse_expire_pay_time(raw: str) -> datetime | None:
    s = raw.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt)
            now = datetime.now()
            return t.replace(year=now.year, month=now.month, day=now.day)
        except ValueError:
            continue
    return None


def _expire_pay_time_short(raw: str) -> str:
    expire_dt = _parse_expire_pay_time(raw)
    if expire_dt is not None:
        return expire_dt.strftime("%H:%M")
    s = sanitize_text(raw)
    if not s:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        if len(s) >= len(fmt):
            tail = s[-5:]
            if ":" in tail:
                return tail
    return s


def _price_parts(root: dict[str, Any]) -> dict[str, str]:
    """realTotalAmount string 元口径 → ¥ + 两位小数。"""
    return yuan_parts_from_yuan(pick_amount(root, "realTotalAmount"))


def _status_display(order_status: str, *, has_locker: bool) -> tuple[str, str]:
    if has_locker:
        return "美味已入柜", _STATUS_RED
    status = _normalize_order_status(order_status)
    if status in _STATUS_DISPLAY:
        return _STATUS_DISPLAY[status]
    raw = sanitize_text(order_status)
    if raw:
        color = _STATUS_GRAY if status in _STATUS_GRAY_KEYS else _STATUS_RED
        return raw, color
    return "", _STATUS_GRAY


def _products(order_product_list: Any) -> List[dict[str, str]]:
    if not isinstance(order_product_list, list):
        return []
    out: List[dict[str, str]] = []
    for raw in order_product_list:
        if not isinstance(raw, dict):
            continue
        name = sanitize_text(raw.get("productName"))
        if not name:
            continue
        image = str(raw.get("productImage") or "").strip() or _DEFAULT_PRODUCT_IMAGE
        out.append({"productName": name, "productImage": image})
    return out


# 与 assets/genui/query-order.ndjson 餐品横滑区几何一致（装填期按 Harmony 卡片最大宽估算）
_CARD_MAX_WIDTH = 336
_PRODUCTS_ROW_PADDING_H = 12
_SCROLL_WRAP_WIDTH_RATIO = 0.80
_PRODUCT_ITEM_WIDTH = 75
_PRODUCT_ITEM_GAP = 8


def _products_list_viewport_width(card_content_width: float = _CARD_MAX_WIDTH) -> float:
    inner = card_content_width - _PRODUCTS_ROW_PADDING_H * 2
    return inner * _SCROLL_WRAP_WIDTH_RATIO


def _products_list_content_width(product_count: int) -> float:
    if product_count <= 0:
        return 0.0
    return (
        product_count * _PRODUCT_ITEM_WIDTH
        + (product_count - 1) * _PRODUCT_ITEM_GAP
    )


def _products_need_horizontal_scroll(product_count: int) -> bool:
    """餐品行总宽超过横滑视口时显示右缘淡出（非固定件数阈值）。"""
    if product_count <= 0:
        return False
    return _products_list_content_width(product_count) > _products_list_viewport_width()


def _item_count_display(order_product_list: Any) -> str:
    if not isinstance(order_product_list, list):
        return ""
    total = 0
    for raw in order_product_list:
        if not isinstance(raw, dict):
            continue
        try:
            total += int(raw.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
    if total <= 0:
        return ""
    return f"共{total}件"


def _pickup_code(root: dict[str, Any]) -> str:
    """取餐码（schema pickupCode）；无则不用 orderId 兜底。"""
    return sanitize_text(root.get("pickupCode"))


def _order_number_display(root: dict[str, Any]) -> str:
    """底栏「订单号」行展示值（配餐中状态用取餐码）。"""
    return _pickup_code(root)


def _show_pickup_footer(fields: dict[str, Any], pickup_display: str) -> dict[str, Any]:
    fields["footerOrderLabel"] = "订单号"
    fields["footerOrderValue"] = pickup_display
    fields["flags"]["showFooterOrderId"] = "visible"
    return fields


def _show_hint_footer(fields: dict[str, Any], hint: str) -> dict[str, Any]:
    fields["footerHint"] = hint
    fields["flags"]["showFooterHint"] = "visible"
    return fields


def _show_pay_footer(
    fields: dict[str, Any],
    *,
    prefix: str,
    pay_url: str,
) -> dict[str, Any]:
    fields["footerPayPrefix"] = prefix
    fields["footerPaySuffix"] = ""
    fields["flags"]["showFooterPay"] = "visible"
    fields["flags"]["showPayButton"] = visibility_if(bool(pay_url))
    return fields


def _footer_fields(root: dict[str, Any], order_status: str) -> dict[str, Any]:
    status = _normalize_order_status(order_status)
    locker_code = sanitize_text(root.get("lockerCode"))
    pay_url = sanitize_text(root.get("payH5Url"))

    empty = {
        "footerHint": "",
        "footerPayPrefix": "",
        "footerPayTime": "",
        "footerPaySuffix": "",
        "footerOrderLabel": "",
        "footerOrderValue": "",
        "footerLockerLabel": "",
        "footerLockerCode": "",
        "payH5Url": pay_url,
        "flags": {
            "showFooterHint": "none",
            "showFooterPay": "none",
            "showPayButton": "none",
            "showFooterOrderId": "none",
            "showFooterLocker": "none",
        },
    }

    if locker_code:
        empty["footerLockerLabel"] = "取餐柜密码 "
        empty["footerLockerCode"] = locker_code
        empty["flags"]["showFooterLocker"] = "visible"
        return empty

    if status == STATUS_PENDING_PAY:
        pay_time = _expire_pay_time_short(sanitize_text(root.get("expirePayTime")))
        empty["footerPayPrefix"] = "等待支付，请在 "
        empty["footerPayTime"] = pay_time
        empty["footerPaySuffix"] = " 前完成支付"
        empty["flags"]["showFooterPay"] = "visible"
        empty["flags"]["showPayButton"] = visibility_if(bool(pay_url))
        return empty

    if status == STATUS_PAY_FAILED:
        return _show_pay_footer(
            empty,
            prefix="支付未成功，请重新支付",
            pay_url=pay_url,
        )

    if status == STATUS_CANCELLED:
        return _show_hint_footer(empty, _CANCEL_HINT)

    if status == STATUS_CANCEL_CHECKING:
        return _show_hint_footer(empty, _CANCEL_CHECKING_HINT)

    if status == STATUS_COMPLETED:
        return _show_hint_footer(empty, "订单已准备完毕，喜欢您再来")

    if status == STATUS_PART_REFUND:
        return _show_hint_footer(empty, _PART_REFUND_HINT)

    if status == STATUS_ALL_REFUND:
        return _show_hint_footer(empty, _ALL_REFUND_HINT)

    if status == STATUS_REFUNDING:
        return _show_hint_footer(empty, _REFUND_HINT)

    if status == STATUS_STORE_CONFIRMED:
        return _show_hint_footer(empty, _STORE_CONFIRMED_HINT)

    if status == STATUS_RESTAURANT_CATERING:
        order_no = _order_number_display(root)
        if order_no:
            return _show_pickup_footer(empty, order_no)
        return _show_hint_footer(empty, _WAIT_HINT)

    if status == STATUS_DELIVERY:
        return _show_hint_footer(empty, _WAIT_HINT)

    if status == STATUS_PAID:
        return _show_hint_footer(empty, _PAID_WAIT_HINT)

    if status == STATUS_MEAL_SERVED:
        return _show_hint_footer(empty, _MEAL_READY_HINT)

    if status == STATUS_CATERING_COMPLETED:
        return _show_hint_footer(empty, _CATERING_COMPLETED_HINT)

    pickup_code = _pickup_code(root)
    if pickup_code:
        return _show_pickup_footer(empty, pickup_code)

    return empty


def adapt(data: Any) -> Any:
    root = _unwrap_data(data)
    ctx = _order_context(root)
    order_id = sanitize_text(ctx.get("orderId"))
    if not order_id:
        return data

    order_status = sanitize_text(ctx.get("orderStatus"))
    locker_code = sanitize_text(ctx.get("lockerCode"))
    store_address = sanitize_text(ctx.get("storeAddress"))
    products = _products(ctx.get("orderProductList"))
    item_count = _item_count_display(ctx.get("orderProductList"))
    price_parts = _price_parts(ctx)
    status_text, status_color = _status_display(
        order_status,
        has_locker=bool(locker_code),
    )
    footer = _footer_fields(ctx, order_status)
    status_is_gray = status_color == _STATUS_GRAY

    return {
        "orderId": order_id,
        "storeName": sanitize_text(ctx.get("storeName")),
        "storeAddress": store_address,
        "orderStatus": status_text,
        "products": products,
        "itemCountDisplay": item_count,
        "realTotalSymbol": price_parts["symbol"],
        "realTotalValue": price_parts["value"],
        "footerHint": footer["footerHint"],
        "footerPayPrefix": footer["footerPayPrefix"],
        "footerPayTime": footer["footerPayTime"],
        "footerPaySuffix": footer["footerPaySuffix"],
        "footerOrderLabel": footer["footerOrderLabel"],
        "footerOrderValue": footer["footerOrderValue"],
        "footerLockerLabel": footer["footerLockerLabel"],
        "footerLockerCode": footer["footerLockerCode"],
        "payH5Url": footer["payH5Url"],
        "flags": {
            "showStoreAddress": visibility_if(bool(store_address)),
            "showProducts": visibility_if(bool(products)),
            "showProductsScrollFade": visibility_if(
                _products_need_horizontal_scroll(len(products))
            ),
            "showOrderStatusRed": visibility_if(bool(status_text) and not status_is_gray),
            "showOrderStatusGray": visibility_if(bool(status_text) and status_is_gray),
            **footer["flags"],
        },
    }


def validate(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return bool(sanitize_text(data.get("orderId"))) and bool(
        sanitize_text(data.get("orderStatus"))
    )
