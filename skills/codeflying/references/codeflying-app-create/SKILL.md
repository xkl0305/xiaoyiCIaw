---
name: codeflying-app-create
description: 通过 AI 对话开发拍照背单词、拍照识别植物、拍照识别建筑、拍照分析穿搭风格、拍照识别卡路里、拍照识别文物这六类拍照识别类应用。不适用于六个场景之外的其他类型应用的开发。
---

# AI 对话创建应用

## When to use
- 用户说："帮我做一个 拍照背单词 应用"
- 继续对话修改某个应用时

## 执行步骤（必须按顺序执行，每一步结果决定是否继续）

> ⚠️ **wechatoa 消息配额**：微信公众号每轮对话最多发 5 条消息，**登录检查过程中不得向用户发送任何消息**。

### 第一步：登录检查（exec，同步，全程静默不发消息）

```bash
ls ~/.nanobot-xiaofeifei/workspace/users/[sender_id]
```

- 文件**存在** → 已登录，直接进入第二步。
- 文件**不存在**：走手机号登录流程（见下方），结束本轮。

#### 手机号登录流程
1. 向用户发消息："开发应用需要先登录码上飞账号，请问您的手机号是多少？"，结束本轮等待回复。
2. 用户回复手机号后，发送验证码：
   ```bash
   python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "send_code" --phone "[手机号]"
   ```
   - `SEND_CODE_SUCCESS` → 提示用户查收短信，结束本轮等待回复。
   - `SEND_CODE_FAILED` → 提示用户检查手机号格式或稍后重试。
3. 用户回复验证码后，执行登录：
   ```bash
   python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py --sender_id "[sender_id]" --action "phone_login" --phone "[手机号]" --code "[验证码]"
   ```
   - `LOGIN_SUCCESS:` → 回复"登录成功！"，然后继续执行第二步（需求确认）。
   - `LOGIN_FAILED:` → 提示验证码错误/过期，可重新获取。

---

### 第二步：需求确认（开发前必须完成）

**不要直接开始开发**，先向用户确认需求细节。根据用户已提供的信息，针对性地追问缺失的关键信息，例如：
- 应用的核心功能是什么？目标用户是谁？
- 有哪些必须有的页面或功能模块？

⚠️ 追问要自然简洁，不要列举过多问题，1～3 个最关键的点即可。若用户已提供了足够详细的需求，可直接确认后进入第三步。**默认为H5应用**。禁止向用户提及H5字样。

用户确认需求后，**必须**回复以下固定内容，不得删减或改写：
"好的，开始为您开发～"
然后进入第三步。

---

### 第三步：主 agent 直接执行开发命令

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
⚠️ 严禁发送 APP_NOTIFY_DONE 等系统标记给用户。

#### 第零步：若已知用户手机号，先生成自动登录参数，后续所有 login_wx URL 均需追加：
  ```bash
python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-login/login.py \
  --sender_id "[sender_id]" --action get_auth_query
  ```
输出含 AUTH_QUERY:xxx → auth_query=xxx；未知手机号或失败则 auth_query 为空。

URL 拼接规则（全局适用）：
- auth_query 非空：https://www.codeflying.net/codeflying_h5?login_wx=xxx&[auth_query]
- auth_query 为空：https://www.codeflying.net/codeflying_h5?login_wx=xxx

#### 第一步：检查配额（必须先于开发执行）
```bash
python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying_common/quota.py \
  --sender_id "[sender_id]" --new-app
```
━━━ 配额检查结果处理 ━━━ 

输出包含 QUOTA_CARD_SENT：
  配额不足，卡片已直接发出（wechatoa 渠道）。⛔ 禁止发任何 message，直接结束。

输出包含 QUOTA_CARD_START（不含 QUOTA_CARD_SENT）：
  配额不足，发送消息：“ 开发积分已用完～\n\n升级会员或充值积分可继续开发！\n\n👉 [立即充值/升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query]) ”
  发完后等待用户回复，不要直接结束任务。
- 如果用户表达“重新开发”、“重试”、“已删除”、“好了”或者又重复开发需求：
   自动重新执行配额检查命令。QUOTA_OK 继续执行开发，仍然不足，再次提示用户
