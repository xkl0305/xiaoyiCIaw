#!/usr/bin/env bash
# MCP 工具通用调用器 (curl 版)
#
# 零依赖，仅需 curl。jq 可选（用于美化输出）。
#
# 使用方式:
#   bash call_tool.sh <tool-name> '<json-args>'
#
# 示例:
#   bash call_tool.sh campaign-calendar '{}'
#   bash call_tool.sh query-meals '{"storeCode": "1950963", "beCode": "195096302"}'
#
# Token 来源: 文件 /home/sandbox/.openclaw/.xiaoyienv，格式为 117797261_login_token=xxx
# Token 过期时调用 huawei_id_tool("117797261","mcd-skills") 刷新

set -euo pipefail

# 读取华为小艺 Token
TOKEN_FILE="/home/sandbox/.openclaw/.xiaoyienv"
MCD_MCP_TOKEN=""
if [ -f "${TOKEN_FILE}" ]; then
    MCD_MCP_TOKEN=$(grep '^117797261_login_token=' "${TOKEN_FILE}" | cut -d'=' -f2- | tr -d '\n' || true)
fi
MCD_MCP_URL="${MCD_MCP_URL:-https://mcp.mcd.cn}"

# 检查参数
EXTRACT=false
if [ "${1:-}" = "--extract" ]; then
    EXTRACT=true
    shift
fi

if [ $# -lt 1 ]; then
    echo "使用方式: bash call_tool.sh <tool-name> [json-args]"
    echo ""
    echo "示例:"
    echo "  bash call_tool.sh campaign-calendar '{}'"
    echo "  bash call_tool.sh query-meals '{\"storeCode\": \"1950963\", \"beCode\": \"195096302\"}'"
    exit 1
fi

# 检查 Token
if [ -z "${MCD_MCP_TOKEN}" ]; then
    echo "错误: 117797261_login_token 为空或未设置，请刷新 Token" >&2
    echo '调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用' >&2
    exit 1
fi

TOOL_NAME="$1"
ARGUMENTS="${2:-\{\}}"

# 构造 JSON-RPC 请求体
PAYLOAD=$(cat <<EOF
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "${TOOL_NAME}",
    "arguments": ${ARGUMENTS}
  }
}
EOF
)

# 发送请求
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${MCD_MCP_URL}" \
    -H "Authorization: Bearer ${MCD_MCP_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" \
    --max-time 30 2>/dev/null)

# 分离响应体和状态码
HTTP_CODE=$(echo "${RESPONSE}" | tail -1)
BODY=$(echo "${RESPONSE}" | sed '$d')

# 检查 HTTP 状态
if [ "${HTTP_CODE}" = "401" ]; then
    echo "错误: Token 无效或已过期，请刷新 Token" >&2
    echo '调用 huawei_id_tool("117797261","mcd-skills") 刷新凭证, 仅可调用一次，不能重复调用' >&2
    exit 1
elif [ "${HTTP_CODE}" = "429" ]; then
    echo "错误: 请求过于频繁（限 600 次/分钟），请稍后重试" >&2
    exit 1
elif [ "${HTTP_CODE}" -ge 400 ] 2>/dev/null; then
    echo "错误: HTTP ${HTTP_CODE}" >&2
    echo "${BODY}" >&2
    exit 1
fi

# 输出结果
if [ "${EXTRACT}" = "true" ] && command -v jq &>/dev/null; then
    # --extract 模式：提取业务数据
    SUCCESS=$(echo "${BODY}" | jq -r '.result.structuredContent.success')
    if [ "${SUCCESS}" = "false" ]; then
        echo "${BODY}" | jq -r '.result.content[]?.text // empty'
        exit 1
    else
        echo "${BODY}" | jq '.result.structuredContent.data'
        exit 0
    fi
elif [ "${EXTRACT}" = "true" ]; then
    # --extract 但无 jq，用 python 提取
    echo "${BODY}" | python3 -c "
import json,sys
data=json.load(sys.stdin)
sc=data.get('result',{}).get('structuredContent',{})
if sc.get('success') is False:
    for c in data.get('result',{}).get('content',[]):
        print(c.get('text',''))
    sys.exit(1)
else:
    print(json.dumps(sc.get('data',{}),ensure_ascii=False,indent=2))
"
    exit $?
else
    # 默认模式：完整输出
    if command -v jq &>/dev/null; then
        echo "${BODY}" | jq .
    else
        echo "${BODY}"
    fi
fi

# 检查 JSON-RPC 错误
if command -v jq &>/dev/null; then
    if echo "${BODY}" | jq -e '.error' &>/dev/null; then
        exit 1
    fi
fi
