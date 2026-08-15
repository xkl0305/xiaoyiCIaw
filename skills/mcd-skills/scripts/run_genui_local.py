#!/usr/bin/env python3
"""
本地 GenUI 调试：tool_name + MCP 数据 → genui 围栏（assets 模板，无后端）。

用法:
    python run_genui_local.py calculate-price
    python run_genui_local.py calculate-price scripts/mock/calculate-price.json
    python run_genui_local.py query-meals scripts/mock/query-meals.json

scripts/mock/*.json 为 unwrap 后的 data 业务体，字段须与实时 discover_tools --json
里对应工具的 outputSchema.properties.data 一致，勿编造 schema 外字段，勿包 MCP 信封。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from call_tool import call_mcp_tool  # noqa: E402
from genui import render_local  # noqa: E402


def configure_stdio_utf8() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except (AttributeError, OSError, ValueError):
                pass


def read_stdin_text() -> str:
    configure_stdio_utf8()
    if hasattr(sys.stdin, "buffer"):
        data = sys.stdin.buffer.read()
        if data:
            return data.decode("utf-8-sig", errors="replace")
    return sys.stdin.read().lstrip("\ufeff")


def write_stdout_text(text: str) -> None:
    configure_stdio_utf8()
    sys.stdout.write(text)
    sys.stdout.flush()


def _load_mcp_json(arg: str) -> object:
    if arg == "-":
        raw = read_stdin_text().strip()
        if not raw:
            raise ValueError("stdin is empty")
        return json.loads(raw)
    if arg.startswith("@"):
        path = Path(arg[1:])
    else:
        path = Path(arg)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(arg)


def _is_mcp_response(obj: object) -> bool:
    if isinstance(obj, list):
        return True
    if not isinstance(obj, dict):
        return False
    if "result" in obj or obj.get("error"):
        return True
    if "data" in obj and ("code" in obj or "message" in obj or "success" in obj):
        return True
    return False


def main() -> int:
    configure_stdio_utf8()

    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    tool = sys.argv[1].strip()

    if len(sys.argv) > 2:
        arg = sys.argv[2]
        try:
            if arg in ("-",) or arg.startswith("@") or Path(arg).is_file():
                raw = _load_mcp_json(arg)
            else:
                parsed = json.loads(arg)
                raw = parsed if _is_mcp_response(parsed) else None
                if raw is None:
                    raw = call_mcp_tool(tool, parsed)
        except json.JSONDecodeError as e:
            print(f"invalid JSON: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"load/call failed: {e}", file=sys.stderr)
            return 1
    else:
        try:
            raw = call_mcp_tool(tool, {})
        except Exception as e:
            print(f"call_tool failed: {e}", file=sys.stderr)
            return 1

    print(json.dumps(raw, ensure_ascii=False, indent=2), file=sys.stderr)

    out = render_local(tool, raw)
    if not out:
        print(
            "genui: empty output (no template in assets/genui/ or assemble failed)",
            file=sys.stderr,
        )
        return 1

    write_stdout_text(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
