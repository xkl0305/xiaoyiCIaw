#!/bin/bash

set -e

echo "========================================="
echo " OpenClaw Weixin 安装脚本"
echo "========================================="

# 步骤1：执行 npm pack 下载 tgz 包
echo ""
echo "[步骤 1/3] 正在下载 @tencent-weixin/openclaw-weixin@2.4.4 ..."
TGZ_FILE=$(npm pack @tencent-weixin/openclaw-weixin@2.4.4 2>&1 | tail -n 1)

if [ ! -f "$TGZ_FILE" ]; then
  echo "❌ 错误：未找到下载的 tgz 文件：$TGZ_FILE"
  exit 1
fi

echo "✅ 下载成功：$TGZ_FILE"

# 步骤2：安装插件
echo ""
echo "[步骤 2/3] 正在安装插件：$TGZ_FILE ..."
NPM_CONFIG_REGISTRY=https://registry.npmmirror.com openclaw plugins install "$TGZ_FILE"
echo "✅ 插件安装成功"

# 步骤3：使用 Node 脚本来生成二维码并同步等待扫码
# 改用 wechat_login_full.js（插件内部 API 方式），支持长轮询等待，二维码不过期
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ""
echo "[步骤 3/3] 正在启动微信扫码登录（Node API 方式，最长等待5分钟）..."

# 清理旧进程和临时文件
OLD_PIDS=$(ps aux | grep "wechat_login_full" | grep -v grep | awk '{print $2}')
if [ -n "$OLD_PIDS" ]; then
  for PID in $OLD_PIDS; do
    kill -9 "$PID" 2>/dev/null
  done
  sleep 1
fi
rm -f /tmp/wx_stdout.txt /tmp/wx_stderr.txt

# 后台启动 Node 脚本（异步等待扫码，最长5分钟）
nohup timeout 310 node "$SKILL_DIR/scripts/wechat_login_full.js" \
  > /tmp/wx_stdout.txt 2>/tmp/wx_stderr.txt &
LOGIN_PID=$!
echo "登录脚本 PID: $LOGIN_PID"

# 等待二维码生成（最多10秒，比 CLI 方式更快）
echo "⏳ 等待二维码生成..."
for i in $(seq 1 10); do
  if grep -q "^QR_URL:" /tmp/wx_stdout.txt 2>/dev/null; then
    break
  fi
  sleep 1
done

QRCODE_URL=$(grep "^QR_URL:" /tmp/wx_stdout.txt 2>/dev/null | head -1 | cut -d: -f2-)

if [ -n "$QRCODE_URL" ]; then
  echo "✅ 二维码已生成"
  echo ""
  echo "QRCODE_URL=$QRCODE_URL"
  echo ""
  echo "========================================="
  echo " 安装完成！请用微信扫描以下链接中的二维码："
  echo " $QRCODE_URL"
  echo " ========================================="
  echo " 登录脚本在后台等待扫码(PID: $LOGIN_PID)"
  echo " 脚本会在扫码成功后自动保存账号"
  echo " 扫码完成后执行以下命令查看结果："
  echo "   cat /tmp/wx_stdout.txt"
  echo "========================================="
else
  echo "⚠️ 未检测到二维码链接，查看日志："
  echo "  cat /tmp/wx_stderr.txt"
fi
