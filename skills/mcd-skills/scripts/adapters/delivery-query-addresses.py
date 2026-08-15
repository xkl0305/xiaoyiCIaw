"""
delivery-query-addresses adapter: API data -> GenUI view model.

API data:
  - addresses[]: { addressId, contactName, fullAddress, phone }

Template view:
  - addresses[]: { addressId, fullAddress, contactDisplay, showContact, showDivider }
  - flags.showList / flags.showListScroll / flags.showEmpty
    (<=6 items: showList; >6 items: showListScroll with fixed height)
"""

from __future__ import annotations

import re
from typing import Any, List

from _util import sanitize_text, visibility_if

# Address count at/below this uses auto-height List; above uses fixed-height scroll List.
_LIST_SCROLL_THRESHOLD = 6


def _unwrap_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    addresses = data.get("addresses")
    if isinstance(addresses, list):
        return data
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("addresses"), list):
        return inner
    return data


def _mask_phone(phone: Any) -> str:
    s = sanitize_text(phone)
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 11:
        return f"{digits[:3]}****{digits[-4:]}"
    return s


def _pick_phone(raw: dict[str, Any]) -> str:
    for key in ("phone", "mobilePhone", "mobile"):
        value = sanitize_text(raw.get(key))
        if value:
            return value
    return ""


def _contact_display(contact_name: Any, phone: Any) -> str:
    name = sanitize_text(contact_name)
    masked_phone = _mask_phone(phone)
    if name and masked_phone:
        return f"{name} {masked_phone}"
    return name or masked_phone


def _address_item(raw: Any, *, show_divider: bool) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    full_address = sanitize_text(raw.get("fullAddress"))
    contact_display = _contact_display(
        raw.get("contactName"),
        _pick_phone(raw),
    )
    if not full_address and not contact_display:
        return None
    return {
        "addressId": sanitize_text(raw.get("addressId")),
        "fullAddress": full_address,
        "contactDisplay": contact_display,
        "showContact": visibility_if(bool(contact_display)),
        "showDivider": visibility_if(show_divider),
    }


def _empty_view() -> dict[str, Any]:
    return {
        "addresses": [],
        "flags": {
            "showList": "none",
            "showListScroll": "none",
            "showEmpty": "visible",
        },
    }


def adapt(data: Any) -> Any:
    root = _unwrap_data(data)
    raw_addresses = root.get("addresses")
    if not isinstance(raw_addresses, list):
        return _empty_view()

    addresses: List[dict[str, Any]] = []
    for index, raw in enumerate(raw_addresses):
        item = _address_item(raw, show_divider=index < len(raw_addresses) - 1)
        if item is not None:
            addresses.append(item)

    if not addresses:
        return _empty_view()

    addresses[-1]["showDivider"] = "none"
    n = len(addresses)
    return {
        "addresses": addresses,
        "flags": {
            "showList": visibility_if(n <= _LIST_SCROLL_THRESHOLD),
            "showListScroll": visibility_if(n > _LIST_SCROLL_THRESHOLD),
            "showEmpty": "none",
        },
    }


def validate(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("addresses"), list)
