"""
Shared helpers for per-tool adapters.

Adapters: structural mapping + display formatting (¥、xN 等).
Templates only use {"path": "/..."} per genui 协议；禁止 transform 等非协议字段。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from sanitize import sanitize_text  # noqa: E402


def yuan_display(amount: Any) -> str:
    """元口径字符串（或已有 ¥）→ ¥xx.xx。"""
    if amount is None or amount == "":
        return ""
    s = str(amount).strip()
    if not s:
        return ""
    if s.startswith("¥"):
        inner = s.lstrip("¥").strip()
        return f"¥{inner}" if inner else ""
    return f"¥{s}"


def yuan_parts_from_yuan(amount: Any, *, negative: bool = False) -> dict[str, str]:
    """订单类 API 元口径 → {symbol: '¥', value: '37.00'}；不除以 100。"""
    if amount is None or amount == "":
        return {"symbol": "", "value": ""}
    s = str(amount).strip()
    if not s:
        return {"symbol": "", "value": ""}
    prefix = ""
    if s.startswith("-"):
        prefix = "-"
        s = s[1:].strip()
    s = s.lstrip("¥").strip()
    if not s:
        return {"symbol": "", "value": ""}
    try:
        num = f"{abs(float(s)):.2f}"
        if negative:
            num = f"-{num}"
        elif prefix:
            num = f"{prefix}{num}"
        return {"symbol": "¥", "value": num}
    except (TypeError, ValueError):
        full = yuan_display(amount)
        if not full.startswith("¥"):
            return {"symbol": "", "value": full}
        return {"symbol": "¥", "value": full.lstrip("¥").strip()}


def yuan_from_cents(amount: Any) -> str:
    """API 分（string 或整数，如 \"4380\"）→ ¥xx.xx。"""
    if amount is None or amount == "":
        return ""
    try:
        return f"¥{int(amount) / 100:.2f}"
    except (TypeError, ValueError):
        return yuan_display(amount)


def yuan_parts_from_cents(amount: Any, *, negative: bool = False) -> dict[str, str]:
    """API 分（schema type string，如 \"4380\"）→ {symbol: '¥', value: '43.80'}。"""
    if amount is None or amount == "":
        return {"symbol": "", "value": ""}
    try:
        val = abs(int(amount)) / 100
        num = f"{val:.2f}"
        if negative:
            num = f"-{num}"
        return {"symbol": "¥", "value": num}
    except (TypeError, ValueError):
        full = yuan_display(amount)
        if not full:
            return {"symbol": "", "value": ""}
        s = full.strip()
        prefix = ""
        if s.startswith("-"):
            prefix = "-"
            s = s[1:].strip()
        if s.startswith("¥"):
            return {"symbol": "¥", "value": f"{prefix}{s[1:].strip()}"}
        return {"symbol": "", "value": full}


def quantity_display(qty: Any) -> str:
    try:
        return f"x{int(qty)}"
    except (TypeError, ValueError):
        return "x1"


def key_present(data: dict[str, Any], *keys: str) -> bool:
    return any(k in data and data[k] is not None for k in keys)


def pick_amount(data: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return 0


def visibility_for_keys(data: dict[str, Any], *keys: str) -> str:
    return "visible" if key_present(data, *keys) else "none"


def visibility_if(show: bool) -> str:
    return "visible" if show else "none"


def amount_positive(value: Any) -> bool:
    if value is None or value == "":
        return False
    try:
        s = str(value).strip().lstrip("¥").strip()
        if not s:
            return False
        return float(s) > 0
    except (TypeError, ValueError):
        return bool(str(value).strip())
