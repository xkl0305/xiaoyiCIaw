"""
GenUI DSL 落盘 + 向 Agent stdout 输出轻量 a2uiCard 指针。

DSL 正文写入本地文件（默认 /tmp/a2uidsl.txt），不进模型上下文；
端侧通过 displayA2UICardByPath({ cardDSLPath }) 读取并渲染。

落盘格式（固定）::

    \\n```genui\\n
    ["root",...]
    ...
    \\n```\\n
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from genui import ensure_genui_fence  # noqa: E402

DEFAULT_DSL_PATH = os.environ.get("MCD_A2UI_DSL_PATH", "/tmp/a2uidsl.txt")
DISPLAY_TOOL = "displayA2UICardByPath"


def format_dsl_for_disk(ui_code: str) -> str:
    """Normalize fence for on-disk delivery: leading \\n + ```genui\\n ... \\n```\\n."""
    if not ui_code or not ui_code.strip():
        return ui_code
    text = ensure_genui_fence(ui_code.replace("\r\n", "\n").replace("\r", "\n"))
    body = text.lstrip("\n")
    out = "\n" + body
    if not out.endswith("\n"):
        out += "\n"
    return out


def resolve_dsl_path(tool_name: str, override: str | None = None) -> str:
    if override:
        return override
    if os.environ.get("MCD_A2UI_UNIQUE", "").strip().lower() in ("1", "true", "yes"):
        safe = (tool_name or "card").strip().lower().replace("/", "_")
        return f"/tmp/a2uidsl-{safe}-{uuid.uuid4().hex[:8]}.txt"
    return DEFAULT_DSL_PATH


def write_dsl_file(ui_code: str, path: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(format_dsl_for_disk(ui_code), encoding="utf-8", newline="\n")
    return str(p)


def build_a2ui_card_meta(tool_name: str, card_path: str) -> dict[str, str]:
    return {
        "cardDSLPath": card_path,
        "displayTool": DISPLAY_TOOL,
        "toolName": tool_name,
        "displayRequirement": (
            f"toolCall {DISPLAY_TOOL}({{\"cardDSLPath\":\"{card_path}\"}}) "
            "会直接向用户展示卡片；该卡片已包含全部 GenUI 与业务信息，用户可见。"
            "禁止再用 Markdown 表格/列表/图片/裸字段输出同批业务数据。"
            "回复格式：1 句导语 + 上述 toolCall + 1 句总结（≤20 字）；"
            f"禁止读取 {card_path} 的文件内容、禁止显示和读取 ```genui``` 块。"
            f"再次强调，调用工具displayA2UICardByPath({{\"cardDSLPath\":\"/tmp/a2uidsl.txt\"}})"
            "再次强调：卡片已完整展示业务内容，禁止任何形式的重复输出。"
            "必须使用OpenAI API Function Calling格式来调用displayA2UICardByPath"
        ),
    }


def attach_ui_output(
    out: dict,
    tool_name: str,
    ui_code: str,
    *,
    genui_inline: bool = False,
    dsl_file: str | None = None,
) -> dict:
    """Attach UI to agent-visible output; always sets isShowCard (bool)."""
    if not ui_code:
        out["isShowCard"] = False
        return out
    if genui_inline:
        out["genui"] = ui_code
        out["isShowCard"] = True
        return out
    card_path = write_dsl_file(ui_code, resolve_dsl_path(tool_name, dsl_file))
    out["a2uiCard"] = build_a2ui_card_meta(tool_name, card_path)
    out["isShowCard"] = True
    return out
