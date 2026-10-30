---
name: muse-ai
description: 用 MuseAI 创作、修改并生成歌曲，包括写词、调整副歌、设计风格与段落、生成纯音乐、查询进度、获取试听地址，以及处理登录、额度、超时和生成失败。适用于“帮我做一首歌”“副歌更抓耳”“生成并发我链接”等音乐创作请求；不处理与音乐创作无关的任务。
allowed-tools: exec read write huawei_id_tool
env:
  - 118052471_login_token: "华为账号服务提供的平台受管会话变量，仅交给 Muse CLI 用于当前用户的服务端鉴权；Agent 不接触其内容，也不展示、复制或持久化"
  - 118052471_login_token_expire_time: "由华为账号服务注入的有效期；Agent 只依据 whoami 返回的状态决定是否发起一次授权刷新"
---

# MuseAI 音乐创作

本 Skill 是可独立部署的小艺开放平台 Skill，作词、编曲资料与 Python CLI 均随包分发，不依赖其他 Skill。

## 按需读取

- 写词、改词、中文咬字、和声与 ad-lib：`references/lyrics.md`
- 风格、段落结构、人声编排与纯器乐：`references/arrangement.md`
- 需要具体流派配方时：`references/genres.md`
- 需要核对标签可靠性或确切写法时：`references/tags.md`
- 需要登录、生成、查询、排错或完整参数时：`references/runtime.md`

不要一次读取全部资料。

## 工作流

1. 判断用户要完整做歌，还是只写词、改词、调编曲、生成、查询或排错。
2. 只读取相关创作资料，形成标题、歌词或描述、`style`、人声和生成模式。
3. 涉及 API 操作时读取 `references/runtime.md`，先检查 CLI 版本和登录状态。
4. 首次生成前可查询额度，积分余额不直接等于可生成次数；提交返回 `credits` 时停止，并原样使用 `references/runtime.md` 中的固定提示。
5. 调用 `song generate` 异步提交一次并保存返回的 `taskId`。
6. 使用原 `taskId` 查询，直到任务完成且歌曲均为终态；只处理非空 `audioUrl`。
7. 对每首成功歌曲执行 `song download --work-id <workId> --output-dir /tmp/openclaw/muse-ai`，以接口返回的标题生成本地音频文件。
8. 用下载结果中的本地 `path` 作为音频附件交付；不得直接把 `audioUrl` 当附件，否则客户端会显示 CDN 哈希文件名。当前环境没有结构化发送工具时，在最终回复中为每首歌单独输出一行 `MEDIA:<path>`，不加 Markdown 包裹。
9. 用户不满意时，判断问题属于歌词、编曲还是执行，再修改对应输入并生成新任务。

## 执行约束

平台以 Skill 根目录为工作目录，命令统一使用：

```bash
python3 ./scripts/muse_cli.py <command> [args]
```

调用工具时必须同时传入非空字符串 `command` 和中文 `description`，例如：

`exec(command: "python3 ./scripts/muse_cli.py whoami", description: "检查 MuseAI 登录状态")`

禁止传命令数组、Markdown 代码块或 `/home/sandbox/...` 绝对脚本路径。除 `--help` 和 `--version` 外，stdout 必须按 JSON 解析，并以 `ok` 字段判断成败。

真机本次任务首次执行前运行一次：

`exec(command: "python3 ./scripts/muse_cli.py --version", description: "检查 Muse CLI 版本")`

当前必须输出 `muse 0.4.3`。文件不存在或版本不符时停止并报告 Skill 未更新。

仅当当前任务明确是安装、升级此 Skill，或用户明确要求清理旧备份时，才执行安装收尾。先用不带 `--apply` 的命令预览，把返回的候选目录名和旧版本号展示给用户，并取得用户对这些具体目标的明确删除确认；未经确认禁止执行 `--apply`。确认后，把这些候选项对应的 `confirmationToken` 作为独立参数执行：

`exec(command: "python3 ./scripts/muse_install.py cleanup-backups --apply <token1> <token2>", description: "清理用户已确认的 MuseAI 旧版本备份")`

必须用预览返回的真实令牌替换占位符，不得原样执行 `<token1>` 或 `<token2>`。

只有返回 `ok: true`，且 `remainingCandidates`、`remainingConflicts` 均为空、`rescanError` 为 `null`，才视为清理完成。确认令牌绑定预览时的目录名、备份版本，以及完整递归目录清单、对象身份、权限和全部文件内容；工具在删除前把目标原子移入私有隔离名并再次校验，删除后重新扫描同级备份。目标必须位于当前 `muse-ai` 同级、名称严格匹配 `muse-ai.bak-YYYYMMDD` 或 `muse-ai.bak-YYYYMMDDhhmmss`，且包含合法、版本不高于当前版本的 `muse-ai` Skill 结构。普通文件、符号链接、新版、结构不完整或预览后变化的目录均拒绝自动删除；被拒目录只要含 `SKILL.md` 或本身为符号链接，就会列入 `remainingConflicts` 并要求人工处理。普通音乐创作、生成、查询、登录和排错任务不得执行备份清理。

## 认证边界

- 先运行 `whoami`；用户未指定登录方式时，有效的华为或手机号凭据都可直接使用；用户明确指定时以其选择为准。
- 仅在无可用凭据且 `huawei_status` 为 `missing`、`expired` 或 `invalid_expiry` 时，调用一次 `huawei_id_tool(clientId=118052471, skillName=muse-ai)`，随后只复查一次 `whoami`。
- 用户明确选择手机号，或华为授权被拒绝/失败时，按 `references/runtime.md` 发送验证码并暂停等待用户提供验证码。
- 未收到用户验证码时禁止调用 `login verify`；禁止猜测、重复发码或展示明文 token。

## 失败与安全

- `generate` 非幂等。网络或服务端错误时任务可能已创建并扣费，先核对任务或额度，禁止盲目重发。
- `auth` 且当前 `auth_source=huawei` 时，在本次任务共用的一次刷新额度内调用 `huawei_id_tool` 并重试一次；额度已用或仍失败则进入手机号流程。禁止循环刷新或原样重试。
- `timeout` 使用原 `taskId` 续查；`credits` 以提交结果为准，停止生成并原样回复 `references/runtime.md` 中的固定提示；`params` 修正本地参数；其他错误按 `references/runtime.md` 有界处理。
- 只连接 `https://skill-api.muse.top` 及其返回的音频资源地址。
- 不在指令、脚本、示例或回复中写入 token、验证码、密码、设备标识和调试堆栈。
- 不生成仿冒指定在世歌手音色、侵权翻唱或违法违规内容。

最终至少返回任务状态；成功时返回标题，并把 `song download` 返回的本地路径作为音频附件发送。可附试听 URL，但不能用它替代已按标题命名的附件。
