#!/usr/bin/env python3
"""
GenUI 渲染（skill 内，路径不变）。

流水线:
  1. unwrap_mcp_data   — 通用：MCP 信封 → 业务 data
  2. adapter.adapt     — 可选、按 tool：结构映射 + 展示用字符串格式化
  3. fill              — 通用：ndjson 模板 + view model → 展开 list slot → materialize
  4. wrap_genui        — 通用：tuple 行 → ```genui``` 围栏（由 call_tool_for_genui 调用；Agent 勿直连）

模板仅允许 genui 协议的 {"path":"/..."} 绑定；展示用字符串由 adapters 格式化，fill 阶段 materialize_paths 解析为字面值。

用法:
    python scripts/genui.py <tool-name> '<mcp-json>' | - | @file.json
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Set

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from sanitize import sanitize_text  # noqa: E402


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------

def _skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _assets_dir() -> Path:
    return _skill_root() / "assets" / "genui"


def _find_template(tool_name: str) -> Optional[Path]:
    """在 assets/genui/ 里找 <tool_name>.ndjson（不区分大小写）。"""
    d = _assets_dir()
    if not d.is_dir():
        return None
    target = tool_name.strip().lower()
    for f in d.iterdir():
        if f.is_file() and f.stem.lower() == target and f.suffix.lower() in (".ndjson", ".txt"):
            return f
    return None


def has_genui_template(tool_name: str) -> bool:
    """是否配置了本地 GenUI 模板（有则展示路径应优先 ```genui``` 围栏）。"""
    return _find_template(tool_name) is not None


def _adapters_dir() -> Path:
    return Path(__file__).resolve().parent / "adapters"


_ADAPTER_CACHE: Dict[str, Optional[ModuleType]] = {}


def _load_adapter_module(tool_name: str) -> Optional[ModuleType]:
    """Load scripts/adapters/<tool_name>.py if present."""
    key = tool_name.strip().lower()
    if key in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[key]

    d = _adapters_dir()
    mod: Optional[ModuleType] = None
    if d.is_dir():
        adapters_path = str(d)
        if adapters_path not in sys.path:
            sys.path.insert(0, adapters_path)
        for f in d.iterdir():
            if f.is_file() and f.stem.lower() == key and f.suffix.lower() == ".py":
                spec = importlib.util.spec_from_file_location(f"genui_adapter_{key}", f)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

    _ADAPTER_CACHE[key] = mod
    return mod


def apply_adapter(tool_name: str, data: Any) -> Any:
    """
    Optional per-tool adapter: MCP data → view model (structural mapping only).
    See scripts/adapters/<tool>.py. No adapter → data passed through.
    """
    mod = _load_adapter_module(tool_name)
    if mod is None:
        return data
    adapt_fn = getattr(mod, "adapt", None)
    if not callable(adapt_fn):
        print(f"[genui] adapter for '{tool_name}' missing adapt()", file=sys.stderr)
        return data
    try:
        return adapt_fn(data)
    except Exception as e:
        print(f"[genui] adapter error for '{tool_name}': {e}", file=sys.stderr)
        return data


def validate_adapted(tool_name: str, data: Any) -> bool:
    """Optional adapter validate(data) → False aborts render."""
    mod = _load_adapter_module(tool_name)
    if mod is None:
        return True
    validate_fn = getattr(mod, "validate", None)
    if not callable(validate_fn):
        return True
    try:
        return bool(validate_fn(data))
    except Exception as e:
        print(f"[genui] adapter validate error for '{tool_name}': {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# MCP 响应解包  (与 payload.py unwrap_mcp_data 一致)
# ---------------------------------------------------------------------------

def unwrap_mcp_data(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get("error"):
        return payload

    if isinstance(payload, dict) and "result" in payload:
        result = payload.get("result")
        if isinstance(result, dict):
            sc = result.get("structuredContent")
            if isinstance(sc, dict):
                if "data" in sc:
                    return sc["data"]
                return sc

    if isinstance(payload, dict) and "data" in payload and (
        "code" in payload or "message" in payload or "success" in payload
    ):
        return payload["data"]

    return payload


# ---------------------------------------------------------------------------
# 通用装填：模板 + view model → tuple 行（与业务无关）
# ---------------------------------------------------------------------------

LAYOUT_TYPES = frozenset({"Row", "Column", "List", "Stack", "Grid"})


def _is_list_array_children(children: Any) -> bool:
    return (
        isinstance(children, dict)
        and isinstance(children.get("componentId"), str)
        and isinstance(children.get("path"), str)
    )


def _child_id_refs(children: Any) -> List[str]:
    if isinstance(children, list):
        return [c for c in children if isinstance(c, str)]
    if _is_list_array_children(children):
        return [children["componentId"]]
    return []


def _list_template_ids(tuples: List[List[Any]]) -> Set[str]:
    """List 数组绑定模板的根及其子树（保留相对 path，不参与 materialize）。"""
    by_id = _rows_by_id(tuples)
    roots: List[str] = []
    for t in tuples:
        if len(t) >= 4 and t[1] == "List" and _is_list_array_children(t[3]):
            roots.append(t[3]["componentId"])
    out: Set[str] = set()

    def walk(cid: str) -> None:
        if cid in out or cid not in by_id:
            return
        out.add(cid)
        row = by_id[cid]
        if len(row) >= 4:
            for ch in _child_id_refs(row[3]):
                walk(ch)

    for root in roots:
        walk(root)
    return out


def _split_template_rows(
    tuples: List[List[Any]],
) -> tuple[List[List[Any]], List[List[Any]]]:
    """组件行 [id,type,props(,children)] 与数据 schema 行 [\"/\", {...}] 分离。"""
    components: List[List[Any]] = []
    schema_rows: List[List[Any]] = []
    for t in tuples:
        if len(t) == 2 and t[0] == "/":
            schema_rows.append(t)
        elif len(t) >= 3:
            components.append(t)
    return components, schema_rows


def _is_query_meals_nested_schema(schema: dict[str, Any]) -> bool:
    """query-meals 模板 schema：categories[].items[] 嵌套结构。"""
    categories = schema.get("categories")
    if not isinstance(categories, list):
        return False
    if not categories:
        return True
    first = categories[0]
    return isinstance(first, dict) and "items" in first


def _query_meals_data_row(data: Any) -> dict[str, Any]:
    """从 adapter view model 提取 query-meals List 模板绑定的字段。"""
    if not isinstance(data, dict):
        return {"categories": []}
    categories = data.get("categories")
    if not isinstance(categories, list):
        return {"categories": []}

    out_categories: List[dict[str, Any]] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        raw_items = cat.get("items")
        if not isinstance(raw_items, list):
            continue
        items: List[dict[str, Any]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            raw_tags = raw_item.get("tags")
            tags: List[str] = []
            if isinstance(raw_tags, list):
                tags = [
                    sanitize_text(t)
                    for t in raw_tags
                    if sanitize_text(t)
                ]
            items.append(
                {
                    "name": sanitize_text(raw_item.get("name", "")),
                    "image": raw_item.get("image", ""),
                    "tags": tags,
                    "currentPriceSymbol": raw_item.get("currentPriceSymbol", ""),
                    "currentPriceValue": raw_item.get("currentPriceValue", ""),
                    "showTags": raw_item.get("showTags", "none"),
                    "showDivider": raw_item.get("showDivider", "none"),
                }
            )
        cat_name = sanitize_text(cat.get("name", ""))
        if items or cat_name:
            out_categories.append({"name": cat_name, "items": items})
    return {"categories": out_categories}


def _is_calculate_price_schema(schema: dict[str, Any]) -> bool:
    product_list = schema.get("productList")
    return isinstance(product_list, list)


def _calculate_price_data_row(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"productList": []}
    product_list = data.get("productList")
    if not isinstance(product_list, list):
        return {"productList": []}
    return {"productList": product_list}


def _is_create_order_schema(schema: dict[str, Any]) -> bool:
    product_items = schema.get("productItems")
    return isinstance(product_items, list)


def _create_order_data_row(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"productItems": []}
    product_items = data.get("productItems")
    if not isinstance(product_items, list):
        return {"productItems": []}
    return {"productItems": product_items}


def _is_delivery_query_addresses_schema(schema: dict[str, Any]) -> bool:
    return isinstance(schema.get("addresses"), list)


def _delivery_query_addresses_data_row(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"addresses": []}
    addresses = data.get("addresses")
    if not isinstance(addresses, list):
        return {"addresses": []}
    out_addresses: List[dict[str, Any]] = []
    for raw in addresses:
        if not isinstance(raw, dict):
            continue
        out_addresses.append(
            {
                "addressId": sanitize_text(raw.get("addressId", "")),
                "fullAddress": sanitize_text(raw.get("fullAddress", "")),
                "contactDisplay": sanitize_text(
                    raw.get("contactDisplay") or raw.get("contactLine", "")
                ),
                "showContact": raw.get("showContact", "none"),
                "showDivider": raw.get("showDivider", "none"),
            }
        )
    return {"addresses": out_addresses}


def _is_query_order_schema(schema: dict[str, Any]) -> bool:
    products = schema.get("products")
    if not isinstance(products, list):
        return False
    if not products:
        return True
    first = products[0]
    return isinstance(first, dict) and "productName" in first and "productImage" in first


def _query_order_data_row(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"products": []}
    products = data.get("products")
    if not isinstance(products, list):
        return {"products": []}
    out_products: List[dict[str, Any]] = []
    for raw in products:
        if not isinstance(raw, dict):
            continue
        out_products.append(
            {
                "productName": sanitize_text(raw.get("productName", "")),
                "productImage": raw.get("productImage", ""),
            }
        )
    return {"products": out_products}


def _schema_anchor_component_ids(
    tuples: List[List[Any]],
) -> List[tuple[List[Any], Optional[str]]]:
    """schema 行与其在模板中紧随其后的首个组件 id（插入锚点）。"""
    pairs: List[tuple[List[Any], Optional[str]]] = []
    pending: List[List[Any]] = []
    for t in tuples:
        if len(t) == 2 and t[0] == "/":
            pending.append(t)
        elif len(t) >= 3 and isinstance(t[0], str):
            if pending:
                anchor = t[0]
                for schema in pending:
                    pairs.append((schema, anchor))
                pending = []
    for schema in pending:
        pairs.append((schema, None))
    return pairs


def _insert_schema_rows(
    filled: List[List[Any]],
    schema_anchors: List[tuple[List[Any], Optional[str]]],
    mcp_data: Any,
) -> List[List[Any]]:
    """按模板锚点将 data 行插入已排序的组件行（默认插在锚点组件之前）。

    When the anchor component was pruned (visibility none), skip that schema row
    instead of appending it to the end — the removed subtree no longer needs data.
    """
    if not schema_anchors:
        return filled

    id_to_index: dict[str, int] = {}
    for i, row in enumerate(filled):
        if len(row) >= 1 and isinstance(row[0], str):
            id_to_index[row[0]] = i

    result = list(filled)
    append_rows: List[List[Any]] = []
    for schema, anchor_id in reversed(schema_anchors):
        filled_row = _fill_schema_row(schema, mcp_data)
        if anchor_id is not None and anchor_id in id_to_index:
            result.insert(id_to_index[anchor_id], filled_row)
        elif anchor_id is None:
            append_rows.insert(0, filled_row)
        # else: anchor was pruned; omit orphaned schema row
    result.extend(append_rows)
    return result


def _fill_schema_row(row: List[Any], data: Any) -> List[Any]:
    """将模板 schema 行装填为运行时 data 行（query-meals 嵌套 categories/items）。"""
    if len(row) != 2 or row[0] != "/":
        return row
    schema = row[1]
    if not isinstance(schema, dict):
        return row
    if _is_query_meals_nested_schema(schema):
        return ["/", _query_meals_data_row(data)]
    if _is_calculate_price_schema(schema):
        return ["/", _calculate_price_data_row(data)]
    if _is_create_order_schema(schema):
        return ["/", _create_order_data_row(data)]
    if _is_delivery_query_addresses_schema(schema):
        return ["/", _delivery_query_addresses_data_row(data)]
    if _is_query_order_schema(schema):
        return ["/", _query_order_data_row(data)]
    return row


def _normalize_component_row(t: List[Any]) -> List[Any]:
    """[id, type, [child, ...]] 省略空 props 时规范为 [id, type, {}, children]。"""
    if (
        len(t) == 3
        and isinstance(t[0], str)
        and isinstance(t[1], str)
        and isinstance(t[2], list)
        and all(isinstance(c, str) for c in t[2])
    ):
        return [t[0], t[1], {}, t[2]]
    return t


def parse_template_ndjson(text: str) -> List[List[Any]]:
    lines: List[List[Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"\bxxx\b", line):
            line = re.sub(r"\bxxx\b", "null", line)
        row = json.loads(line)
        if not isinstance(row, list):
            raise ValueError(f"template line must be a JSON array, got: {line!r}")
        if len(row) == 2 and row[0] == "/":
            lines.append(row)
        else:
            lines.append(_normalize_component_row(row))
    return lines


def resolve_pointer(data: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return data
    cur = data
    for part in pointer.strip("/").split("/"):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(pointer)
    return cur


def _is_path_binding(obj: Any) -> bool:
    if not isinstance(obj, dict) or not isinstance(obj.get("path"), str):
        return False
    return set(obj.keys()) == {"path"}


def materialize_paths(obj: Any, data: Any) -> Any:
    if _is_path_binding(obj):
        return resolve_pointer(data, obj["path"])
    if isinstance(obj, dict):
        return {k: materialize_paths(v, data) for k, v in obj.items()}
    if isinstance(obj, list):
        return [materialize_paths(v, data) for v in obj]
    return obj


def _tuple_paths(t: List[Any]) -> List[str]:
    if len(t) < 3:
        return []
    found: List[str] = []

    def walk(o: Any) -> None:
        if _is_path_binding(o):
            found.append(o["path"])
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(t[2])
    return found


_ARRAY_INDEX0 = re.compile(r"^/([^/]+)/0(/|$)")


def _detect_array_keys(tuples: List[List[Any]]) -> List[str]:
    keys: List[str] = []
    seen: set[str] = set()
    for t in tuples:
        for p in _tuple_paths(t):
            m = _ARRAY_INDEX0.match(p)
            if not m:
                continue
            k = m.group(1)
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def _renumber_paths(node: Any, array_key: str, i: int) -> Any:
    if _is_path_binding(node):
        p = re.sub(
            rf"/{re.escape(array_key)}/0(/|$)",
            rf"/{array_key}/{i}\1",
            node["path"],
        )
        return {"path": p}
    if isinstance(node, dict):
        return {k: _renumber_paths(v, array_key, i) for k, v in node.items()}
    if isinstance(node, list):
        return [_renumber_paths(v, array_key, i) for v in node]
    return node


def _rows_by_id(tuples: List[List[Any]]) -> dict[str, List[Any]]:
    out: dict[str, List[Any]] = {}
    for t in tuples:
        if len(t) >= 1 and isinstance(t[0], str):
            out[t[0]] = t
    return out


def _has_path_in_subtree(by_id: dict[str, List[Any]], cid: str) -> bool:
    """子树内是否存在 data path 绑定（Divider 等静态装饰节点返回 False）。"""
    t = by_id.get(cid)
    if not t:
        return False
    if _tuple_paths(t):
        return True
    if len(t) >= 4 and isinstance(t[3], list):
        return any(
            _has_path_in_subtree(by_id, c) for c in t[3] if isinstance(c, str)
        )
    return False


def _collect_slot_ids(by_id: dict[str, List[Any]], array_key: str) -> Set[str]:
    seed: Set[str] = set()
    for cid, t in by_id.items():
        if len(t) < 3:
            continue
        if any(p.startswith(f"/{array_key}/0") for p in _tuple_paths(t)):
            seed.add(cid)
    if not seed:
        return set()

    slot_ids = set(seed)
    changed = True
    while changed:
        changed = False
        for cid in list(slot_ids):
            t = by_id.get(cid)
            if not t or len(t) < 4 or not isinstance(t[3], list):
                continue
            for child in t[3]:
                if isinstance(child, str) and child not in slot_ids:
                    slot_ids.add(child)
                    changed = True
        for pid, t in by_id.items():
            if pid in slot_ids or len(t) < 4 or not isinstance(t[3], list):
                continue
            kids = [c for c in t[3] if isinstance(c, str)]
            slot_kids = [c for c in kids if _has_path_in_subtree(by_id, c)]
            if slot_kids and all(c in slot_ids for c in slot_kids):
                slot_ids.add(pid)
                changed = True
    return slot_ids


def _child_ids(by_id: dict[str, List[Any]], cid: str) -> Set[str]:
    t = by_id.get(cid)
    if not t or len(t) < 4 or not isinstance(t[3], list):
        return set()
    return {c for c in t[3] if isinstance(c, str)}


def _descendants(by_id: dict[str, List[Any]], root: str) -> Set[str]:
    out: Set[str] = {root}
    queue = [root]
    while queue:
        cid = queue.pop()
        for ch in _child_ids(by_id, cid):
            if ch not in out:
                out.add(ch)
                queue.append(ch)
    return out


def _slot_root(ids: Set[str], by_id: dict[str, List[Any]], array_key: str) -> str:
    """取绑定 `/{array_key}/0` 子树的最外层 slot 容器（如 cat0，而非 pl0 / list_col）。"""
    candidates: List[str] = []
    slot_id_rx = re.compile(r"^[a-z]+0$")
    for cid in ids:
        if cid not in by_id or not slot_id_rx.match(cid):
            continue
        paths: List[str] = []
        for d in _descendants(by_id, cid):
            if d in by_id:
                paths.extend(_tuple_paths(by_id[d]))
        if any(p.startswith(f"/{array_key}/0") for p in paths):
            candidates.append(cid)
    if not candidates:
        return ""
    outer = [
        c
        for c in candidates
        if not any(c != o and c in _descendants(by_id, o) for o in candidates)
    ]
    return min(outer, key=len) if outer else min(candidates, key=len)


def _slot_id_at_index(root: str, i: int) -> str:
    if root.endswith("0"):
        return f"{root[:-1]}{i}"
    return root if i == 0 else f"{root}_{i}"


def _renumber_component_id(cid: str, root: str, i: int) -> str:
    if not root:
        return cid
    root_i = _slot_id_at_index(root, i)
    if cid == root:
        return root_i
    if cid.startswith(root) and len(cid) > len(root):
        return root_i + cid[len(root) :]
    return cid


def _expand_one_array(tuples: List[List[Any]], data: Any, array_key: str) -> List[List[Any]]:
    arr = data.get(array_key) if isinstance(data, dict) else None
    if not isinstance(arr, list) or len(arr) == 0:
        return tuples

    by_id = _rows_by_id(tuples)
    slot_ids = _collect_slot_ids(by_id, array_key)
    if not slot_ids:
        return tuples

    root = _slot_root(slot_ids, by_id, array_key)
    if not root:
        return tuples

    dup_ids = _descendants(by_id, root)

    slot_rows = [by_id[cid] for cid in slot_ids if cid in by_id and cid in dup_ids]
    static_rows = [t for t in tuples if len(t) < 3 or str(t[0]) not in dup_ids]
    child_roots = [_slot_id_at_index(root, i) for i in range(len(arr))]

    patched_static: List[List[Any]] = []
    for t in static_rows:
        t = deepcopy(t)
        if len(t) >= 4 and isinstance(t[3], list) and root in t[3]:
            t[3] = [c for c in t[3] if c != root] + child_roots
        patched_static.append(t)

    expanded: List[List[Any]] = []
    for i in range(len(arr)):
        for t in slot_rows:
            row = deepcopy(t)
            if isinstance(row[0], str):
                row[0] = _renumber_component_id(row[0], root, i)
            row[2] = _renumber_paths(row[2], array_key, i)
            if len(row) >= 4 and isinstance(row[3], list):
                row[3] = [
                    _renumber_component_id(c, root, i) if isinstance(c, str) else c
                    for c in row[3]
                ]
            expanded.append(row)

    # 静态行（含总计/按钮等）与 slot 子树分离拼接会打乱 NDJSON 行序；渲染器按流式行序布局。
    return sort_tuples_depth_first(patched_static + expanded)


def expand_arrays(tuples: List[List[Any]], data: Any) -> List[List[Any]]:
    for key in _detect_array_keys(tuples):
        tuples = _expand_one_array(tuples, data, key)
    return tuples


def _detect_nested_array_slots(tuples: List[List[Any]]) -> List[tuple[str, str]]:
    """Find (parent_pointer, array_key) for nested lists, e.g. (/items/0, comboItems) or (/productLines)."""
    top_level_keys = set(_detect_array_keys(tuples))
    slots: set[tuple[str, str]] = set()
    for t in tuples:
        for p in _tuple_paths(t):
            parts = [x for x in p.strip("/").split("/") if x]
            for i in range(len(parts) - 1):
                if parts[i + 1] != "0" or parts[i].isdigit():
                    continue
                parent = "/" + "/".join(parts[:i]) if i > 0 else ""
                key = parts[i]
                # 顶层 `/categories/0/...` 已由 expand_arrays 处理，勿再当嵌套 slot
                if not parent and key in top_level_keys:
                    continue
                slots.add((parent, key))
    return sorted(slots)


def _nested_path_prefix(parent_prefix: str, array_key: str, index: int) -> str:
    base = parent_prefix.rstrip("/")
    if base:
        return f"{base}/{array_key}/{index}"
    return f"/{array_key}/{index}"


def _renumber_nested_cid(
    cid: str, from_i: int, to_i: int, *, array_key: str = ""
) -> str:
    if from_i == to_i:
        return cid
    cid = re.sub(rf"_c{from_i}$", f"_c{to_i}", cid)
    cid = re.sub(rf"_c{from_i}_", f"_c{to_i}_", cid)
    if array_key == "tags":
        return re.sub(rf"_tg{from_i}$", f"_tg{to_i}", cid)
    # cat{N}_pl{M}：只改餐品下标，不改分类前缀（cat0→cat1 由 expand_arrays 负责）
    if re.match(rf"^cat\d+_pl{from_i}($|_)", cid):
        return re.sub(rf"_pl{from_i}($|_)", rf"_pl{to_i}\1", cid, count=1)
    for prefix in ("pl", "item", "row", "pg", "fl", "cat"):
        slot = f"{prefix}{from_i}"
        slot_to = f"{prefix}{to_i}"
        if cid == slot:
            return slot_to
        if cid.startswith(slot + "_") or (cid.startswith(slot) and len(cid) > len(slot)):
            return slot_to + cid[len(slot) :]
    return cid


def _meal_cid_prefix(parent_prefix: str, slot_index: int = 0) -> Optional[str]:
    """从 parent_prefix 解析餐品 slot 前缀，如 /categories/0/items/2 → cat0_pl2。"""
    parts = [x for x in parent_prefix.strip("/").split("/") if x]
    if (
        len(parts) >= 4
        and parts[0] == "categories"
        and parts[2] == "items"
        and parts[1].isdigit()
        and parts[3].isdigit()
    ):
        return f"cat{parts[1]}_pl{parts[3]}"
    if len(parts) >= 2 and parts[0] == "categories" and parts[1].isdigit():
        return f"cat{parts[1]}_pl{slot_index}"
    return None


def _tuple_belongs_to_nested_item(
    t: List[Any], parent_prefix: str, array_key: str, index: int = 0
) -> bool:
    prefix = _nested_path_prefix(parent_prefix, array_key, index)
    if any(p == prefix or p.startswith(prefix + "/") for p in _tuple_paths(t)):
        return True
    cid = t[0] if t else ""
    if not isinstance(cid, str):
        return False
    if array_key == "tags":
        meal_prefix = _meal_cid_prefix(parent_prefix)
        if meal_prefix and re.match(rf"^{re.escape(meal_prefix)}_tg\d+$", cid):
            return True
        return False
    if cid == f"pl{index}" or cid.startswith(f"pl{index}_"):
        return True
    meal_prefix = _meal_cid_prefix(parent_prefix, index)
    if meal_prefix and (cid == meal_prefix or cid.startswith(f"{meal_prefix}_")):
        return True
    parts = [x for x in parent_prefix.strip("/").split("/") if x]
    if parts and parts[-1].isdigit():
        row_slot = f"row{parts[-1]}_c{index}"
        if cid == row_slot or cid.startswith(f"{row_slot}_"):
            return True
    return False


def _replace_nested_index(
    t: List[Any], parent_prefix: str, array_key: str, from_i: int, to_i: int
) -> List[Any]:
    row = deepcopy(t)
    cid = row[0]
    path_from = _nested_path_prefix(parent_prefix, array_key, from_i)
    path_to = _nested_path_prefix(parent_prefix, array_key, to_i)
    if isinstance(cid, str):
        row[0] = _renumber_nested_cid(cid, from_i, to_i, array_key=array_key)

    def walk(o: Any) -> Any:
        if _is_path_binding(o):
            p = o["path"]
            if p == path_from or p.startswith(path_from + "/"):
                p = path_to + p[len(path_from) :]
            return {"path": p}
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o

    if len(row) >= 3:
        row[2] = walk(row[2])
    if len(row) >= 4 and isinstance(row[3], list):
        row[3] = [
            _renumber_nested_cid(c, from_i, to_i, array_key=array_key)
            if isinstance(c, str)
            else c
            for c in row[3]
        ]
    return row


def _patch_nested_children(
    static_tpl: List[List[Any]], slot0_id: str, combo_ids: List[str]
) -> List[List[Any]]:
    patched: List[List[Any]] = []
    for t in static_tpl:
        t = deepcopy(t)
        if len(t) >= 4 and isinstance(t[3], list) and slot0_id in t[3]:
            new_children: List[Any] = []
            for c in t[3]:
                if c == slot0_id:
                    new_children.extend(combo_ids)
                else:
                    new_children.append(c)
            t[3] = new_children
        patched.append(t)
    return patched


def _nested_item_slot0_id(
    item_tpl: List[List[Any]], parent_prefix: str, index: int, array_key: str = ""
) -> str:
    """Item 容器行 id（用于 patch 父 Column 的 children），勿用带 path 的子节点当 slot0。"""
    parts = [x for x in parent_prefix.strip("/").split("/") if x]
    if array_key == "tags":
        meal_prefix = _meal_cid_prefix(parent_prefix)
        if meal_prefix:
            want = f"{meal_prefix}_tg{index}"
            for t in item_tpl:
                if t and t[0] == want:
                    return want
        for t in item_tpl:
            if t and isinstance(t[0], str) and re.search(r"_tg\d+$", t[0]):
                return t[0]
        return ""
    if len(parts) >= 4 and parts[0] == "categories" and parts[2] == "items":
        want = f"cat{parts[1]}_pl{parts[3]}"
        for t in item_tpl:
            if t and t[0] == want:
                return want
    if len(parts) >= 2 and parts[0] == "categories" and parts[1].isdigit():
        want = f"cat{parts[1]}_pl{index}"
        for t in item_tpl:
            if t and t[0] == want:
                return want
    want_pl = f"pl{index}"
    for t in item_tpl:
        if t and t[0] == want_pl:
            return want_pl
    for t in item_tpl:
        if len(t) >= 2 and t[1] == "Row" and isinstance(t[0], str):
            return t[0]
    return item_tpl[0][0] if item_tpl and isinstance(item_tpl[0][0], str) else ""


def _expand_one_nested_list(
    tuples: List[List[Any]], data: Any, parent_prefix: str, array_key: str
) -> tuple[List[List[Any]], bool]:
    try:
        arr = resolve_pointer(data, f"{parent_prefix}/{array_key}")
    except (KeyError, TypeError, ValueError):
        return tuples, False
    if not isinstance(arr, list):
        return tuples, False

    item_tpl = [
        t for t in tuples if _tuple_belongs_to_nested_item(t, parent_prefix, array_key, 0)
    ]
    if not item_tpl:
        return tuples, False
    static_tpl = [t for t in tuples if t not in item_tpl]
    slot0_id = _nested_item_slot0_id(item_tpl, parent_prefix, 0, array_key)

    if not arr:
        return _patch_nested_children(static_tpl, slot0_id, []), True

    combo_ids: List[str] = []
    expanded: List[List[Any]] = []
    for i in range(len(arr)):
        combo_id = (
            _renumber_nested_cid(slot0_id, 0, i, array_key=array_key)
            if slot0_id
            else f"c{i}"
        )
        combo_ids.append(combo_id)
        for t in item_tpl:
            expanded.append(_replace_nested_index(t, parent_prefix, array_key, 0, i))

    merged = _patch_nested_children(static_tpl, slot0_id, combo_ids) + expanded
    return sort_tuples_depth_first(merged), True


def expand_nested_list_templates(tuples: List[List[Any]], data: Any) -> List[List[Any]]:
    """Expand nested array templates, e.g. /items/0/comboItems/0 → /items/0/comboItems/N."""
    if not isinstance(data, (dict, list)):
        return tuples
    result = list(tuples)
    expanded_slots: set[tuple[str, str]] = set()
    while True:
        changed = False
        for parent_prefix, array_key in _detect_nested_array_slots(result):
            if not parent_prefix:
                continue
            slot_key = (parent_prefix, array_key)
            if slot_key in expanded_slots:
                continue
            next_result, did_apply = _expand_one_nested_list(
                result, data, parent_prefix, array_key
            )
            if did_apply:
                expanded_slots.add(slot_key)
            if next_result != result:
                changed = True
                result = next_result
        if not changed:
            break
    return result


def fill(template_text: str, data: Any) -> List[List[Any]]:
    """Materialize 流水线：parse → expand_arrays → materialize_paths → prune。"""
    return assemble(template_text, data)


def _props_visibility(props: Any) -> Optional[str]:
    if isinstance(props, dict):
        vis = props.get("visibility")
        if isinstance(vis, str):
            return vis
    return None


def prune_hidden_components(tuples: List[List[Any]]) -> List[List[Any]]:
    """
    Remove components with visibility \"none\" and their descendants from the tree.

    Schema rows [\"/\", {...}] are preserved in place; they are independent of
    component visibility and are never removed when a List is pruned.
    """
    by_id: dict[str, List[Any]] = {}
    child_map: dict[str, List[str]] = {}
    hidden: set[str] = set()

    for t in tuples:
        if len(t) == 2 and t[0] == "/":
            continue
        if len(t) < 3 or not isinstance(t[0], str):
            continue
        cid = t[0]
        by_id[cid] = t
        if _props_visibility(t[2]) == "none":
            hidden.add(cid)
        if len(t) >= 4:
            child_map[cid] = _child_id_refs(t[3])

    queue = list(hidden)
    while queue:
        pid = queue.pop()
        for ch in child_map.get(pid, []):
            if ch not in hidden:
                hidden.add(ch)
                queue.append(ch)

    pruned: List[List[Any]] = []
    for t in tuples:
        if len(t) == 2 and t[0] == "/":
            pruned.append(deepcopy(t))
            continue
        if len(t) < 3 or not isinstance(t[0], str):
            continue
        if t[0] in hidden:
            continue
        row = deepcopy(t)
        if len(row) >= 4:
            ch = row[3]
            if isinstance(ch, list):
                row[3] = [c for c in ch if isinstance(c, str) and c not in hidden]
        pruned.append(row)
    return pruned


def sort_tuples_depth_first(tuples: List[List[Any]]) -> List[List[Any]]:
    """按组件树 children 深度优先重排 NDJSON 行（展开后静态行与 slot 行会错位）。"""
    by_id: dict[str, List[Any]] = {}
    for t in tuples:
        if len(t) >= 3 and isinstance(t[0], str):
            by_id[t[0]] = t
    if not by_id:
        return tuples

    root_id = "root" if "root" in by_id else tuples[0][0]
    if not isinstance(root_id, str) or root_id not in by_id:
        return tuples

    ordered: List[List[Any]] = []
    seen: set[str] = set()

    def walk(cid: str) -> None:
        if cid in seen or cid not in by_id:
            return
        seen.add(cid)
        ordered.append(by_id[cid])
        row = by_id[cid]
        if len(row) >= 4:
            for ch in _child_id_refs(row[3]):
                walk(ch)

    walk(root_id)
    for t in tuples:
        cid = t[0] if len(t) >= 1 and isinstance(t[0], str) else None
        if cid and cid not in seen:
            ordered.append(t)
    return ordered


def _fill_component_row(
    t: List[Any], list_tpl_ids: Set[str], mcp_data: Any
) -> List[Any] | None:
    if len(t) < 3:
        return None
    cid, ctype, props = t[0], t[1], t[2]
    if cid in list_tpl_ids:
        new_props = props
    else:
        new_props = materialize_paths(props, mcp_data)
    new_row: List[Any] = [cid, ctype, new_props]
    if len(t) >= 4:
        new_row.append(t[3])
    return new_row


def _assemble_list_template_sequential(
    tuples: List[List[Any]], mcp_data: Any
) -> List[List[Any]]:
    """Fill template line-by-line in file order; schema rows stay in place."""
    component_rows = [
        t for t in tuples if not (len(t) == 2 and t[0] == "/")
    ]
    list_tpl_ids = _list_template_ids(component_rows)
    filled: List[List[Any]] = []
    for t in tuples:
        if len(t) == 2 and t[0] == "/":
            filled.append(_fill_schema_row(t, mcp_data))
            continue
        if len(t) < 3:
            continue
        try:
            row = _fill_component_row(t, list_tpl_ids, mcp_data)
        except (KeyError, TypeError, ValueError) as e:
            print(f"[genui] path binding failed: {e}", file=sys.stderr)
            return []
        if row is not None:
            filled.append(row)
    return prune_hidden_components(filled)


def assemble(template_text: str, mcp_data: Any) -> List[List[Any]]:
    tuples = parse_template_ndjson(template_text)
    if not tuples:
        return []
    components, _schema_rows = _split_template_rows(tuples)
    list_tpl_ids = _list_template_ids(components)
    if list_tpl_ids:
        return _assemble_list_template_sequential(tuples, mcp_data)
    components = expand_arrays(components, mcp_data)
    components = expand_nested_list_templates(components, mcp_data)
    filled: List[List[Any]] = []
    for t in components:
        if len(t) < 3:
            continue
        cid, ctype, props = t[0], t[1], t[2]
        try:
            new_props = materialize_paths(props, mcp_data)
        except (KeyError, TypeError, ValueError) as e:
            print(f"[genui] path binding failed: {e}", file=sys.stderr)
            return []
        new_row: List[Any] = [cid, ctype, new_props]
        if len(t) >= 4:
            new_row.append(t[3])
        filled.append(new_row)
    filled = sort_tuples_depth_first(filled)
    filled = prune_hidden_components(filled)
    schema_anchors = _schema_anchor_component_ids(tuples)
    return _insert_schema_rows(filled, schema_anchors, mcp_data)


def _has_path_binding(obj: Any) -> bool:
    if isinstance(obj, dict) and "path" in obj and isinstance(obj.get("path"), str):
        return True
    if isinstance(obj, dict):
        return any(_has_path_binding(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_path_binding(v) for v in obj)
    return False


_INTERACTION_PROP_KEYS = frozenset({"onChange", "action", "onClick"})


def _has_ui_path_binding(obj: Any) -> bool:
    """UI 展示类 path 绑定；跳过 onChange/action/onClick 内的 setDataModel 等交互 path。"""
    if isinstance(obj, dict) and "path" in obj and isinstance(obj.get("path"), str):
        return True
    if isinstance(obj, dict):
        return any(
            _has_ui_path_binding(v)
            for k, v in obj.items()
            if k not in _INTERACTION_PROP_KEYS
        )
    if isinstance(obj, list):
        return any(_has_ui_path_binding(v) for v in obj)
    return False


def validate(tuples: List[List[Any]]) -> bool:
    if not tuples:
        return False
    component_rows = [t for t in tuples if not (len(t) == 2 and t[0] == "/")]
    if not component_rows:
        return False
    first = component_rows[0]
    if not isinstance(first, list) or len(first) < 3:
        return False
    if first[0] != "root" or first[1] not in ("Column", "Stack"):
        return False
    props = first[2]
    if not isinstance(props, dict):
        return False
    list_tpl_ids = _list_template_ids(component_rows)
    defined: set[str] = set()
    needed: set[str] = set()
    for row in component_rows:
        if len(row) < 3:
            return False
        cid, ctype = row[0], row[1]
        if not isinstance(cid, str) or not isinstance(ctype, str):
            return False
        defined.add(cid)
        if ctype in LAYOUT_TYPES:
            if len(row) < 4:
                return False
            ch = row[3]
            if ctype == "List" and _is_list_array_children(ch):
                needed.add(ch["componentId"])
            elif isinstance(ch, list):
                for child in ch:
                    if isinstance(child, str):
                        needed.add(child)
            else:
                return False
        elif len(row) > 3:
            return False
        if _has_ui_path_binding(row[2]) and cid not in list_tpl_ids:
            return False
    return needed.issubset(defined)


GENUI_FENCE_OPEN = "```genui"
GENUI_FENCE_CLOSE = "```"

GENUI_STDOUT_LEAD_BY_TOOL: dict[str, str] = {
    "query-meals": "菜单如下：",
    "calculate-price": "价格明细如下：",
    "create-order": "订单信息如下：",
    "query-order": "订单进度如下：",
    "delivery-query-addresses": "配送地址如下：",
}
GENUI_STDOUT_LEAD_DEFAULT = "如下："


def genui_stdout_lead_line(tool_name: str) -> str | None:
    override = os.environ.get("MCD_GENUI_STDOUT_LEAD")
    if override is not None:
        s = override.strip()
        if not s or s == "0":
            return None
        return s
    key = (tool_name or "").strip().lower()
    return GENUI_STDOUT_LEAD_BY_TOOL.get(key, GENUI_STDOUT_LEAD_DEFAULT)


def prepend_genui_stdout_lead(tool_name: str, ui_code: str) -> str:
    lead = genui_stdout_lead_line(tool_name)
    if not lead:
        return ui_code
    return f"{lead}\n{ui_code}"


def is_genui_fence_complete(ui_code: str) -> bool:
    """True if output has opening ```genui line and a final line that is only ```."""
    if not ui_code or GENUI_FENCE_OPEN not in ui_code:
        return False
    lines = ui_code.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return False
    if not lines[0].strip().startswith(GENUI_FENCE_OPEN):
        return False
    return lines[-1].strip() == GENUI_FENCE_CLOSE


def ensure_genui_fence(ui_code: str) -> str:
    """Append closing ``` line when missing (defensive; agents also truncate paste)."""
    if not ui_code or GENUI_FENCE_OPEN not in ui_code:
        return ui_code
    if is_genui_fence_complete(ui_code):
        return ui_code if ui_code.endswith("\n") else ui_code + "\n"
    return ui_code.rstrip("\n\r") + "\n```\n"


def wrap_genui(tuples: List[List[Any]]) -> str:
    """Wrap materialized tuples in a ```genui``` fence."""
    lines = [json.dumps(t, ensure_ascii=False, separators=(",", ":")) for t in tuples]
    return ensure_genui_fence("```genui\n" + "\n".join(lines) + "\n```")


# ---------------------------------------------------------------------------
# 入口：tool 名 → 模板 + adapter + fill
# ---------------------------------------------------------------------------

def render_local(tool_name: str, mcp_payload: Any) -> str:
    """
    本地渲染：查找 assets/genui/<tool_name>.ndjson → assemble → validate → 返回围栏。
    失败返回空字符串（调用方回退 Markdown）。
    """
    if mcp_payload is None:
        return ""
    if isinstance(mcp_payload, dict) and mcp_payload.get("error"):
        return ""

    tpl_path = _find_template(tool_name)
    if not tpl_path:
        return ""

    data = unwrap_mcp_data(mcp_payload)
    if data is None or (isinstance(data, dict) and data.get("error")):
        return ""

    data = apply_adapter(tool_name, data)
    if not validate_adapted(tool_name, data):
        print(f"[genui] adapter validation failed for '{tool_name}'", file=sys.stderr)
        return ""

    try:
        template_text = tpl_path.read_text(encoding="utf-8")
        tuples = fill(template_text, data)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[genui] assemble error: {e}", file=sys.stderr)
        return ""

    if not tuples or not validate(tuples):
        print(f"[genui] validation failed for '{tool_name}'", file=sys.stderr)
        return ""

    return wrap_genui(tuples)


def _load_payload(arg: str) -> Any:
    """读取 MCP JSON：stdin（-），@file，内联字符串，或路径。"""
    if arg == "-":
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace").strip()
        if not raw:
            raise ValueError("stdin is empty")
        return json.loads(raw)
    if arg.startswith("@"):
        p = Path(arg[1:])
        if not p.is_file():
            raise FileNotFoundError(f"file not found: {p}")
        return json.loads(p.read_text(encoding="utf-8"))
    p = Path(arg)
    if p.is_file() and p.suffix.lower() in (".json", ".ndjson"):
        return json.loads(p.read_text(encoding="utf-8"))
    # 兼容 PowerShell 传参里字面量 \"
    raw = arg.strip()
    if '\\"' in raw:
        try:
            return json.loads(raw.replace('\\"', '"'))
        except json.JSONDecodeError:
            pass
    return json.loads(raw)


def fence_fixup_stdin() -> int:
    """stdin → stdout：补全 ```genui 围栏闭合行；仍不完整则 exit 1。"""
    raw = sys.stdin.read()
    if not raw.strip():
        return 1
    fixed = ensure_genui_fence(raw)
    if not is_genui_fence_complete(fixed):
        return 1
    sys.stdout.write(fixed)
    return 0


def main() -> int:
    # 设置 stdout UTF-8（Windows）
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    if len(sys.argv) >= 2 and sys.argv[1].strip() in ("--fence-fixup", "fence-fixup"):
        return fence_fixup_stdin()

    if len(sys.argv) < 3:
        print(
            "Usage: python genui.py <tool-name> '<mcp-json>' | - | @file.json\n"
            "       python genui.py --fence-fixup   # stdin → stdout，补围栏闭合\n"
            "Example: python scripts/run_genui_local.py calculate-price scripts/mock/calculate-price.json",
            file=sys.stderr,
        )
        return 2

    tool_name = sys.argv[1].strip()
    try:
        payload = _load_payload(sys.argv[2])
    except (ValueError, FileNotFoundError) as e:
        print(f"[genui] input error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"[genui] invalid JSON: {e}", file=sys.stderr)
        return 1

    out = render_local(tool_name, payload)
    if out:
        sys.stdout.write(out)
        sys.stdout.flush()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
