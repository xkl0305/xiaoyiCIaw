#!/usr/bin/env bash
# MCP 工具调用 + 可选 GenUI 装填（Agent 唯一脚本入口）
#
# 用法:
#   bash call_tool_for_genui.sh [--extract] [--max_categories <N>] [--max_items_per_category <N>] <tool-name> '<json-args>'
#   bash call_tool_for_genui.sh --filter_mode meals [--search <term>] [--max_categories <N>] [--max_items_per_category <N>] <tool-name> '<json-args>' < data.json
#
# 选项:
#   --extract                     提取 structuredContent.data 业务字段
#   --filter_mode <mode>          过滤模式（目前仅支持 meals），从 stdin 读取 JSON 数据
#   --search <term>               搜索关键词（配合 --filter_mode meals，按餐品名过滤）
#   --max_categories <N>          截断分类数量上限（默认 10）
#   --max_items_per_category <N>  每分类餐品数量上限（默认 20）
#   --dsl-file <path>             GenUI DSL 落盘路径（默认 /tmp/a2uidsl.txt）
#   --genui-inline                调试：genui inline 进 stdout，不写文件

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    echo "用法: bash call_tool_for_genui.sh [--extract] [--filter_mode meals] [--max_categories N] [--max_items_per_category N] <tool-name> ['<json-args>']" >&2
    exit 2
fi

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "[call_tool_for_genui] python3/python not found" >&2
    exit 1
fi

exec "${PYTHON}" "${SCRIPT_DIR}/call_tool_for_genui.py" "$@"
