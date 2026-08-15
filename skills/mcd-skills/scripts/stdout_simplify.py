"""
Flatten agent-visible stdout when DSL card is rendered (isShowCard=true).

Full business data is still used for render_local / DSL file. query-meals strips
nested menu JSON to a simplify list on stdout; query-order normalizes orderStatus
when lockerCode is present; other DSL tools keep full business JSON alongside
a2uiCard.
"""

from __future__ import annotations

from typing import Callable

from sanitize import sanitize_text

DSL_TOOLS = frozenset(
    {
        "query-meals",
        "calculate-price",
        "create-order",
        "query-order",
        "delivery-query-addresses",
    }
)


def _norm_tool(tool_name: str) -> str:
    return (tool_name or "").strip().lower()


def _build_meals_simplify_lines(categories: list, meals: dict) -> list[str]:
    lines: list[str] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        for mc in cat.get("meals") or []:
            if not isinstance(mc, dict):
                continue
            code = mc.get("code", "")
            if not code or code not in meals:
                continue
            m = meals[code]
            name = m.get("name", "")
            price = m.get("currentPrice", "")
            lines.append(f"{name} ¥{price} code:{code}")
    return lines


def simplify_query_meals(data: dict) -> dict:
    return {
        "simplify": _build_meals_simplify_lines(
            data.get("categories") or [], data.get("meals") or {}
        )
    }


def normalize_query_order_stdout(data: dict) -> dict:
    result = dict(data)
    locker = sanitize_text(result.get("lockerCode"))
    if not locker:
        detail = result.get("orderDetail")
        if isinstance(detail, dict):
            locker = sanitize_text(detail.get("lockerCode"))
    if locker:
        result["orderStatus"] = "美味已入柜"
        if isinstance(result.get("orderDetail"), dict):
            detail = dict(result["orderDetail"])
            detail["orderStatus"] = "美味已入柜"
            result["orderDetail"] = detail
    return result


_SIMPLIFIERS: dict[str, Callable[[dict], dict]] = {
    "query-meals": simplify_query_meals,
    "query-order": normalize_query_order_stdout,
}


def simplify_agent_output(tool_name: str, data: dict) -> dict:
    """Return flattened stdout fields for the given tool and business data."""
    if not isinstance(data, dict):
        return {"simplify": []}
    fn = _SIMPLIFIERS.get(_norm_tool(tool_name))
    if fn is None:
        return dict(data)
    return fn(data)


def apply_flat_stdout(out: dict, tool_name: str, data: dict) -> None:
    """When isShowCard=true, replace stdout business JSON per tool simplifier."""
    if not out.get("isShowCard"):
        return
    if not isinstance(data, dict):
        data = {}
    flat = simplify_agent_output(tool_name, data)
    preserved = {
        k: out[k]
        for k in ("isShowCard", "a2uiCard", "genui")
        if k in out
    }
    out.clear()
    out.update(flat)
    out.update(preserved)
