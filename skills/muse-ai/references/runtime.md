# Muse CLI 运行手册

本页负责认证、命令参数、异步任务和错误处理。歌词内容见 `references/lyrics.md`，风格与结构见 `references/arrangement.md`。

## 命令与输出契约

真实入口为：

```bash
python3 ./scripts/muse_cli.py <command> [args]
```

下文用 `muse ...` 简写，执行时必须替换为完整入口，并调用：

`exec(command: "python3 ./scripts/muse_cli.py ...", description: "本次操作说明")`

关键规则：

1. 解析 stdout，stderr 只用于诊断和进度。
2. 除 `--help`、`--version` 外，stdout 始终是单个 JSON 信封。
3. 以 `ok` 判断成败，不只看退出码。
4. 全局参数放在叶子子命令之后，例如 `muse song query --task-id T --auth-source phone`。

```json
{"ok": true, "schemaVersion": 1, "data": {}}
{"ok": false, "schemaVersion": 1, "error": {"type": "auth", "http": 401, "message": "..."}}
```

退出码为 `0` 成功、`1` 运行错误、`2` 用法错误；用法错误也会输出 `error.type=params` 信封。

## 首次检查与认证

真机每次任务首次操作先检查版本：

```bash
muse --version
```

必须输出 `muse 0.4.3`。随后查询本地凭据状态：

```bash
muse whoami
```

`data` 包含 `has_token`、`auth_source`、`huawei_status` 和已掩码的 `auth_token`。`auth_source` 为 `huawei`、`phone`、`override` 或 `null`；`huawei_status` 为 `valid`、`missing`、`expired` 或 `invalid_expiry`。

- 用户未指定登录方式时，有效的华为或手机号凭据都可直接使用；用户明确指定时以其选择为准。
- `whoami` 的 `valid` 仅表示本地凭据未到期。排查解绑或登录异常时，使用 `member --auth-source huawei` 验证服务端状态；按 Skill 的一次刷新限制处理 `auth` 错误。不得输出凭据文件内容或使用刷新 Token 查询业务信息。
- 仅在没有任何可用凭据且华为状态为 `missing`、`expired` 或 `invalid_expiry` 时，按 `SKILL.md` 调用一次账号授权工具，再复查一次。
- 用户选择手机号或华为授权失败时发送验证码：

```bash
muse login send-code --phone 13800138000 --auth-source phone
```

只有返回 `ok: true` 才表示发送成功。此时停止并等待用户提供验证码；收到后才能执行：

```bash
muse login verify --phone 13800138000 --code '<用户验证码>' --auth-source phone
```

本次任务后续认证命令追加 `--auth-source phone`。`logout` 只清除手机号登录凭据；华为解绑由账号管理页处理。

## 标准生成流程

```bash
muse member
muse song generate --mode custom --lyrics '[Verse]...' --title '标题' --style '风格描述' --voice female
muse song query --task-id <taskId>
muse song info --work-id <workId>
muse song download --work-id <workId> --output-dir /tmp/openclaw/muse-ai
```

默认异步生成并立即返回 `{"taskId":"..."}`。保存这个 ID，再按需轮询。需要单命令等待时可加：

```bash
muse song generate --mode custom --lyrics '...' --wait --interval 5 --timeout 600
```

`--interval` 默认 5 秒，`--timeout` 默认 600 秒，`0` 表示无限等待。

## 命令参考

### 全局参数

| 参数 | 默认 | 用途 |
| --- | --- | --- |
| `--config PATH` | Muse 默认配置路径 | 覆盖手机号配置文件 |
| `--token JWT` | 无 | 临时覆盖 token，不落盘 |
| `--auth-source auto\|huawei\|phone` | `auto` | 指定认证来源 |
| `--device-id ID` | 自动生成 | 临时覆盖设备 ID |
| `--retries N` | `3` | 调整读请求重试次数 |
| `--no-retry` | 关闭 | 禁止自动重试 |
| `--verbose` | 关闭 | 向 stderr 输出诊断 |
| `--base-url URL` | 官方 API | 仅本地开发调试；Skill 运行时禁止覆盖 |

对应环境变量为 `MUSE_CONFIG`、`MUSE_TOKEN`、`MUSE_AUTH_SOURCE`、`MUSE_DEVICE_ID` 和 `MUSE_BASE_URL`。

### 登录与账号

- `login send-code --phone <P>`：发送短信，成功 `data={"ok":true}`。
- `login verify --phone <P> --code <C>`：验证并保存手机号 token，返回 `{"newReg":<bool>}`。
- `logout`：清除手机号 token，保留设备 ID。
- `whoami`：纯本地查询，所有 token 均掩码。
- `member`：返回会员类型、标签、积分和过期时间；积分余额不直接等于可生成次数，实际能否提交以生成接口结果为准。

