"""
query-meals adapter: API data → GenUI view model（方案 A + C）。

API 入参（unwrap 后的 data，见实时 discover_tools --json → query-meals → data）:
  - categories[]: { name, daypart?, meals: [{ code, tags? }] }
  - meals: { [code]: { name, currentPrice, image? } }

出参（仅供模板）:
  - categories[]: { name, items[] }（先按 name 合并 API 同名分类的 meals，再截断展示）
  - 展示上限：MAX_CATEGORIES × MAX_ITEMS_PER_CATEGORY
"""

from __future__ import annotations

from typing import Any, List

from _util import sanitize_text, visibility_if, yuan_parts_from_yuan

# 方案 C：控制 GenUI 菜单长度（可按产品调整）
MAX_CATEGORIES = 10
MAX_ITEMS_PER_CATEGORY = 20

MORE_HINT = "菜单较长，仅展示部分分类与餐品；可直接说想吃的餐品名继续查找。"

# 无 API 餐品图时使用麦当劳 CDN 占位图（GenUI Image.src 须为 https URL）
DEFAULT_MEAL_IMAGE = "https://img.mcd.cn/mini/main/images/default.png"


def _dedupe_meal_refs(refs: List[Any]) -> List[Any]:
    """同名分类合并后，按 code 去重（保留先出现的条目）。"""
    seen: set[str] = set()
    out: List[Any] = []
    for mc in refs:
        if not isinstance(mc, dict):
            continue
        code = mc.get("code")
        if not code:
            continue
        key = str(code)
        if key in seen:
            continue
        seen.add(key)
        out.append(mc)
    return out


def _merge_categories_by_name(categories: List[Any]) -> List[dict[str, Any]]:
    """按排序后的顺序，将同名分类的 meals 合并为一个分类。"""
    merged: List[dict[str, Any]] = []
    index_by_name: dict[str, int] = {}

    for cat in categories:
        if not isinstance(cat, dict):
            continue
        name = sanitize_text(cat.get("name"))
        if not name:
            continue
        meal_refs = cat.get("meals")
        if not isinstance(meal_refs, list) or not meal_refs:
            continue

        if name in index_by_name:
            merged[index_by_name[name]]["meals"].extend(meal_refs)
        else:
            index_by_name[name] = len(merged)
            merged.append({"name": name, "meals": list(meal_refs)})

    for cat in merged:
        cat["meals"] = _dedupe_meal_refs(cat["meals"])
    return [c for c in merged if c.get("meals")]


def _meal_item(
    code: str,
    detail: dict[str, Any],
    tags: List[Any],
    *,
    show_divider: bool,
) -> dict[str, Any]:
    tag_labels = [sanitize_text(t) for t in tags if sanitize_text(t)]
    image_url = str(detail.get("image") or "").strip() or DEFAULT_MEAL_IMAGE
    price_parts = yuan_parts_from_yuan(detail.get("currentPrice", ""))
    return {
        "code": code,
        "name": sanitize_text(detail.get("name")),
        "currentPriceSymbol": price_parts["symbol"],
        "currentPriceValue": price_parts["value"],
        "image": image_url,
        "hasImage": visibility_if(True),
        "tags": tag_labels,
        "showTags": visibility_if(bool(tag_labels)),
        "showDivider": visibility_if(show_divider),
    }


def adapt(data: Any) -> Any:
    categories_out: List[dict[str, Any]] = []
    truncated = False

    if not isinstance(data, dict):
        return _empty_view()

    categories = data.get("categories")
    meals_map = data.get("meals")
    if not isinstance(categories, list) or not isinstance(meals_map, dict):
        return _empty_view()

    def cat_rank(cat: Any) -> tuple[int, int]:
        if not isinstance(cat, dict):
            return (2, 0)
        name = sanitize_text(cat.get("name"))
        if "超值推荐" in name:
            return (0, 0)
        if "推荐" in name:
            return (1, 0)
        return (2, 0)

    sorted_cats = sorted(categories, key=cat_rank)
    merged = _merge_categories_by_name(sorted_cats)
    if len(merged) > MAX_CATEGORIES:
        truncated = True

    for cat in merged[:MAX_CATEGORIES]:
        cat_name = sanitize_text(cat.get("name"))
        meal_refs = cat.get("meals")
        if not isinstance(meal_refs, list):
            continue
        if len(meal_refs) > MAX_ITEMS_PER_CATEGORY:
            truncated = True

        refs_to_show: List[Any] = []
        for mc in meal_refs[:MAX_ITEMS_PER_CATEGORY]:
            if not isinstance(mc, dict):
                continue
            code = mc.get("code")
            if not code:
                continue
            refs_to_show.append(mc)

        items: List[dict[str, Any]] = []
        last_idx = len(refs_to_show) - 1
        for i, mc in enumerate(refs_to_show):
            code = mc.get("code")
            detail = meals_map.get(code)
            if not isinstance(detail, dict):
                detail = {"name": str(detail)} if detail is not None else {}
            tags = mc.get("tags") if isinstance(mc.get("tags"), list) else []
            items.append(
                _meal_item(
                    str(code),
                    detail,
                    tags,
                    show_divider=i < last_idx,
                )
            )

        if items:
            categories_out.append({"name": cat_name, "items": items})

    return {
        "categories": categories_out,
        "moreHint": MORE_HINT if truncated else "",
        "flags": {
            "showList": visibility_if(len(categories_out) > 0),
            "showMoreHint": visibility_if(truncated),
        },
    }


def _empty_view() -> dict[str, Any]:
    return {
        "categories": [],
        "moreHint": "",
        "flags": {
            "showList": visibility_if(False),
            "showMoreHint": visibility_if(False),
        },
    }


def validate(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("categories"), list)
