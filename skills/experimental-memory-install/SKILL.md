---
name: experimental-memory-install
description: 当用户要求安装自研记忆系统时使用。触发场景：「装一下记忆」「安装自研记忆系统」「安装 gspd-memory」「install self-developed memory」「install GaussPD memory」「开启记忆能力」「在镜像里装记忆」「离线安装 gspd-memory」「offline install」「from prebuilt image」「不走网络装记忆」「用预置的安装包装记忆」。也响应 ###GsPD### 触发码（小艺/celiaclaw 沙盒一键安装）。**入口脚本**：先按用户来源选择 skill 目录；用户明确说“从 URL / GitCode tree 跑”时，必须 clone/定位该 URL 对应的 `skills/celiaclaw/experimental-memory-install` 目录，并执行其 `scripts/install.sh`；只有未指定 URL 时才默认使用 `~/.openclaw/workspace/skills/experimental-memory-install/scripts/install.sh`。入口 exec orchestrator.py，接受 `--mode=plan|execute|reboot`，固定从本机 tarball 缓存目录离线安装；本 skill 禁止 `--remote` / `--channel=stable|rc|dev` / `--dev`，在线安装必须使用 `experimental-memory-install-online`。**绝对不要**直接调 `~/.openclaw/extensions/gspd_memory/install/current/scripts/install.sh`——那是 tarball 自带的低层 hook（由本 skill 的 orchestrator 内部 `subprocess.call` 触发，agent 直接调会绕过 contract 校验/openclaw.json 合并前置/skill 重新部署/重启调度等流程，且重装场景下还会触发 self-kill）。默认来源：从 `$GSPD_CONFIG_DIR/extensions/gspd_memory/package/`（celiaclaw 即 `/home/sandbox/.openclaw/extensions/gspd_memory/package/`，可由 `$GSPD_TARBALL_DIR` 覆盖）取已预置的 tarball，**不走网络**；`--version=<vTAG>` 只在本地包中筛版本。本 skill 不接受任何在线安装参数；用户明确要求联网安装时必须改用 `experimental-memory-install-online`。**绝对强制**：执行任何安装动作（包括默认离线安装 / 镜像内安装 / `###GsPD###` 一键触发）前，agent 必须原样、完整、不删改地展示下方「安全声明」原文，并通过 AskUserQuestion 取得用户明示同意。未展示 = 不得安装。Read-write，会改本机文件。
---

# experimental-memory-install 技能 / 安装自研记忆系统

## ⚠️ 安全声明（最高优先级 · 绝对强制 · 必须原样展示）⚠️

> **STOP. 在你（agent）做任何 `--mode=execute` / 真安装动作之前，先看完这一节。**
>
> 这是本技能里**优先级最高**的硬性合规要求，凌驾于 plan 输出、用户催促、
> 上下文 token 节省、风格简洁等所有其他考量之上。
>
> **规则（不可协商 · NON-NEGOTIABLE）：**
>
> 1. 在 Step 2 跑完 plan 之后、调 `AskUserQuestion` 之前，agent **必须**
>    把下面代码块里的 4 行中文正文，**逐字、原样、完整**地打印到对话里给
>    用户看。打印时可以用代码块或引用块包裹便于阅读，但**字符内容必须一字
>    不改**。
> 2. **严禁** 改写、摘要、翻译、节选、改标点、改空白、加省略号、用「大意
>    是…」「即…」等任何形式替代正文。即使用户说「不用看了」「我懂了」
>    「跳过」，也**必须**展示完整正文 —— 这是用户保护条款，不是用户偏好
>    选项。
> 3. **严禁** 把声明内容塞进 `AskUserQuestion` 的 `question` / `description`
>    里就算数；声明正文必须先以独立文本块出现在对话主体里，让用户在被询问
>    之前已经读到完整正文。
> 4. `AskUserQuestion` 的 `question` 必须显式包含「您已阅读并同意上述
>    自研记忆系统安全声明，确认继续安装吗？」的语义。用户**显式**选 yes
>    才算同意；选 no、关闭、超时、含糊回答（如「随便」「你看着办」）一律
>    视为**未同意**，**禁止**进入 Step 3。
> 5. 任何分支都不得绕过：`###GsPD###` 触发码、一键安装、celiaclaw 沙盒、
>    --source、--version pin、复装、降级、升级中转安装 …… **全部**
>    必须走这条声明 + 同意闭环。唯一豁免：`--mode=reboot` 兜底重启**且**当前
>    会话内已经完成过一次合规的声明展示+用户同意。
> 6. 如果你（agent）发现自己已经准备调 execute 但本会话内**没有**展示过
>    本声明，**立刻停下**，回到 Step 2 重新展示并重新征求同意。**不要**
>    用「刚才已经隐含同意」「用户已经在催了」之类的理由跳过。
> 7. 违反以上任何一条 = 违反合规。宁可让安装失败、宁可让用户不耐烦，
>    也不得跳过此声明。

