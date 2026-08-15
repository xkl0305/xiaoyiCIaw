#!/usr/bin/env python3
"""
MCP 工具调用 + 可选 GenUI 装填（Agent 唯一脚本入口）。

用法:
    python scripts/call_tool_for_genui.py [--extract] [--filter_mode <mode>] \\
        [--search <term>] [--max_categories <N>] [--max_items_per_category <N>] \\
        [--dsl-file <path>] [--genui-inline] \\
        <tool-name> '<json-args>'

选项:
    --extract                      提取 structuredContent.data 业务字段
    --filter_mode <mode>           过滤模式（仅支持 meals），从 stdin 读取 JSON
    --search <term>                搜索关键词（配合 --filter_mode meals）
    --max_categories <N>           截断分类数量上限（默认 10）
    --max_items_per_category <N>   每分类餐品数量上限（默认 20）
    --dsl-file <path>              GenUI DSL 落盘路径（默认 /tmp/a2uidsl.txt 或 MCD_A2UI_DSL_PATH）
    --genui-inline                 调试：将 genui 围栏 inline 进 stdout，不写文件

出参（stdout）:
    - 每次 --extract 均含布尔字段 "isShowCard"（true=DSL 卡片已落盘，false=走 Markdown）
    - 有 DSL 且装填成功：isShowCard=true + a2uiCard；query-meals 另有 simplify（菜单压平）
    - 其余有模板工具：isShowCard=true 时 stdout 仍含完整业务 JSON + a2uiCard
    - 无 DSL / 装填失败：isShowCard=false + 完整业务 JSON，无 a2uiCard

Agent 用法:
    - isShowCard=true 且系统提示词版本达标：toolCall displayA2UICardByPath；总结≤20 字
    - isShowCard=false，或版本不达标：按 guide 纯 Markdown（详见 output.md）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from a2ui_card import attach_ui_output  # noqa: E402
from call_tool import call_mcp_tool  # noqa: E402
from genui import has_genui_template, render_local, unwrap_mcp_data  # noqa: E402
from sanitize import sanitize_query_meals_data, sanitize_text  # noqa: E402
from stdout_simplify import apply_flat_stdout, simplify_agent_output  # noqa: E402


def render_ui_if_supported(tool_name: str, raw_data: Any) -> str:
    """Render GenUI when template exists; version gate is enforced at Phase 3 display."""
    if not has_genui_template(tool_name):
        return ""
    return render_local(tool_name, raw_data)


def apply_filter(
    data: dict,
    filter_mode: str,
    search: str | None = None,
    max_cats: int | None = None,
    max_items: int | None = None,
) -> dict:
    """Filter extracted business data, preserving structure for genui rendering.

    Args:
        data: Extracted business data (e.g. structuredContent.data).
        filter_mode: Filter mode name (currently only "meals").
        search: Optional search term matched against meal names.
        max_cats: Override _MAX_MEALS_CATEGORIES (None → use default).
        max_items: Override _MAX_MEALS_ITEMS_PER_CATEGORY (None → use default).

    Returns:
        Filtered dict with the same top-level keys, compatible with adapter input.
    """
    if filter_mode == "meals":
        return _filter_meals_data(data, search, max_cats=max_cats, max_items=max_items)
    return data


# ---------------------------------------------------------------------------
# 截断常量（与 adapters/query-meals.py 保持一致）
# ---------------------------------------------------------------------------
_MAX_MEALS_CATEGORIES = 10
_MAX_MEALS_ITEMS_PER_CATEGORY = 20


def _cat_rank(cat: dict) -> tuple[int, int]:
    """分类排序优先级：超值推荐 → 推荐 → 其他（与 adapter 一致）。"""
    name = str(cat.get("name") or "")
    if "超值推荐" in name:
        return (0, 0)
    if "推荐" in name:
        return (1, 0)
    return (2, 0)


def _truncate_meals(
    categories: list[dict],
    meals: dict,
    max_cats: int | None = None,
    max_items: int | None = None,
) -> tuple[list[dict], set[str]]:
    """Sort categories by priority, truncate to display limits.

    Args:
        max_cats: Override _MAX_MEALS_CATEGORIES (None → use default).
        max_items: Override _MAX_MEALS_ITEMS_PER_CATEGORY (None → use default).

    Returns (truncated_categories, kept_codes).
    """
    cat_limit = max_cats if max_cats is not None else _MAX_MEALS_CATEGORIES
    item_limit = max_items if max_items is not None else _MAX_MEALS_ITEMS_PER_CATEGORY

    sorted_cats = sorted(categories, key=_cat_rank)
    kept_codes: set[str] = set()

    truncated_cats: list[dict] = []
    for cat in sorted_cats[:cat_limit]:
        meal_refs = cat.get("meals")
        if not isinstance(meal_refs, list):
            continue
        truncated_refs = meal_refs[:item_limit]
        for mc in truncated_refs:
            if isinstance(mc, dict) and mc.get("code"):
                kept_codes.add(str(mc["code"]))
        cat_copy = dict(cat)
        cat_copy["meals"] = truncated_refs
        truncated_cats.append(cat_copy)

    return truncated_cats, kept_codes


def _dedupe_meal_refs(refs: list[dict]) -> list[dict]:
    """去重：按 code 保留先出现的条目（对齐 adapter 逻辑）。"""
    seen: set[str] = set()
    out: list[dict] = []
    for mc in refs:
        code = str(mc.get("code", ""))
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(mc)
    return out


def _filter_meals_data(
    data: dict,
    search: str | None = None,
    max_cats: int | None = None,
    max_items: int | None = None,
) -> dict:
    """Filter query-meals data: remove non-matching meals, drop empty categories.

    Categories whose meals all fail the search are removed.  Meals not referenced
    by any surviving category are also pruned from the meals map.

    Args:
        max_cats: Override _MAX_MEALS_CATEGORIES (None → use default).
        max_items: Override _MAX_MEALS_ITEMS_PER_CATEGORY (None → use default).
    """
    data = sanitize_query_meals_data(data)

    categories = data.get("categories")
    meals = data.get("meals")
    if not isinstance(categories, list) or not isinstance(meals, dict):
        return data

    kept_codes: set[str] = set()
    filtered_cats: list[dict] = []

    for cat in categories:
        if not isinstance(cat, dict):
            continue
        cat_meal_refs = cat.get("meals")
        if not isinstance(cat_meal_refs, list):
            continue

        filtered_refs: list[dict] = []
        for mc in cat_meal_refs:
            if not isinstance(mc, dict):
                continue
            code = mc.get("code")
            if not code or code not in meals:
                continue
            meal_name = str(meals[code].get("name", ""))
            if search and search not in meal_name:
                continue
            filtered_refs.append(mc)
            kept_codes.add(str(code))

        if filtered_refs:
            cat_copy = dict(cat)
            cat_copy["meals"] = filtered_refs
            filtered_cats.append(cat_copy)

    # Merge same-name categories (align with adapter's _merge_categories_by_name)
    merged_cats: list[dict] = []
    index_by_name: dict[str, int] = {}
    for cat in filtered_cats:
        name = sanitize_text(cat.get("name"))
        if not name:
            continue
        meal_refs = cat.get("meals")
        if not isinstance(meal_refs, list) or not meal_refs:
            continue
        if name in index_by_name:
            merged_cats[index_by_name[name]]["meals"].extend(meal_refs)
        else:
            index_by_name[name] = len(merged_cats)
            merged_cats.append({"name": name, "meals": list(meal_refs)})
    for cat in merged_cats:
        cat["meals"] = _dedupe_meal_refs(cat["meals"])
    merged_cats = [c for c in merged_cats if c.get("meals")]

    # Truncate to display limits (sort, cap categories, cap items per category)
    truncated_cats, kept_codes = _truncate_meals(
        merged_cats, meals, max_cats=max_cats, max_items=max_items
    )

    filtered_meals = {
        code: detail for code, detail in meals.items() if code in kept_codes
    }

    result = dict(data)
    result["categories"] = truncated_cats
    result["meals"] = filtered_meals
    return result


def _is_query_meals(tool_name: str) -> bool:
    return (tool_name or "").strip().lower() == "query-meals"


def build_output(
    raw_data: Any,
    tool_name: str,
    *,
    genui_inline: bool = False,
    dsl_file: str | None = None,
) -> Any:
    """Merge MCP JSON-RPC envelope with optional a2uiCard (DSL written to file)."""
    if not isinstance(raw_data, dict):
        return {"result": raw_data}

    ui_code = render_ui_if_supported(tool_name, raw_data)
    merged = dict(raw_data)
    attach_ui_output(
        merged,
        tool_name,
        ui_code,
        genui_inline=genui_inline,
        dsl_file=dsl_file,
    )

    result = merged.get("result")
    if isinstance(result, dict):
        sc = result.get("structuredContent")
        if isinstance(sc, dict):
            data = sc.get("data")
            if isinstance(data, dict) and merged.get("isShowCard"):
                merged["result"] = {
                    **result,
                    "structuredContent": {
                        **sc,
                        "data": simplify_agent_output(tool_name, data),
                    },
                }

    return merged


def build_extract_output(
    raw_data: dict,
    tool_name: str,
    *,
    genui_inline: bool = False,
    dsl_file: str | None = None,
) -> dict:
    """Merge structuredContent.data fields with optional a2uiCard (DSL written to file)."""
    sc = raw_data.get("result", {}).get("structuredContent", {})
    data = sc.get("data", {})
    if isinstance(data, dict):
        business = data
    else:
        business = {"data": data}
    out = dict(business) if isinstance(business, dict) else {"data": business}
    ui_code = render_ui_if_supported(tool_name, raw_data)
    attach_ui_output(
        out,
        tool_name,
        ui_code,
        genui_inline=genui_inline,
        dsl_file=dsl_file,
    )
    apply_flat_stdout(out, tool_name, business if isinstance(business, dict) else {})
    return out


def _print_extract_failure(raw_data: dict) -> None:
    for c in raw_data.get("result", {}).get("content", []):
        print(c.get("text", ""))


def main() -> int:
    argv = sys.argv[1:]
    extract = False
    genui_inline = False
    dsl_file: str | None = None
    if argv and argv[0] == "--extract":
        extract = True
        argv = argv[1:]

    filter_mode: str | None = None
    search: str | None = None
    max_cats: int | None = None
    max_items: int | None = None
    while argv and argv[0].startswith("--"):
        if argv[0] == "--genui-inline":
            genui_inline = True
            argv = argv[1:]
        elif argv[0] == "--dsl-file":
            if len(argv) < 2 or not argv[1]:
                print("错误: --dsl-file 需要一个路径参数", file=sys.stderr)
                return 2
            dsl_file = argv[1]
            argv = argv[2:]
        elif argv[0] == "--filter_mode":
            if len(argv) < 2 or not argv[1]:
                print("错误: --filter_mode 需要一个参数 (meals)", file=sys.stderr)
                return 2
            filter_mode = argv[1]
            if filter_mode not in ("meals",):
                print(f"错误: 不支持的 --filter_mode: {filter_mode}，仅支持 meals", file=sys.stderr)
                return 2
            argv = argv[2:]
        elif argv[0] == "--search":
            if len(argv) < 2 or not argv[1]:
                print("错误: --search 需要一个参数", file=sys.stderr)
                return 2
            search = argv[1]
            argv = argv[2:]
        elif argv[0] == "--max_categories":
            if len(argv) < 2 or not argv[1]:
                print("错误: --max_categories 需要一个整数参数", file=sys.stderr)
                return 2
            try:
                max_cats = int(argv[1])
            except ValueError:
                print(f"错误: --max_categories 需要整数，收到: {argv[1]}", file=sys.stderr)
                return 2
            argv = argv[2:]
        elif argv[0] == "--max_items_per_category":
            if len(argv) < 2 or not argv[1]:
                print("错误: --max_items_per_category 需要一个整数参数", file=sys.stderr)
                return 2
            try:
                max_items = int(argv[1])
            except ValueError:
                print(f"错误: --max_items_per_category 需要整数，收到: {argv[1]}", file=sys.stderr)
                return 2
            argv = argv[2:]
        else:
            break

    if not argv:
        print(__doc__)
        return 2

    tool_name = argv[0].strip()
    args_str = argv[1] if len(argv) > 1 else "{}"
    try:
        arguments = json.loads(args_str)
    except json.JSONDecodeError as e:
        print(f"错误: 参数不是有效的 JSON 格式: {e}", file=sys.stderr)
        return 1

    try:
        # ---- filter_mode path: read from stdin, filter, render genui ----
        if filter_mode:
            raw_stdin = sys.stdin.read()
            if not raw_stdin.strip():
                print(
                    "错误: --filter_mode 需要从 stdin 输入 JSON 数据", file=sys.stderr
                )
                return 1
            try:
                stdin_data = json.loads(raw_stdin)
            except json.JSONDecodeError as e:
                print(f"错误: stdin 不是有效的 JSON 格式: {e}", file=sys.stderr)
                return 1

            # Unwrap MCP envelope if present (supports both raw & extracted input)
            business_data = unwrap_mcp_data(stdin_data)
            if not isinstance(business_data, dict):
                print(json.dumps({"isShowCard": False, "data": business_data}, ensure_ascii=False))
                return 0

            filtered = apply_filter(
                business_data, filter_mode, search,
                max_cats=max_cats, max_items=max_items,
            )
            payload = {"result": {"structuredContent": {"data": filtered}}}
            ui_code = render_ui_if_supported(tool_name, payload)

            out = dict(filtered) if isinstance(filtered, dict) else {"data": filtered}
            attach_ui_output(
                out,
                tool_name,
                ui_code or "",
                genui_inline=genui_inline,
                dsl_file=dsl_file,
            )
            if isinstance(filtered, dict):
                apply_flat_stdout(out, tool_name, filtered)
            print(json.dumps(out, ensure_ascii=False))
            return 0

        # ---- normal MCP call path ----
        raw_data = call_mcp_tool(tool_name, arguments)
        if not isinstance(raw_data, dict):
            print(json.dumps(raw_data, ensure_ascii=False))
            return 0

        if raw_data.get("error"):
            print(json.dumps(raw_data, ensure_ascii=False))
            return 1

        # Apply meals truncation in all modes (not just --filter_mode)
        business_data = unwrap_mcp_data(raw_data)
        if _is_query_meals(tool_name) and isinstance(business_data, dict):
            truncated = _filter_meals_data(
                business_data, max_cats=max_cats, max_items=max_items,
            )
            raw_data["result"]["structuredContent"]["data"] = truncated

        sc = raw_data.get("result", {}).get("structuredContent", {})
        if extract and sc.get("success") is False:
            _print_extract_failure(raw_data)
            return 1

        ui_opts = {"genui_inline": genui_inline, "dsl_file": dsl_file}
        if extract:
            out = build_extract_output(raw_data, tool_name, **ui_opts)
        else:
            out = build_output(raw_data, tool_name, **ui_opts)

        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
