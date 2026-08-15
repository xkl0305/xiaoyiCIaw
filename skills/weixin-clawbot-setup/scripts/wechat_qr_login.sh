#!/bin/bash
# WeChat QR Login - one-shot wrapper
# Usage: bash wechat_qr_login.sh
# Generates QR, sends to user, waits for scan, saves account, restarts gateway
# Outputs: last line is DONE:<accountId> on success

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
QR_IMAGE="/tmp/wechat_qr_login.png"

# Step 1: Generate QR code and wait for scan (Node API, 最长 5 分钟)
echo "[微信登录] 正在获取二维码..."
node "$SKILL_DIR/scripts/wechat_login_full.js" 2>/tmp/wx_stderr.txt | tee /tmp/wx_stdout.txt

# Check result
RESULT_LINE=$(grep -E "^(DONE:|DUP:|FAIL:)" /tmp/wx_stdout.txt | tail -1)
echo "RESULT:$RESULT_LINE"

case "$RESULT_LINE" in
  DONE:*)
    ACCOUNT_ID="${RESULT_LINE#DONE:}"
    echo "[微信登录] ✅ 登录成功，账号: $ACCOUNT_ID"
    ;;
  DUP:*)
    echo "[微信登录] ⚠️ 该微信已绑定: ${RESULT_LINE#DUP:}"
    ;;
  FAIL:*)
    echo "[微信登录] ❌ 登录失败: ${RESULT_LINE#FAIL:}"
    exit 1
    ;;
  *)
    echo "[微信登录] ❌ 未知结果"
    exit 1
    ;;
esac