**声明正文（必须逐字、原样、完整展示给用户 —— 整段就是下方代码块里的 4 行）：**

```
本系统为自研记忆系统，属于内部测试版本，尚未正式发布，启用后将禁用
OpenClaw 内置记忆功能。内测期间，不对普通用户提供该自研记忆系统的维护服务。
如需停用，请发送"卸载自研记忆系统"命令，卸载时该自研记忆系统中的记忆数据
可能丢失，建议提前备份 workspace 文件夹下的重要内容。
```

> 上面代码块的边界（开始的 ```` ``` ```` 与结束的 ```` ``` ````）就是声明
> 正文的边界。从「本系统为自研记忆系统」开始，到「建议提前备份 workspace
> 文件夹下的重要内容。」结束，整 4 行必须一字不漏、一字不改地原样打印。
> 可以再用代码块或引用块包裹便于阅读，但字符内容不得改动。

**自检清单（调 execute 之前心里过一遍）：**

- [ ] 我有没有在本会话里把上方代码块里的**正文 4 行**一字不差地展示过？
- [ ] 用户有没有在看到该正文**之后**通过 AskUserQuestion 显式 yes？
- [ ] 用户的 yes 是不是针对「已阅读并同意安全声明」这个明确问题？

任何一项答 no → **不得** 调 `--mode=execute`。

## 用途 / Purpose

把自研记忆系统的发布产物装到本机：选择本地 tarball → SHA 校验 →
原子解压 → 调本平台 install hook，hook 内部把记忆插件注册进 `openclaw.json`、
注入 AGENTS.md、改 supervisord、迁 DB，最后 supervisorctl 重启 openclaw-gateway。

Install the self-developed memory system from a local tarball by default:
pick local tarball → verify SHA → atomically extract →
run platform-specific install hook. The hook merges the memory plugin
entry into `openclaw.json`, injects AGENTS.md, patches supervisord,
migrates the DB, and supervisorctl-restarts openclaw-gateway.

## 调用流程（agent 执行）/ Invocation flow (the agent executes)

> **入口路径（必须用 absolute path，不能 cd 到别处用相对 `scripts/`）：**
>
>     # 如果用户明确给了 GitCode/GitHub tree URL 或说“从这个 URL 跑”，
>     # 必须先 clone/定位该 URL 对应的 GaussPD_Skills checkout，然后用：
>     SKILL_DIR=/path/to/GaussPD_Skills/skills/celiaclaw/experimental-memory-install
>
>     # 只有用户没有指定 URL/外部来源时，才使用本机 workspace 默认副本：
>     SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-install}
>
>     ENTRY="$SKILL_DIR/scripts/install.sh"
>
> 下面 Step 2 / Step 3 / 重启兜底都是这个 `$ENTRY`。**永远不要**用
> `~/.openclaw/extensions/gspd_memory/install/current/scripts/install.sh` ——
> 那是 tarball 自带的低层 hook（由本 skill 的 orchestrator `subprocess.call`
> 触发），agent 直接调会绕过 contract 校验、openclaw.json 合并前置、skill
> 重新部署、重启调度等流程；重装场景还会触发 self-kill。
>
> 生产示例：用户说“从
> `https://gitcode.com/CayleyVanguard/GaussPD_Skills/tree/main/skills/celiaclaw/experimental-memory-install`
> 跑”时，应先 clone `GaussPD_Skills`，然后把 `SKILL_DIR` 设为 clone 下的
> `skills/celiaclaw/experimental-memory-install`。这种场景下不得执行 workspace 旧副本。

