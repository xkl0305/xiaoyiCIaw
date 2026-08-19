---
name: codeflying-app-update
description: 通过 AI 对话修改已有应用功能，需要先明确修改哪个应用，这是 CodeFlying 的核心能力。提交后不会立即修改，该工具会判读修改的需求是否清晰，可能会需要用户进一步的确认，你需要在中间进行沟通。⚠️ 平台硬限制：每个应用在其整个生命周期内只能修改一次，已修改过的应用无法再次修改。
---

# AI 对话修改应用

## Description
通过自然语言描述需求，让 AI 修改应用功能。这是 CodeFlying 的核心能力。 
没有返回结果之前，不要重复启动同样的修改任务。


## When to use
- 用户说："帮我把首页顶部文案改一下"
- 用户说："增加一个活动报名入口"

## ⚠️ 前置条件：登录检查

**必须先检查用户是否已登录！**

```bash
ls ~/.nanobot-xiaofeifei/workspace/users/[sender_id]
```

- 如果文件**存在**，继续后续流程。
- 如果文件**不存在**，说明用户未登录，**按以下流程操作：**

### 未登录处理流程

1. **询问用户手机号**：向用户发消息："修改应用需要先登录码上飞账号，请问您的手机号是多少？"

2. **发送短信验证码**：
   ```bash
   python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "send_code" --phone "[手机号]"
   ```
   - 输出包含 `SEND_CODE_SUCCESS` → 提示用户："验证码已发送，请查收短信并告诉我验证码。"，结束本轮等待用户回复。
   - 输出包含 `SEND_CODE_FAILED` → 提示用户检查手机号格式或稍后重试。

3. **用户回复验证码后，执行登录**：
   ```bash
   python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "phone_login" --phone "[手机号]" --code "[验证码]"
   ```
   - 输出包含 `LOGIN_SUCCESS:` → 回复"登录成功！"，然后继续下方的正常修改流程。
   - 输出包含 `LOGIN_FAILED:` → 提示用户验证码错误或已过期，可回复"重新发送"重新获取验证码。

---

## ⚠️ 限制：每个应用只能修改一次

**在执行更新命令之前，必须先判断目标应用是否已经被修改过。**

判断方式：执行
  ```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-list/requirement_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" --app-id 123
  ```

- 如果应用**尚未修改过** → 正常进入后续修改流程。
- 如果应用**已经被修改过** → 直接回复用户：
  "抱歉，一个应用只能更新修改一次，该应用已经更新过了。"
  然后直接结束，不执行任何修改命令。


## 任务模板

**主 agent 遵从执行规则开发**

#### 执行规则（必须遵守）
- 执行开发命令时，exec参数设置为timeout=1800。
- 命令会先返回 Command still running (session xxx) → 这很正常，立即用 process(poll, sessionId=xxx, timeout=60000) 检查进度。
- 每轮 poll 最多等60秒，重复直到看见 Process exited with code 0。
- 在此期间不得回复用户任何消息。
- 如果 timeout(1800秒/30分钟)到了还没结束 → 回复"开发超时，请稍后重试"，直接结束。
- 进程结束后，提取日志中的结果，然后才回复用户。
- 主agent 必须持续等待，不得提前中断回合。

按照下面的任务模板执行，**未返回结果前不要重复启动同样的任务**
---
⚠️ 严格禁止：不得使用 read_file / edit_file / write_file 读写任何代码文件，只能运行命令和发送消息。

### 第零步：若已知用户手机号，先生成自动登录参数，后续所有 login_wx URL 均需追加：
  ```bash
python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "[sender_id]" --action get_auth_query
  ```
输出含 AUTH_QUERY:xxx → auth_query=xxx；未知手机号或失败则 auth_query 为空。

URL 拼接规则（全局适用）：
- auth_query 非空：https://www.codeflying.net/codeflying_h5?login_wx=xxx&[auth_query]
- auth_query 为空：https://www.codeflying.net/codeflying_h5?login_wx=xxx

如果 channel 是 wechatoa，先发通知：“⚙️ 正在为您修改应用”
其他渠道无需发此通知。