### `song generate`

| 参数 | 必需 | 说明 |
| --- | --- | --- |
| `--mode custom\|instrumental` | 是 | 歌词模式或纯器乐模式 |
| `--description TEXT` | 三选一 | 文本内容，`-` 从 stdin 读取 |
| `--lyrics TEXT` | 三选一 | `--description` 的可读别名 |
| `--description-file PATH` | 三选一 | 从文件读取，`-` 从 stdin 读取 |
| `--title T` | 否 | 标题 |
| `--style S` | 否 | 风格描述 |
| `--voice male\|female\|random` | 否 | 人声 |
| `--song-model M` | 否 | 默认由服务端选择 |
| `--wait` | 否 | 等待至终态 |
| `--interval SEC` | 否 | 轮询间隔 |
| `--timeout SEC` | 否 | 等待预算 |

三个内容来源必须且只能提供一个。`instrumental` 内容去除首尾空白后至少 10 个 Unicode 字符，`custom` 内容必须非空。使用 `-` 时必须实际提供 stdin；交互式 TTY 会被拒绝，避免挂死。

### 查询命令

- `song query --task-id <T>`：返回任务状态及歌曲数组。
- `song info --work-id <W>`：使用当前登录凭据返回单曲歌词、时长等详情；华为来源同时携带绑定渠道头。
- `song download --work-id <W> [--output-dir DIR]`：使用当前登录凭据读取单曲详情并下载音频；默认输出到当前目录，文件名使用歌曲标题，重名时依次追加 `-2`、`-3`。返回 `workId`、`title`、`filename` 和绝对 `path`。

任务和单曲状态均为整数：`0` 待处理、`1` 生成中、`2` 完成、`3` 失败。只有任务为 `2` 且每首歌均为 `2` 或 `3` 才是终态；未完成歌曲的 `audioUrl` 可能是空字符串。未知 `taskId` 会表现为 `{"status":0,"songs":[]}`，因此必须保存生成接口返回的真实 ID。

下载只接受 MuseAI 返回的 HTTPS 音频地址，单文件上限 100 MiB；标题中的路径分隔符和跨平台非法字符会被替换。交付时使用 JSON 中的本地 `path` 作为结构化音频附件；当前环境未提供发送工具时，在最终回复中逐行输出 `MEDIA:<path>`。不要直接把 `audioUrl` 作为附件，否则客户端通常沿用 CDN 哈希对象名。

## 错误与重试

| `error.type` | 处理 |
| --- | --- |
| `auth` | 当前来源为华为时，在本次任务的一次刷新额度内刷新并重试一次；否则进入手机号流程 |
| `credits` | 停止提交，原样回复下方固定提示；用户明确要求继续后才可再次提交 |
| `params` | 修正参数后再执行 |
| `not_found` | 检查任务或作品 ID |
| `rate_limit` | 退避后有界重试 |
| `server`、`network` | 读请求可有界重试；生成请求先核对任务或额度 |
| `timeout` | 使用错误中的原 `taskId` 续查 |
| `generation_failed` | 调整内容或参数后创建新任务 |
| `internal` | 作为 CLI 缺陷报告 |

读类请求和轮询会对 429、5xx、网络错误自动进行最多 3 次指数退避；`generate` 非幂等，CLI 不自动重试。生成丢失响应时任务可能已创建并扣费，禁止直接重发。

`error.http=null` 通常表示本地校验失败；服务端拒绝会保留实际 HTTP 状态。

歌曲服务业务码 `10004`（即使 HTTP 为 200 或 400）及 HTTP 403 均按 `credits` 处理。`10004` 会出现在 `error.code`；不要把它当普通 `params`，也不要因 HTTP 200 误判为生成成功。即使先前 `member` 显示 VIP 或正积分余额，也以本次提交的 `credits` 结果为准。

面向用户只回复以下固定文案，原样保留品牌名、标点及末尾 `~`：

> 抱歉，本次提交任务失败，免费积分已用完，如需立即使用，可下载「Muse AI」App获取免费额度，或进行充值~

此时不追加 VIP/积分用途的推测、后台排查建议或追问，也不承诺次日刷新。保留已准备的歌词和生成参数，在用户明确要求继续后才可再次提交。

## 凭据安全

- 华为 token 由 CLI 从小艺凭据文件读取，不写入 Muse 配置。
- 手机号 token 保存在权限为 `0600` 的本地配置中。
- 命令行和环境变量覆盖值不写回配置。
- 禁止读取、打印、转述或把明文 token 拼入回复。