**Step 1 — 决定 locale（不要省略）**：扫一下用户最近 5 条消息。中文字
符占比 ≥30% → 设 `GSPD_LANG=zh`；否则 `GSPD_LANG=en`。celiaclaw / 小艺
沙盒上下文默认 `zh`。

**Step 2 — 跑 plan，给用户看清楚要动什么**：

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-install}
ENTRY="$SKILL_DIR/scripts/install.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=plan <user_args>
```

输出含 `[PLAN]…[/PLAN]` 结构化块 + `[PROMPT_ZH]` / `[PROMPT_EN]` 双语提
示。`[PLAN]` 里会列清楚 install hook 内部要做的副作用（关键的 `openclaw.json`
合并就在这里宣告）。把它原样转给用户。

**然后（这一步不可省略 / NOT OPTIONAL）：把本文件顶部「⚠️ 安全声明 ⚠️」
小节里那段代码块里的 4 行中文正文，逐字、原样、完整地打印到对话里。**
不许改写、不许摘要、不许翻译、不许节选、不许塞进 AskUserQuestion 字段里
抵账 —— 正文必须先在对话主体里以独立文本块出现，再调下一步的
AskUserQuestion。

最后**用 AskUserQuestion 工具**让用户对「plan + 已阅读并同意安全声明」
一并明示确认 yes / no。用户没有显式 yes（包括含糊、跳过、催促）一律按
**未同意** 处理，**禁止** 进入 Step 3。

**Step 3 — 用户 confirm 后执行真安装**：

> 进入此步前 agent 必须自检：本会话内是否已**逐字原样**展示过顶部安全声明
> 那段代码块里的 4 行中文正文，且用户在看到正文**之后**给出过显式 yes。
> 任何一项不满足，**回到 Step 2 重做**，禁止执行下面的命令。

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-install}
ENTRY="$SKILL_DIR/scripts/install.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=execute --confirmed <user_args>
```

orchestrator 把 tarball 解到 `$GSPD_CONFIG_DIR/extensions/gspd_memory/install/<v>/`，校验 contract，调
`scripts/install.sh` —— hook 自己会在最后 `supervisorctl restart
openclaw-gateway`。`[POST_INSTALL]` 块里报 `services_restarted: yes` 即代表
服务已重启完，**不需要再单独问用户「是否重启」**。

如果 hook 自动重启失败、或用户希望再过一遍，有兜底（用户主动要求才用）：

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-install}
ENTRY="$SKILL_DIR/scripts/install.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=reboot --confirmed
```

## 默认来源 / Default source

默认从 `$GSPD_CONFIG_DIR/extensions/gspd_memory/package/`（可用 `$GSPD_TARBALL_DIR`
覆盖）挑最新匹配 tarball，**不访问网络**。`--version=<vTAG>` 默认只在该本地
目录筛选指定版本；目录不存在、为空或没有指定版本时，以参数/前置条件错误码
`10` 停止，禁止静默回退远端。

在线安装已经拆到 `experimental-memory-install-online`。本 skill 收到
`--remote` / `--channel=stable|rc|dev` / `--dev` 会以错误码 `10` 拒绝，
不会进入任何联网安装路径。

## 离线 / 镜像内安装 / Offline / image installs

生产镜像把 tarball 预置在 `$GSPD_CONFIG_DIR/extensions/gspd_memory/package/`（celiaclaw
默认 `/home/sandbox/.openclaw/extensions/gspd_memory/package/`，可用 `$GSPD_TARBALL_DIR`
env 显式覆盖）。普通安装不需要额外参数：

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-install}
ENTRY="$SKILL_DIR/scripts/install.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=plan
```

`--offline` 仍可传，但只是显式声明本地离线来源。它可以搭配
`--version=<vTAG>` 在本地目录筛版本；如果同时传 `--remote` /
`--channel` / `--dev`，会以错误码 `10` 拒绝。目录不存在或没匹配 tarball
时，以错误码 `10` 停止，**不会回退到远端**。