### 第一步：执行修改
执行以下命令修改应用（timeout=1800，无论结果如何只运行一次，禁止重试）：
```bash
python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-update/app_update.py \
  --sender_id "[sender_id]" \
  --message "[用户需求]" \
  --app-id [app_id]
```
⚠️ timeout 固定 1800。命令超时不重试，直接按情况C处理。
⚠️ 此命令只能调用一次，禁止并行或重复调用。

命令执行完成后：
⚠️ **必须先完整读取全部输出，提取以下所有字段后再发消息，全程只发 1 条消息：**

从输出中提取：
- has_quota_sent  → 是否含 QUOTA_CARD_SENT
- has_quota_start → 是否含 QUOTA_CARD_START（不含 QUOTA_CARD_SENT）
- done            → 是否含 "应用修改完成"
- view_url     → "应用预览地址: " 后的 URL（无则为空）
- remaining_pts   → "REMAINING_POINTS:" 后的数字（无则为空）

按优先级处理（只命中第一个，处理完直接结束）：

━━━ 情况A：has_quota_sent = true ━━━
⛔ 禁止发送任何 message，直接结束。

━━━ 情况A2：has_quota_start = true ━━━
配额不足，发送消息：“ 开发积分已用完～\n\n升级会员或充值积分可继续开发！\n\n👉 [立即充值/升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query]) ”
**需要把链接渲染成可以点击的形式**，例如
```markdown
[立即充值/升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query])
```
直接结束。

━━━ 情况C：命令超时（被 kill）━━━
  发送消息：“应用开发遇到问题，请重试或换个描述方式。”
  直接结束。

━━━ 情况B：done = true ━━━
管理应用地址（auth_query 已在第零步生成，直接使用）：
- auth_query 非空：http://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps&[auth_query]
- auth_query 为空：http://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps

渠道是 wechatoa：
  剩余积分为[remaining_pts]

其他渠道（含 feishu、default）：
  查询剩余积分：
```bash
    python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying_common/quota.py --sender_id "[sender_id]"
```
    输出含 QUOTA_OK 且含 LOW_POINTS_WARNING:N →剩余积分为 N
    输出含 QUOTA_OK 且不含 LOW_POINTS_WARNING → 从输出提取 REMAINING_POINTS: 后数字 ,作为剩余积分
    查询失败或无积分数据 → 不发积分消息


━━━ 其他情况：done = false 且无超时 ━━━
  message(content="⏳ 应用还在修改中，完成后会主动通知您～", channel="[channel]", chat_id="[chat_id]")
  直接结束。


## 处理结果(done = true)
获取到view_url 和剩余积分

⚠️以下三件事情必须在同一条消息中全部完成，缺一不可：

1.先通过send_html_card工具将view_url 发送给用户（失败后立即重试一次）
  ⚠️send_html_card必须在markdown链接之前调用。
2.**把链接展示给用户，需要把 view_url 渲染成可以点击的形式**，例如
```markdown
[查看](<view_url>)
```
3.说明剩余积分

⛔ 禁止把view_url 的原始长链接直接粘贴给用户


## Edge cases
- 需求描述为空：提示必须填写需求
- 如果用户询问进度，告知"正在开发中，完成后会自动通知"
- 主agent 未返回前不要重复启动同样的任务
- 用户尝试第二次修改同一个应用：直接提示"一个应用只能更新修改一次，该应用已经更新过了"，不执行修改命令。

- 用户明确提出**发布微信小程序，网站/H5，鸿蒙应用（元服务），下载源码**：引导前往官网操作，回复：
  "该操作需要在码上飞官网操作：https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps"
- 如果用户没有明确提出，**禁止向用户主动提及**

- 命令输出包含 `LOW_POINTS_WARNING_SENT`：低积分预警卡片已直接发给用户（wechatoa），无需额外操作。 
- 命令输出包含 `LOW_POINTS_WARNING:`（不含 SENT）：非 wechatoa 渠道，agent 追加回复：
  "⚠️ 温馨提示：您的积分余额即将不足，建议及时充值，避免开发中断。\n👉 立即充值/升级会员：https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team"
