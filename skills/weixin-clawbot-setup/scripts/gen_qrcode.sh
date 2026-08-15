#!/bin/bash
#
# gen_qrcode.sh - 重新生成微信授权二维码
#
# v2 优化：改用 Node API（wechat_login_full.js），告别 CLI 方式的二维码过期问题。
# 生成二维码后同步轮询等待用户扫码，最长 5 分钟。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================="
echo "  微信授权二维码生成（Node API）"
echo "========================================="

# 清理旧进程和临时文件
echo "[1/3] 清理旧登录进程..."
OLD_PIDS=$(ps aux | grep "wechat_login_full" | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PIDS" ]; then
  for PID in $OLD_PIDS; do
    kill -9 "$PID" 2>/dev/null && echo "  已杀掉旧进程 PID: $PID"
  done
  sleep 1
fi
rm -f /tmp/wx_stdout.txt /tmp/wx_stderr.txt

# 启动 Node 脚本后台运行
echo "[2/3] 启动微信扫码登录（Node API）..."
nohup timeout 310 node "$SKILL_DIR/scripts/wechat_login_full.js" \
  > /tmp/wx_stdout.txt 2>/tmp/wx_stderr.txt &
LOGIN_PID=$!
echo "  登录脚本 PID: $LOGIN_PID"

# 等待二维码生成（最多 10 秒）
echo "[3/3] 等待二维码生成..."
for i in $(seq 1 10); do
  if grep -q "^QR_URL:" /tmp/wx_stdout.txt 2>/dev/null; then
    break
  fi
  sleep 1
done

QRCODE_URL=$(grep "^QR_URL:" /tmp/wx_stdout.txt 2>/dev/null | head -1 | cut -d: -f2-)

if [ -n "$QRCODE_URL" ]; then
  echo ""
  echo "✅ 二维码已生成"
  echo ""
  echo "QRCODE_URL=$QRCODE_URL"
  echo ""
  echo "========================================="
  echo "  登录脚本在后台等待扫码(PID: $LOGIN_PID)"
  echo "  扫码完成后检查结果："
  echo "    cat /tmp/wx_stdout.txt"
  echo "========================================="
else
  echo "⚠️ 未检测到二维码链接，查看日志："
  echo "  cat /tmp/wx_stderr.txt"
  exit 1
fi