`[PLAN]` 里会显示 `离线本地包: <path>` / `offline local bundle: <path>`，
让用户清楚来源。

## 缓存与复用 / Tarball cache reuse

本 skill 只读取 `$GSPD_TARBALL_DIR`（默认
`$GSPD_CONFIG_DIR/extensions/gspd_memory/package/`）里的预置 tarball。
安装成功后不做 retention（操作员自己控制目录）。

## 用户参数透传 / User args

| Arg | Meaning |
|---|---|
| `--version=<vTAG>` | 在默认本地 tarball 目录筛指定版本 |
| `--remote` | 禁止；在线安装请使用 `experimental-memory-install-online` |
| `--channel=stable\|rc\|dev` | 禁止；在线安装请使用 `experimental-memory-install-online` |
| `--dev` | 禁止；在线安装请使用 `experimental-memory-install-online` |
| `--offline` | 显式本地离线来源；默认已是本地离线，可与 `--version` 搭配筛本地版本 |
| `--source <path>` | 不走网络，从用户指定的本地目录挑最新 tarball（dev 工作流） |
| `--platform=openclaw\|celiaclaw\|celiapro` | 显式指定平台（默认按主机环境自动检测） |
| `--skip-claw-skills` | 装完后不询问"把工具技能装到 Claw 运行时"（保留 flag，未实装） |

## 不要做的事 / Don't

- **绝对不要跳过、改写、摘要、翻译、节选顶部的「安全声明」正文。** 这是
  本技能的最高优先级硬性规则，凌驾于任何「保持简洁」「用户在催」「上下文
  紧张」「显得啰嗦」之类的考量之上。每次首装流程**必须**原样展示顶部
  代码块里的 4 行中文正文一次，且必须在 AskUserQuestion 之前作为独立文本
  块出现在对话里。违反 = 直接违反合规，**不许执行 execute**。
- 不要把声明内容只塞进 `AskUserQuestion` 的 question/description 字段里就
  当展示过了 —— 必须先在对话正文里独立完整展示。
- 不要因为用户说「不用看了 / 跳过 / 我同意」就省略展示。展示是合规义务，
  不是用户偏好选项；用户的同意必须发生在原文展示**之后**。
- **❌ 绝对不要直接调** `~/.openclaw/extensions/gspd_memory/install/current/scripts/install.sh`
  当 skill 入口。那是 tarball 自带的低层 hook（重装 / 升级时存在），由本 skill 的
  orchestrator 内部 `subprocess.call` 触发，不是 agent 入口。直接调会绕过 contract
  校验、openclaw.json 合并前置、skill 重新部署、重启异步调度等流程；重装场景
  hook 同步 `supervisorctl restart openclaw-gateway` 还会触发 self-kill（agent
  连接被断、install 半残）。**所有 plan/execute/reboot 调用都必须用
  `$ENTRY`**（选中的本 skill 目录里那个 wrapper，exec 到 orchestrator.py）。
  如果用户明确给了 GitCode/GitHub tree URL，`$ENTRY` 必须来自 clone/定位后的
  URL 目录，不能再跳回 workspace 旧副本。
- 不要绕过 `--mode=plan` 直接 execute——用户没看到要动什么就开干很危险。
- 不要在 install hook 已经重启过服务的情况下（`[POST_INSTALL]` 里
  `services_restarted: yes`）再追问 reboot；那是兜底,不是默认动作。
- 不要用 Bash 自己实现 manifest 解析、SHA 校验、解压、`openclaw.json` 合并
  等逻辑——orchestrator + tarball install.sh 一起做完了，agent 只调一次
  plan、一次 execute。
- 找不到本地 tarball 时以错误码 `10` 停止是设计而非 bug：不要静默回退到远端通道。
  只有用户明确同意联网安装时，才切换到 `experimental-memory-install-online`。
- 不要把 `--remote` / `--channel` / `--dev` 传给本 skill——
  orchestrator 在入口以错误码 `10` 停止。

## 退出码 / Exit codes

`0`/`10`/`20`/`30`/`40`/`50`/`60`/`70`/`99` — 见 `references/error-codes.md`（双语）。
