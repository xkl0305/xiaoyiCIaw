#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HOME/.openclaw/.xiaoyienv"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.jsonc"
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CHANGED=0

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
changed() { CHANGED=1; }

check_prerequisites() {
    info "========== 前置条件检查 =========="

    if ! command -v openclaw &>/dev/null; then
        error "openclaw 命令未找到，请先安装 openclaw"
        exit 1
    fi
    info "openclaw 命令: $(command -v openclaw)"

    if ! command -v npm &>/dev/null; then
        error "npm 命令未找到，请先安装 npm"
        exit 1
    fi
    info "npm 命令: $(command -v npm)"

    if ! command -v python3 &>/dev/null; then
        error "python3 命令未找到，请先安装 python3"
        exit 1
    fi
    info "python3 命令: $(command -v python3)"

    if [[ ! -f "$ENV_FILE" ]]; then
        error "环境变量文件不存在: $ENV_FILE"
        exit 1
    fi
    info "环境变量文件: $ENV_FILE"

    info "前置条件检查通过"
}

load_env() {
    info "========== 读取环境变量 =========="

    SERVICE_URL=""
    PERSONAL_UID=""
    PERSONAL_API_KEY=""

    while IFS='=' read -r key value; do
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        case "$key" in
            SERVICE_URL)       SERVICE_URL="$value" ;;
            PERSONAL-UID)      PERSONAL_UID="$value" ;;
            PERSONAL-API-KEY)  PERSONAL_API_KEY="$value" ;;
        esac
    done < "$ENV_FILE"

    if [[ -z "$SERVICE_URL" ]]; then
        error "SERVICE_URL 未在 $ENV_FILE 中配置"
        exit 1
    fi
    info "SERVICE_URL=$SERVICE_URL"

    if [[ -z "$PERSONAL_UID" ]]; then
        error "PERSONAL-UID 未在 $ENV_FILE 中配置"
        exit 1
    fi
    info "PERSONAL-UID=$PERSONAL_UID"

    if [[ -z "$PERSONAL_API_KEY" ]]; then
        error "PERSONAL-API-KEY 未在 $ENV_FILE 中配置"
        exit 1
    fi
    info "PERSONAL-API-KEY=****(已隐藏)"

    SERVICE_URL="${SERVICE_URL%/}"

    info "环境变量读取完成"
}

configure_acpx_config() {
    info "========== 配置 ACPX 插件参数 =========="

    # 检查现有配置是否已匹配，匹配则跳过
    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        local need_update
        need_update=$(python3 -c "
import json, sys

with open('$OPENCLAW_CONFIG', 'r') as f:
    config = json.load(f)

existing = config.get('plugins', {}).get('entries', {}).get('acpx', {})
if (existing.get('enabled') == True and
    existing.get('config', {}).get('permissionMode') == 'approve-all' and
    existing.get('config', {}).get('nonInteractivePermissions') == 'fail'):
    print('no')
else:
    print('yes')
")
        if [[ "$need_update" == "no" ]]; then
            info "ACPX 插件配置已就绪，跳过配置步骤"
            return 0
        fi
    fi

    changed

    info "通过 batch-json 写入 ACPX 插件配置..."
    if ! TERM=dumb openclaw config set --batch-json "$(cat <<EOF
[
  {"path": "plugins.entries.acpx.enabled", "value": true},
  {"path": "plugins.entries.acpx.config.permissionMode", "value": "approve-all"},
  {"path": "plugins.entries.acpx.config.nonInteractivePermissions", "value": "fail"}
]
EOF
)" >/dev/null 2>&1; then
        error "ACPX 插件配置写入失败"
        exit 1
    fi
    info "ACPX 插件配置完成"
}

install_acpx() {
    info "========== 检查 ACPX 插件 =========="

    if openclaw plugins list 2>/dev/null | grep -q "@openclaw/acpx"; then
        info "ACPX 插件已安装，跳过安装步骤"
    else
        changed
        warn "ACPX 插件未安装，开始安装..."

        local npm_dir="$HOME/.openclaw/npm"
        if [[ ! -d "$npm_dir" ]]; then
            info "npm 目录不存在，创建: $npm_dir"
            mkdir -p "$npm_dir"
        fi

        info "执行: chmod -R 755 $npm_dir"
        chmod -R 755 "$npm_dir"
        info "npm 目录权限设置完成"

        info "执行: openclaw plugins install @openclaw/acpx"
        TERM=dumb openclaw plugins install @openclaw/acpx@2026.6.6 >/dev/null 2>&1
        info "ACPX 插件安装完成"

        info "执行: find 递归修复 npm 项目目录权限 (dir=755, file=644)"
        find "$npm_dir" -type d -exec chmod 755 {} \;
        find "$npm_dir" -type f -exec chmod 644 {} \;
        info "npm 目录权限重新设置完成"
    fi

    info "配置 ACPX 插件参数..."
    configure_acpx_config

    info "ACPX 插件安装并启用完成"
}

install_opencode_ai() {
    info "========== 安装 opencode-ai =========="

    if [[ -d "$HOME/node_modules/opencode-ai" ]]; then
        info "opencode-ai 已安装，跳过安装步骤"
        return 0
    fi

    changed
    local max_retries=3
    local retry=0

    while (( retry < max_retries )); do
        info "执行: cd ~/ && npm i opencode-ai (第$((retry+1))次)"
        if cd "$HOME" && npm i opencode-ai; then
            info "opencode-ai 安装完成"
            return 0
        fi
        retry=$((retry+1))
        if (( retry < max_retries )); then
            warn "安装失败，${retry}/${max_retries}，3秒后重试..."
            sleep 3
        fi
    done

    error "opencode-ai 安装失败，已重试 ${max_retries} 次"
    exit 1
}

