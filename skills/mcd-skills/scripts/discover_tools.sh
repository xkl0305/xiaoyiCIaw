#!/usr/bin/env bash
# MCP 工具发现 (curl 版)
#
# 通过 tools/list 接口动态发现可用工具，按天缓存到本地文件。
#
# 缓存策略：
#   - 缓存路径：scripts/cache/tools_YYYY-MM-DD.json
#   - 运行时自动检查当天缓存是否存在，不存在则拉取并写入
#   - 写入新缓存时自动删除前一天及更早的缓存文件
#
# 使用方式:
#   bash discover_tools.sh              # 显示工具列表（优先读当天缓存）
#   bash discover_tools.sh --refresh    # 强制刷新当天缓存
#   bash discover_tools.sh --json       # JSON 格式输出
#
# Token 来源: 环境变量 117797261_login_token (华为小艺)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="${SCRIPT_DIR}/cache"

# 读取华为小艺 Token
MCD_MCP_TOKEN=$(printenv '117797261_login_token' 2>/dev/null || true)
MCD_MCP_URL="${MCD_MCP_URL:-https://mcp.mcd.cn}"
TODAY=$(date +%Y-%m-%d)
CACHE_FILE="${CACHE_DIR}/tools_${TODAY}.json"

# 检查是否有 jq
HAS_JQ=false
if command -v jq &>/dev/null; then
    HAS_JQ=true
fi

cleanup_old_caches() {
    for f in "${CACHE_DIR}"/tools_*.json; do
        [ -f "$f" ] || continue
        if [ "$f" != "${CACHE_FILE}" ]; then
            rm -f "$f"
            echo "已清理旧缓存: $(basename "$f")" >&2
        fi
    done
}

fetch_and_cache() {
    if [ -z "${MCD_MCP_TOKEN}" ]; then
        echo "错误: 117797261_login_token 为空或未设置，请刷新 Token" >&2
        echo '调用 huawei_id_tool("117797261","mcd-skills") 刷新' >&2
        exit 1
    fi

    echo "正在从 MCP 服务器获取工具列表..." >&2

    PAYLOAD='{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
    RESPONSE=$(curl -s \
        -X POST "${MCD_MCP_URL}" \
        -H "Authorization: Bearer ${MCD_MCP_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "${PAYLOAD}" \
        --max-time 10 \
        2>/dev/null)

    if $HAS_JQ; then
        TOOLS_JSON=$(echo "${RESPONSE}" | jq '.result.tools // empty' 2>/dev/null)
        if [ -n "${TOOLS_JSON}" ] && [ "${TOOLS_JSON}" != "null" ]; then
            mkdir -p "${CACHE_DIR}"
            echo "${TOOLS_JSON}" > "${CACHE_FILE}"
            echo "工具列表已缓存到: ${CACHE_FILE}" >&2
            cleanup_old_caches
            return 0
        fi
    else
        if [ -n "${RESPONSE}" ]; then
            mkdir -p "${CACHE_DIR}"
            echo "${RESPONSE}" > "${CACHE_FILE}"
            echo "工具列表已缓存到: ${CACHE_FILE}（原始响应，建议安装 jq）" >&2
            cleanup_old_caches
            return 0
        fi
    fi

    echo "错误: 无法获取工具列表，请检查网络和 Token" >&2
    return 1
}

print_tools() {
    local file="$1"
    if $HAS_JQ; then
        echo "========================================"
        echo "麦当劳 MCP 可用工具 (${TODAY})"
        echo "========================================"
        echo ""
        jq -r '.[]? | "  • \(.name)"' "$file" 2>/dev/null
        TOTAL=$(jq '. | length' "$file" 2>/dev/null)
        echo ""
        echo "总计: ${TOTAL} 个工具"
        echo "缓存文件: ${file}"
        echo ""
        echo "Agent 可直接读取缓存文件查看完整参数定义（inputSchema）"
    else
        cat "$file"
    fi
}

# 主逻辑
FORCE_REFRESH=false
JSON_MODE=false

for arg in "$@"; do
    case "$arg" in
        --refresh) FORCE_REFRESH=true ;;
        --json) JSON_MODE=true ;;
    esac
done

# 非强制刷新时，优先读当天缓存
if ! $FORCE_REFRESH && [ -f "${CACHE_FILE}" ]; then
    if $JSON_MODE; then
        cat "${CACHE_FILE}"
    else
        print_tools "${CACHE_FILE}"
    fi
    exit 0
fi

# 拉取并缓存
fetch_and_cache || exit 1

if $JSON_MODE; then
    cat "${CACHE_FILE}"
else
    print_tools "${CACHE_FILE}"
fi
