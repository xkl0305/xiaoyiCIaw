#!/usr/bin/env bash
# ACP 环境检查脚本 — 验证 opencode ACP 接入 openclaw 的各项配置是否就绪
# 返回码: 0=全部就绪, 1=存在缺失项

ENV_FILE="$HOME/.openclaw/.xiaoyienv"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.jsonc"
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [[ "$result" == "ok" ]]; then
        echo "[PASS] $desc"
        PASS=$((PASS+1))
    else
        echo "[FAIL] $desc"
        FAIL=$((FAIL+1))
    fi
}

# 1. 命令可用性
check "openclaw 命令" "$(command -v openclaw &>/dev/null && echo ok || echo fail)"
check "npm 命令"     "$(command -v npm &>/dev/null && echo ok || echo fail)"
check "python3 命令" "$(command -v python3 &>/dev/null && echo ok || echo fail)"

# 2. 环境变量文件
check ".xiaoyienv 文件存在" "$([[ -f "$ENV_FILE" ]] && echo ok || echo fail)"

if [[ -f "$ENV_FILE" ]]; then
    SERVICE_URL=""
    PERSONAL_UID=""
    PERSONAL_API_KEY=""

    while IFS='=' read -r key value; do
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        case "$key" in
            SERVICE_URL)      SERVICE_URL="$value" ;;
            PERSONAL-UID)     PERSONAL_UID="$value" ;;
            PERSONAL-API-KEY) PERSONAL_API_KEY="$value" ;;
        esac
    done < "$ENV_FILE"

    check "SERVICE_URL 已配置" "$([[ -n "$SERVICE_URL" ]] && echo ok || echo fail)"
    check "PERSONAL-UID 已配置" "$([[ -n "$PERSONAL_UID" ]] && echo ok || echo fail)"
    check "PERSONAL-API-KEY 已配置" "$([[ -n "$PERSONAL_API_KEY" ]] && echo ok || echo fail)"
else
    check "SERVICE_URL 已配置" "fail"
    check "PERSONAL-UID 已配置" "fail"
    check "PERSONAL-API-KEY 已配置" "fail"
fi

# 3. ACPX 插件
check "ACPX 插件已安装" "$(openclaw plugins list 2>/dev/null | grep -q "@openclaw/acpx" && echo ok || echo fail)"

# 4. opencode-ai
check "opencode-ai 已安装" "$([[ -d "$HOME/node_modules/opencode-ai" ]] && echo ok || echo fail)"