configure_provider() {
    info "========== 配置 opencode provider =========="

    local base_url="${SERVICE_URL}/celia-claw/v1/sse-api"
    info "baseURL: $base_url"
    info "x-uid: $PERSONAL_UID"
    info "x-api-key: ****(已隐藏)"

    mkdir -p "$(dirname "$OPENCODE_CONFIG")"

    local result
    result=$(python3 -c "
import json, re, os, sys

config_path = '$OPENCODE_CONFIG'
base_url = '$base_url'
uid = '$PERSONAL_UID'
api_key = '$PERSONAL_API_KEY'

default_provider = {
    'npm': '@ai-sdk/openai-compatible',
    'name': 'XiaoYi AI Provider',
    'options': {
        'baseURL': base_url,
        'headers': {
            'Accept': 'text/event-stream',
            'x-request-from': 'openclaw',
            'x-uid': uid,
            'x-api-key': api_key
        }
    },
    'models': {
        'Auto-Model': {
            'name': 'Auto-Model'
        }
    }
}

changed = False

if os.path.isfile(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    clean = re.sub(r',\s*([}\]])', r'\1', content)
    try:
        config = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f'ERROR: 无法解析配置文件: {e}', file=sys.stderr)
        sys.exit(1)

    if 'model' not in config:
        config['model'] = 'xiaoyiprovider/Auto-Model'
        changed = True

    if 'provider' not in config:
        config['provider'] = {}

    if 'xiaoyiprovider' not in config['provider']:
        config['provider']['xiaoyiprovider'] = default_provider
        changed = True
else:
    config = {
        '\$schema': 'https://opencode.ai/config.json',
        'model': 'xiaoyiprovider/Auto-Model',
        'provider': {
            'xiaoyiprovider': default_provider
        }
    }
    changed = True

if changed:
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print('changed')
else:
    print('unchanged')
")

    if [[ "$result" == "changed" ]]; then
        changed
        info "opencode provider 配置已写入"
    else
        info "xiaoyiprovider 配置已就绪，跳过配置步骤"
    fi

    info "opencode provider 配置完成"
}

enable_acp() {
    info "========== 启用 ACP 配置 =========="

    # 检查现有配置是否已匹配，匹配则跳过
    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        local need_update
        need_update=$(python3 -c "
import json, sys

with open('$OPENCLAW_CONFIG', 'r') as f:
    config = json.load(f)

existing = config.get('acp', {})
if (existing.get('enabled') == True and
    existing.get('backend') == 'acpx' and
    existing.get('defaultAgent') == 'opencode' and
    existing.get('allowedAgents') == ['opencode'] and
    existing.get('runtime', {}).get('ttlMinutes') == 120):
    print('no')
else:
    print('yes')
")
        if [[ "$need_update" == "no" ]]; then
            info "ACP 配置已就绪，跳过配置步骤"
            return 0
        fi
    fi

    changed

    info "通过 batch-json 写入 ACP 配置..."
    if ! TERM=dumb openclaw config set --batch-json "$(cat <<EOF
[
  {"path": "acp.enabled", "value": true},
  {"path": "acp.backend", "value": "acpx"},
  {"path": "acp.defaultAgent", "value": "opencode"},
  {"path": "acp.allowedAgents", "value": ["opencode"]},
  {"path": "acp.runtime.ttlMinutes", "value": 120}
]
EOF
)" >/dev/null 2>&1; then
        error "ACP 配置写入失败"
        exit 1
    fi
    info "ACP 配置启用完成"
}

restart_gateway() {
    info "========== 重启 openclaw-gateway =========="

    if [[ "$CHANGED" -eq 0 ]]; then
        info "无配置变更，跳过重启"
        return 0
    fi

    info "检测到配置变更，执行重启"
    info "执行: python3 -m supervisor.supervisorctl restart openclaw-gateway"
    python3 -m supervisor.supervisorctl restart openclaw-gateway
    info "openclaw-gateway 重启完成"
}

verify() {
    info "========== 配置验证 =========="

    info "检查 ACPX 插件状态..."
    if openclaw plugins list 2>/dev/null | grep -q "@openclaw/acpx"; then
        info "ACPX 插件: 已安装且启用"
    else
        warn "ACPX 插件: 未检测到，请手动检查"
    fi

    if [[ -f "$OPENCODE_CONFIG" ]]; then
        info "opencode 配置文件: $OPENCODE_CONFIG 已存在"
    else
        warn "opencode 配置文件: $OPENCODE_CONFIG 不存在"
    fi

    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        info "openclaw 配置文件: $OPENCLAW_CONFIG 已存在"
    else
        warn "openclaw 配置文件: $OPENCLAW_CONFIG 不存在"
    fi

    info "========== 配置全部完成 =========="
}

main() {
    echo "============================================"
    echo "  OpenCode ACP 接入 OpenClaw 一键配置脚本"
    echo "============================================"
    echo ""

    check_prerequisites
    load_env
    install_acpx
    install_opencode_ai
    configure_provider
    enable_acp
    restart_gateway
    verify

    echo ""
    info "所有步骤执行完毕！"
}

main "$@"
