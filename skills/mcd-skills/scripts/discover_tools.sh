#!/usr/bin/env bash
# Discover available MCP tools from the live tools/list endpoint.
#
# Usage:
#   bash discover_tools.sh            # concise live tool list
#   bash discover_tools.sh --json     # full live tools JSON, including inputSchema
#   bash discover_tools.sh --refresh  # accepted for compatibility; no cache exists

set -euo pipefail

TOKEN_FILE="/home/sandbox/.openclaw/.xiaoyienv"
MCD_MCP_TOKEN=""
if [ -f "${TOKEN_FILE}" ]; then
    MCD_MCP_TOKEN=$(grep '^117797261_login_token=' "${TOKEN_FILE}" | cut -d'=' -f2- | tr -d '\n' || true)
fi
if [ -z "${MCD_MCP_TOKEN}" ] && [ -f "${HOME}/.openclaw/.xiaoyienv" ]; then
    MCD_MCP_TOKEN=$(grep '^117797261_login_token=' "${HOME}/.openclaw/.xiaoyienv" | cut -d'=' -f2- | tr -d '\n' || true)
fi

MCD_MCP_URL="${MCD_MCP_URL:-https://mcp.mcd.cn}"

HAS_JQ=false
if command -v jq >/dev/null 2>&1; then
    HAS_JQ=true
fi

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

JSON_MODE=false
for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=true ;;
        --refresh) ;; # Compatibility only: tools/list is always fetched live.
    esac
done

if [ -z "${MCD_MCP_TOKEN}" ]; then
    echo "错误: 117797261_login_token 为空或未设置，请刷新 Token" >&2
    echo '调用 HuaweiIDTool("mcd-skills", "117797261") 刷新' >&2
    exit 1
fi

PAYLOAD='{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${MCD_MCP_URL}" \
    -H "Authorization: Bearer ${MCD_MCP_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    --max-time 10 \
    2>/dev/null)

HTTP_CODE=$(echo "${RESPONSE}" | tail -1)
BODY=$(echo "${RESPONSE}" | sed '$d')

if [ "${HTTP_CODE}" = "401" ]; then
    echo "Token 无效或已过期，请刷新 Token" >&2
    echo '调用 HuaweiIDTool("mcd-skills", "117797261") 刷新' >&2
    exit 1
elif [ "${HTTP_CODE}" = "429" ]; then
    echo "请求过于频繁（限 600 次/分钟），请稍后重试" >&2
    exit 1
elif [ "${HTTP_CODE}" -ge 400 ] 2>/dev/null; then
    echo "错误: HTTP ${HTTP_CODE}" >&2
    echo "${BODY}" >&2
    exit 1
fi

if ! $HAS_JQ; then
    if $JSON_MODE; then
        echo "${BODY}"
    elif [ -n "${PYTHON_BIN}" ]; then
        printf '%s' "${BODY}" | "${PYTHON_BIN}" -c 'import json, sys
data = json.load(sys.stdin)
tools = data.get("result", {}).get("tools", [])
print("=" * 40)
print("麦当劳 MCP 可用工具（实时 tools/list）")
print("=" * 40)
print()
for tool in tools:
    desc = str(tool.get("description") or "").split("\n")[0][:80]
    print("  • {}".format(tool.get("name", "unknown")))
    if desc:
        print(f"      {desc}")
print()
print(f"总计: {len(tools)} 个工具")
print()
print("需要完整 inputSchema 时，运行: bash scripts/discover_tools.sh --json")'
    else
        echo "错误: 默认摘要输出需要 jq 或 python；完整实时 schema 可使用 --json。" >&2
        exit 1
    fi
    exit 0
fi

TOOLS_JSON=$(echo "${BODY}" | jq '.result.tools // empty' 2>/dev/null)
if [ -z "${TOOLS_JSON}" ] || [ "${TOOLS_JSON}" = "null" ]; then
    echo "错误: 无法获取工具列表，请检查网络和 Token" >&2
    exit 1
fi

if $JSON_MODE; then
    echo "${TOOLS_JSON}"
    exit 0
fi

TODAY=$(date +%Y-%m-%d)
echo "========================================"
echo "麦当劳 MCP 可用工具（实时 tools/list，${TODAY}）"
echo "========================================"
echo ""
echo "${TOOLS_JSON}" | jq -r '.[]? | "  • \(.name)\n      \((.description // "") | split("\n")[0][0:80])"'
echo ""
TOTAL=$(echo "${TOOLS_JSON}" | jq '. | length')
echo "总计: ${TOTAL} 个工具"
echo ""
echo "需要完整 inputSchema 时，运行: bash scripts/discover_tools.sh --json"
