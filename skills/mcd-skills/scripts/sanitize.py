"""
Text normalization for MCP / adapter / GenUI pipelines.

GenUI Text.content must not contain newlines; API fields may include \\n.
"""

from __future__ import annotations

from typing import Any


def sanitize_text(value: Any) -> str:
    """Remove \\r\\n / \\n / \\r from display text and trim edges."""
    s = str(value or "")
    return s.replace("\r\n", "").replace("\n", "").replace("\r", "").strip()


def sanitize_query_meals_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize query-meals API payload: categories[].name, meals{}.name, tags."""
    if not isinstance(data, dict):
        return data

    result = dict(data)

    categories = result.get("categories")
    if isinstance(categories, list):
        new_cats: list[Any] = []
        for cat in categories:
            if not isinstance(cat, dict):
                new_cats.append(cat)
                continue
            cat_copy = dict(cat)
            if "name" in cat_copy:
                cat_copy["name"] = sanitize_text(cat_copy.get("name"))
            meal_refs = cat_copy.get("meals")
            if isinstance(meal_refs, list):
                new_refs: list[Any] = []
                for mc in meal_refs:
                    if not isinstance(mc, dict):
                        new_refs.append(mc)
                        continue
                    mc_copy = dict(mc)
                    tags = mc_copy.get("tags")
                    if isinstance(tags, list):
                        mc_copy["tags"] = [
                            sanitize_text(t) for t in tags if sanitize_text(t)
                        ]
                    new_refs.append(mc_copy)
                cat_copy["meals"] = new_refs
            new_cats.append(cat_copy)
        result["categories"] = new_cats

    meals = result.get("meals")
    if isinstance(meals, dict):
        new_meals: dict[str, Any] = {}
        for code, detail in meals.items():
            if isinstance(detail, dict):
                d = dict(detail)
                if "name" in d:
                    d["name"] = sanitize_text(d.get("name"))
                new_meals[str(code)] = d
            elif detail is not None:
                new_meals[str(code)] = sanitize_text(detail)
            else:
                new_meals[str(code)] = detail
        result["meals"] = new_meals

    return result
