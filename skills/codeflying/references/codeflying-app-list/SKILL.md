---
name: codeflying-app-list
description: 获取 CodeFlying 应用列表，支持分页和筛选，也可以传入具体的应用ID查询一个应用的详细信息
---

# 获取应用列表

## Description
获取当前租户下的所有应用列表，支持分页、按名称搜索等。

## When to use
- 用户说："我的应用列表"
- 用户说："查看所有应用"
- 用户说："有哪些应用"
- 需要获取应用 ID 进行后续操作时

## ⚠️ 前置条件：登录检查

**在执行命令之前，必须先检查用户是否已登录！**

```bash
ls ~/.nanobot-xiaofeifei/workspace/users/[sender_id]
```

- 如果文件**存在**，继续后续流程。
- 如果文件**不存在**，说明用户未登录，**按以下流程操作：**

### 未登录处理流程

1. **询问用户手机号**：向用户发消息："查看应用列表需要先登录码上飞账号，请问您的手机号是多少？"

2. **发送短信验证码**：
   ```bash
   python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "send_code" --phone "[手机号]"
   ```
   - 输出包含 `SEND_CODE_SUCCESS` → 提示用户："验证码已发送，请查收短信并告诉我验证码。"，结束本轮等待用户回复。
   - 输出包含 `SEND_CODE_FAILED` → 提示用户检查手机号格式或稍后重试。

3. **用户回复验证码后，执行登录**：
   ```bash
   python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "phone_login" --phone "[手机号]" --code "[验证码]"
   ```
   - 输出包含 `LOGIN_SUCCESS:` → 回复"登录成功！"，然后继续下方的正常查询流程。
   - 输出包含 `LOGIN_FAILED:` → 提示用户验证码错误或已过期，可回复"重新发送"重新获取验证码。

## How to use
```bash
# 获取应用列表（默认第1页，每页10条）
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-list/app_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID"

# 指定分页
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-list/app_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" -p 1 -s 20

# 按名称搜索
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-list/app_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" -n "商城"

# 获取单个应用详情
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-list/app_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" --id 123
```

### 参数说明
| 参数         | 必填 | 说明                                       |
|------------|------|------------------------------------------|
| -p, --page | 否 | 页码，默认 1                                  |
| -s, --size | 否 | 每页条数，默认 10                               |
| -n, --name | 否 | 按名称搜索                                    |
| --id       | 否 | 获取指定应用详情                                 |
| --json ,-j | 否 | 输出原始JSON，**必须检查遍历每个preview 的预览链接是否到期**，跳过则有可能拿到已失效的链接 |


## Edge cases
- 无应用：返回空列表
- 应用 ID 不存在：提示应用不存在
- 预览链接到期处理：脚本已对每个预览链接做了到期检查，输出中会附带 `expired` 标记
   - `expired:True` → **不要发卡片，不要发链接**，向用户说明："预览链接已到期，需要回到码上飞官网重启预览才能查看"
   - `expired:False` → 通过 `send-html-card` 将预览链接以卡片形式发送给用户（失败后立即重试一次），**禁止把原始长链接直接粘贴给用户**
- **禁止出现"H5"字样**：向用户展示应用信息时，不得出现"H5"、"H5用户界面"等字样，直接称“预览链接”或“预览”即可。
- 当使用`--json` 参数的时候，脚本只返回API 原始数据，**必须要在获取到JSON 后**，额外遍历每个preview 的url，请求验证是否返回404或包含“预览已到期”。