# 5. opencode provider 配置
PROVIDER_CHECK="fail"
if [[ -f "$OPENCODE_CONFIG" ]]; then
    PROVIDER_CHECK=$(python3 -c "
import json, re, sys

with open('$OPENCODE_CONFIG', 'r', encoding='utf-8') as f:
    content = f.read()

clean = re.sub(r',\s*([}\]])', r'\1', content)
try:
    config = json.loads(clean)
except json.JSONDecodeError:
    print('fail')
    sys.exit(0)

existing = config.get('provider', {}).get('xiaoyiprovider')
if existing is not None:
    print('ok')
else:
    print('fail')
" 2>/dev/null)
fi
check "opencode xiaoyiprovider 已配置" "$PROVIDER_CHECK"

# 5.1 opencode model 字段
MODEL_CHECK="fail"
MODEL_HINT=""
if [[ -f "$OPENCODE_CONFIG" ]]; then
    MODEL_RESULT=$(python3 -c "
import json, re, sys

with open('$OPENCODE_CONFIG', 'r', encoding='utf-8') as f:
    content = f.read()

clean = re.sub(r',\s*([}\]])', r'\1', content)
try:
    config = json.loads(clean)
except json.JSONDecodeError:
    print('fail|配置文件解析失败')
    sys.exit(0)

model = config.get('model', '')
if not model:
    print('fail|model 字段未配置，建议设置为 xiaoyiprovider/Auto-Model')
elif not model.startswith('xiaoyiprovider/'):
    print('fail|当前 model 为 \"' + model + '\"，未使用 xiaoyiprovider，xiaoyiprovider 配置将不会生效')
else:
    print('ok|')
" 2>/dev/null)
    MODEL_CHECK="${MODEL_RESULT%%|*}"
    MODEL_HINT="${MODEL_RESULT#*|}"
fi
check "opencode model 字段" "$MODEL_CHECK"
if [[ "$MODEL_CHECK" != "ok" && -n "$MODEL_HINT" ]]; then
    echo "       → $MODEL_HINT"
fi

# 5.2 xiaoyiprovider api-key 一致性检查（自动修复）
APIKEY_CHECK="skip"
APIKEY_HINT=""
if [[ -f "$OPENCODE_CONFIG" && -n "$PERSONAL_API_KEY" ]]; then
    APIKEY_RESULT=$(python3 -c "
import json, re, sys

config_path = '$OPENCODE_CONFIG'
env_api_key = '$PERSONAL_API_KEY'

with open(config_path, 'r', encoding='utf-8') as f:
    content = f.read()

clean = re.sub(r',\s*([}\]])', r'\1', content)
try:
    config = json.loads(clean)
except json.JSONDecodeError:
    print('skip|配置文件解析失败，无法检查 api-key')
    sys.exit(0)

existing = config.get('provider', {}).get('xiaoyiprovider')
if existing is None:
    print('skip|xiaoyiprovider 未配置，跳过 api-key 检查')
    sys.exit(0)

current_key = existing.get('options', {}).get('headers', {}).get('x-api-key', '')
if current_key == env_api_key:
    print('ok|')
else:
    # 自动修复
    if 'options' not in existing:
        existing['options'] = {}
    if 'headers' not in existing['options']:
        existing['options']['headers'] = {}
    existing['options']['headers']['x-api-key'] = env_api_key
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print('fixed|x-api-key 与 .xiaoyienv 不一致，已自动同步为当前 .xiaoyienv 中的值')
" 2>/dev/null)
    APIKEY_CHECK="${APIKEY_RESULT%%|*}"
    APIKEY_HINT="${APIKEY_RESULT#*|}"
fi
if [[ "$APIKEY_CHECK" == "ok" ]]; then
    check "xiaoyiprovider x-api-key 一致性" "ok"
elif [[ "$APIKEY_CHECK" == "fixed" ]]; then
    check "xiaoyiprovider x-api-key 一致性" "ok"
    echo "       → $APIKEY_HINT"
elif [[ "$APIKEY_CHECK" == "skip" ]]; then
    : # 跳过，不纳入统计
else
    check "xiaoyiprovider x-api-key 一致性" "fail"
fi

# 6. ACP 配置
ACP_CHECK="fail"
if [[ -f "$OPENCLAW_CONFIG" ]]; then
    ACP_CHECK=$(python3 -c "
import json, sys

with open('$OPENCLAW_CONFIG', 'r') as f:
    config = json.load(f)

acp = config.get('acp', {})
if (acp.get('enabled') == True and
    acp.get('backend') == 'acpx' and
    acp.get('defaultAgent') == 'opencode' and
    acp.get('allowedAgents') == ['opencode']):
    print('ok')
else:
    print('fail')
" 2>/dev/null)
fi
check "ACP 配置已启用" "$ACP_CHECK"

# 7. ACPX 插件参数
ACPX_CONFIG_CHECK="fail"
if [[ -f "$OPENCLAW_CONFIG" ]]; then
    ACPX_CONFIG_CHECK=$(python3 -c "
import json, sys

with open('$OPENCLAW_CONFIG', 'r') as f:
    config = json.load(f)

acpx = config.get('plugins', {}).get('entries', {}).get('acpx', {})
if (acpx.get('enabled') == True and
    acpx.get('config', {}).get('permissionMode') == 'approve-all' and
    acpx.get('config', {}).get('nonInteractivePermissions') == 'fail'):
    print('ok')
else:
    print('fail')
" 2>/dev/null)
fi
check "ACPX 插件参数已配置" "$ACPX_CONFIG_CHECK"

# 8. openclaw-gateway 运行状态
GATEWAY_CHECK="fail"
if command -v python3 &>/dev/null; then
    GATEWAY_CHECK=$(python3 -m supervisor.supervisorctl status openclaw-gateway 2>/dev/null | grep -q "RUNNING" && echo ok || echo fail)
fi
check "openclaw-gateway 运行中" "$GATEWAY_CHECK"

# 汇总
echo ""
echo "结果: ${PASS} 项通过, ${FAIL} 项缺失"

if [[ "$FAIL" -eq 0 ]]; then
    echo "状态: ALL READY"
    exit 0
else
    echo "状态: NOT READY — 请执行 bash scripts/setup_acp.sh 完成配置"
    exit 1
fi
