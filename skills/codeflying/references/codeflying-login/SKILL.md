---
name: codeflying-login
description: 手机号+短信验证码登录/注册码上飞。第一步：询问用户手机号；第二步：发送验证码；第三步：询问验证码；第四步：验证并保存 token。
---

# 码上飞手机号登录/注册

用户说"登录"、"注册"、"登录一下"时使用此技能，通过手机号+短信验证码完成登录或注册。所有渠道统一走此流程。

## 1. Description

通过手机号+短信验证码完成登录/注册，适用于非微信渠道用户。

流程：
1. 询问用户手机号
2. 发送短信验证码
3. 询问用户输入验证码
4. 验证登录，保存 token

## 2. When to use

- 用户需要登录或注册码上飞账号
- 系统提示需要用户身份认证时
- 其他技能（如 codeflying-app-create）检测到用户未登录时触发

## 3. How to use

### 第一步：询问用户手机号

直接向用户提问，获取手机号。例如：
```
请问您的手机号是多少？登录/注册码上飞需要验证手机号。
```

### 第二步：发送短信验证码

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "用户的sender_id" \
  --action "send_code" \
  --phone "用户手机号"
```

输出说明：
- `SEND_CODE_SUCCESS:手机号` — 发送成功
- `SEND_CODE_FAILED:错误信息` — 发送失败（如频率限制、手机号格式错误）

发送成功后，提示用户：
```
验证码已发送到您的手机，请查收短信并告诉我验证码。
```

### 第三步：用户输入验证码后，执行登录

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "用户的sender_id" \
  --action "phone_login" \
  --phone "用户手机号" \
  --code "用户输入的验证码"
```

根据输出判断：
- 输出包含 `LOGIN_SUCCESS:` — 登录成功，回复"登录成功！"然后**继续执行用户原来想做的操作**
- 输出包含 `LOGIN_FAILED:` — 登录失败（验证码错误/过期），提示用户重新获取验证码

### 第四步（可选）：检查登录状态

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "用户的sender_id" \
  --action "check_login"
```

- `LOGIN_SUCCESS:路径` — 已有有效 token，无需重新登录
- `NOT_LOGGED_IN` — 未登录，执行上述流程

### 参数说明

- `--sender_id`: 用户唯一标识符（必填），用于保存 token 文件
- `--action`: 操作类型
  - `send_code` — 发送短信验证码（需 `--phone`）
  - `phone_login` — 手机号+验证码登录（需 `--phone` 和 `--code`）
  - `check_login` — 检查本地登录状态
  - `cleanup` — 清理临时文件

### 可选：手机号签名自动登录（无验证码）

适用于已知用户手机号且服务端已部署对应接口时，可跳过短信验证码直接登录：

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "用户的sender_id" \
  --action "phone_auto_login" \
  --phone "用户手机号"
```

输出说明：
- `AUTO_LOGIN_SUCCESS:路径` — 自动登录成功，token 已保存
- `AUTO_LOGIN_FAILED:原因` — 失败，回退到短信验证码流程

**URL 参数加密规则**（供服务端对接参考）：
```
ts   = Unix 时间戳（10位字符串）
key  = HMAC-SHA256(nanobotSecret, ts)          # 32字节
ep   = base64_urlsafe( phone_bytes XOR key )   # 无末尾 =
sign = HMAC-SHA256(nanobotSecret, ep + ts).hex()

GET /wxlogin/login_by_phone_sign?ep={ep}&ts={ts}&sign={sign}
```

服务端验证：① |now−ts| ≤ 300s；② sign 校验；③ 解密 ep 得手机号，返回 token。

## 4. Edge cases

- 验证码发送频率限制：60 秒内同一手机号只能发一次，提示用户稍等。
- 验证码错误：提示用户重新输入或重新发送（需等待 60 秒）。
- 用户已登录（token 文件已存在）：`check_login` 直接返回 `LOGIN_SUCCESS`，无需重复登录。
- 手机号格式错误：`SEND_CODE_FAILED` 会包含具体错误信息，提示用户检查手机号。