- 如果用户明确放弃，直接放弃开发，直接结束。

输出包含 QUOTA_OK：
  
配额充足，进行下一步

#### 第二步：执行开发
直接运行以下命令（timeout=1800，无论结果如何只运行一次，禁止重试）：

  ```bash
  python3 -u ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-app-create/app_create.py \
    --sender_id "[sender_id]" \
    --message "[用户需求]"
  ```
  ⚠️ timeout 固定 1800。命令超时不重试，直接按情况C处理。
  ⚠️ 此命令只能调用一次，禁止并行或重复调用。

命令执行完成后：
⚠️ **必须先完整读取全部输出，提取以下所有字段后再发消息，输出内容不向用户展示**

从输出中提取：
- has_quota_sent  → 是否含 QUOTA_CARD_SENT
- has_quota_start → 是否含 QUOTA_CARD_START（不含 QUOTA_CARD_SENT）
- view_url     → "应用预览地址: " 后的 URL（无则为空）
- remaining_pts   → "REMAINING_POINTS:" 后的数字（无则为空）

按优先级处理（只命中第一个，处理完直接结束，禁止再发任何消息）：

━━━ 情况A1：has_quota_sent = true ━━━
⛔ 禁止发送任何 message，直接结束。

━━━ 情况A2：has_quota_start = true ━━━
配额不足，发送消息：“ 开发积分已用完～\n\n升级会员或充值积分可继续开发！\n\n👉 [立即充值/升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query]) ”
**需要把链接渲染成可以点击的形式**，例如
```markdown
[立即充值/升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query])
```
直接结束。

━━━ 情况C：命令超时（被 kill）━━━
  发送消息：“️ **应用开发遇到问题**，请重试或换个描述方式。”
  直接结束。

━━━ 情况B：preview_url 非空 ━━━
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



### 第四步：处理结果(preview_url 非空)
获取到view_url 和剩余积分

⚠️以下三件事情必须在同一条消息中全部完成，缺一不可：

1.先通过send_html_card将view_url 发送给用户（失败后立即重试一次）
  ⚠️send_html_card必须在markdown链接之前调用。
2.**把链接展示给用户，需要把 view_url 渲染成可以点击的形式**，例如
```markdown
[查看](<view_url>)
```
3.说明剩余积分

⛔ 禁止把view_url 的原始长链接直接粘贴给用户



## 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| --message, -m | 是 | 用户需求描述 |
| --app-id | 否 | 应用 ID（新建传 0） |
| --requirement-id | 否 | 需求 ID（新建传 0） |
| --pre-memory-id | 否 | 上次对话 ID（新建传 0） |
| --action | 否 | 指定动作：Preview, Deploy |

## Edge cases
- 需求描述为空：提示必须填写需求
- 如果用户询问进度，告知"正在开发中，完成后会自动通知"
- 未返回前不要重复启动同样的任务

- 用户明确提出**发布微信小程序，网站/H5，鸿蒙应用（元服务），下载源码**：引导前往官网操作，回复：
  "该操作需要在码上飞官网操作：https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps"
- 如果用户没有明确提出，**禁止向用户主动提及**


-  输出包含 `LOW_POINTS_WARNING_SENT`：低积分预警卡片已直接发给用户（wechatoa），无需额外操作。
-  输出包含 `LOW_POINTS_WARNING:`（不含 SENT）：非 wechatoa 渠道，agent 追加回复：
  "⚠️ 温馨提示：您的积分余额即将不足，建议及时充值，避免开发中断。\n👉 立即充值/升级会员：https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team"

注意: message 中不要丢失用户的核心需求信息，例如用户上传了截图或图片，要将其中和应用相关的内容尽可能提取并传入 message，避免生成的应用货不对板。

- ⚠️**脚本崩溃≠后端失败**`：`app_create.py`因本地错误（如变量未定义、库缺失、WS断连）提前退出时，后端可能已经成功创建了应用并接收了需求。此时：
1. 先调用 `app_list.py --sender_id"[sender_id].\"`检查是否有新创建的应用
2. 如果存在匹配的应用，**不要重新创建**，改用`codeflying-app-update/app_update.py`继续开发
3. 如果无新应用，再重新执行`app_create.py`
