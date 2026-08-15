---
name: weixin-clawbot-setup
description: 微信 ClawBot 安装与扫码登录一体技能。覆盖微信插件安装、重新授权/换绑、查看登录状态全流程。触发词：微信配置、微信插件安装、微信扫码绑定、重新登录微信、微信授权二维码、openclaw-weixin。统一使用 Node 插件内部 API 完成扫码登录（不再使用 openclaw channels login CLI 方式），支持长轮询等待，二维码从生成到扫码始终不超时。
---

# Weixin ClawBot Setup

## 一、安装流程（首次）

### 1. 运行安装脚本

```bash
bash <skill_dir>/scripts/install.sh
```

脚本自动完成：
1. 下载 `@tencent-weixin/openclaw-weixin` 包
2. 安装插件
3. 调用 `wechat_login_full.js`（Node 内部 API）生成二维码并**同步轮询等待扫码**（最长 5 分钟）
4. 输出 `QR_URL:<链接>`

### 2. 返回二维码给用户

提取二维码 URL 并生成图片发送给用户：

```bash
QR_URL="<提取的QR_URL>"
curl -s -o /tmp/wechat_qr_login.png \
  "https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QR_URL'))")"
```

使用 `send_file_to_user` 工具发送图片，告知用户扫码完成后找我。

### 3. 扫码完成 → 持久化 → 重启

检查登录结果：
```bash
cat /tmp/wx_stdout.txt | grep -E "^(DONE:|DUP:|FAIL:)"
```
- `DONE:<accountId>` → 继续
- `DUP:...` → 已绑定过，询问用户是否换绑
- `FAIL:...` → 告知失败，重新执行

**⚠️ 持久化配置（关键坑点）：** 脚本虽已调用 `triggerWeixinChannelReload` 写入配置，但 Gateway 重启会用自己的内存状态覆盖文件，导致新增条目丢失。**重启前必须先持久化：**

```bash
python3 <skill_dir>/scripts/ensure_weixin_config.py
python3 -m supervisor.supervisorctl restart openclaw-gateway
sleep 5
openclaw channels status | grep weixin
```

预期输出：`openclaw-weixin ... enabled, configured, running, in:just now`

## 二、重新授权 / 换绑 / 重新登录（日常）

适用于二维码过期、换微信账号等场景。流程与首次安装完全一致，只是跳过插件下载安装步骤。

### 快速命令

```bash
# 1. 启动登录（Node API，长轮询 5 分钟，二维码不超时）
nohup timeout 310 node <skill_dir>/scripts/wechat_login_full.js \
  > /tmp/wx_stdout.txt 2>/tmp/wx_stderr.txt &
sleep 4

# 2. 提取二维码 URL
QR_URL=$(grep "^QR_URL:" /tmp/wx_stdout.txt | cut -d: -f2-)

# 3. 生成图片并发送给用户
curl -s -o /tmp/wechat_qr_login.png \
  "https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QR_URL'))")"
send_file_to_user 发送 /tmp/wechat_qr_login.png 给用户

# 4. 用户扫码后检查结果
cat /tmp/wx_stdout.txt | grep -E "^(DONE:|DUP:|FAIL:)"

# 5. 持久化 + 重启
python3 <skill_dir>/scripts/ensure_weixin_config.py
python3 -m supervisor.supervisorctl restart openclaw-gateway
```

### 备选：使用 Shell 封装
```bash
bash <skill_dir>/scripts/wechat_qr_login.sh
```

## 三、查看状态

```bash
openclaw channels status | grep weixin
```

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `scripts/install.sh` | 首次安装：下载 tgz → 安装插件 → 同步等待扫码（Node API，二维码不过期） |
| `scripts/wechat_login_full.js` | **核心脚本**。Node.js 自动化：生成 QR → 长轮询等待扫码 → 保存账号 |
| `scripts/wechat_qr_login.sh` | Shell 封装，一行命令完成扫码登录 |
| `scripts/gen_qrcode.sh` | 独立生成二维码（也走 Node API），用于非安装场景 |
| `scripts/ensure_weixin_config.py` | **配置持久化脚本**。重启 Gateway 前执行，防止新增配置被覆盖 |

## 注意事项

### 配置持久化（核心坑点）

`wechat_login_full.js` 会自动调用 `triggerWeixinChannelReload()` 将配置写入 `openclaw.json`，但 Gateway 重启时使用**自身内存状态**写回文件，新增的微信配置条目会被丢弃。**重启前必须执行持久化。**

**解决方案：** 每次重启 Gateway 前执行：
```bash
python3 <skill_dir>/scripts/ensure_weixin_config.py
```
该脚本会自动添加：
- `plugins.entries.openclaw-weixin: { "enabled": true }`
- `channels.openclaw-weixin: { "channelConfigUpdatedAt": "<ISO时间>" }`

### 其他

- Gateway 重启必须用 `python3 -m supervisor.supervisorctl restart openclaw-gateway`，不要用 `openclaw gateway restart`
- `wechat_login_full.js` 最长等待 5 分钟，超时需重试
- 扫码后若微信弹出验证码输入界面，让用户告诉数字，在脚本终端中输入
- 所有临时文件统一使用 `/tmp/wx_stdout.txt`（二维码URL/结果）和 `/tmp/wx_stderr.txt`（日志）
