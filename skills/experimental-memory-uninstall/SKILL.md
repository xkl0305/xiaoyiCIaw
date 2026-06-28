---
name: experimental-memory-uninstall
description: 当用户要求卸载 / 禁用自研记忆系统时使用。触发场景：「卸载记忆」「卸载自研记忆系统」「uninstall gspd-memory」「关掉记忆能力」「remove the plugin」。**入口脚本**：先按用户来源选择 skill 目录；用户明确说“从 URL / GitCode tree 跑”时，必须 clone/定位该 URL 对应的 `skills/celiaclaw/experimental-memory-uninstall` 目录，并执行其 `scripts/uninstall.sh`；只有未指定 URL 时才默认使用 `~/.openclaw/workspace/skills/experimental-memory-uninstall/scripts/uninstall.sh`。入口 exec orchestrator.py，接受 `--mode=uninstall-{plan,execute,reboot}`。**绝对不要**直接调 `~/.openclaw/extensions/gspd_memory/install/current/scripts/uninstall.sh`——那是 tarball 自带的低层 hook（仅接 `disable|remove|help` 位置参数），由本 skill 的 orchestrator 内部按需触发，agent 直接调会绕过 plan/确认/软链清理/reboot 流程，且 hook 旧版本同步重启会触发 self-kill。三种模式：`disable`(仅在 openclaw.json 关掉)、`remove`(默认 — 删插件文件,DB 保留)、`purge`(remove + 删 DB,**不可恢复**)。**强制双重确认**:动作前 + 重启前(uninstall hook 不会自己重启 openclaw-gateway,需要走 reboot Step 把 plugin 从运行中的 gateway 内存里彻底卸下来)。`purge` 模式额外多一次确认。Read-write,会改本机文件。
---

# experimental-memory-uninstall 技能 / 卸载自研记忆系统

## 用途 / Purpose

把自研记忆系统从本机移除。三种模式按破坏性分级:

| Mode | 破坏性 | 由谁执行 | 说明 |
|---|---|---|---|
| `disable` | 最低 | tarball uninstall.sh | 只在 `openclaw.json` 关掉条目;插件文件、DB 全保留。可立刻 install 回来。 |
| `remove` (默认) | 中 | tarball uninstall.sh | disable + 删插件目录 + 删二进制。DB 不动;之后 install 会重新启用。 |
| `purge` | **最高** | tarball uninstall.sh + orchestrator 补刀 | remove + 删 DB 目录 `~/.openclaw/workspace/memory/gspd_memory/`（含 `gspd_memory.db` + `-shm`/`-wal`）+ 兼容删除老路径 `workspace/memory/gspd_memory.db` 与 `~/.openclaw/memory/gspd_memory.db`。**所有记忆永久丢失**。 |

> 实现细节:tarball 自带的 `scripts/uninstall.sh` 只支持 `disable` / `remove`。
> orchestrator 在 `purge` 模式下**先**用 `remove` 调 hook,**再**自己删 DB 文件
> (位置取自 `$GSPD_CONFIG_DIR/workspace/memory/`,兼容老路径 `$GSPD_CONFIG_DIR/memory/`)。

## 调用流程 / Invocation flow

> **入口路径(必须用 absolute path,不能 cd 到别处用相对 `scripts/`):**
>
>     # 如果用户明确给了 GitCode/GitHub tree URL 或说“从这个 URL 跑”，
>     # 必须先 clone/定位该 URL 对应的 GaussPD_Skills checkout，然后用：
>     SKILL_DIR=/path/to/GaussPD_Skills/skills/celiaclaw/experimental-memory-uninstall
>
>     # 只有用户没有指定 URL/外部来源时，才使用本机 workspace 默认副本：
>     SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-uninstall}
>
>     ENTRY="$SKILL_DIR/scripts/uninstall.sh"
>
> 下面 Step 2/3/4 都是这个 `$ENTRY`。**永远不要**用
> `~/.openclaw/extensions/gspd_memory/install/current/scripts/uninstall.sh` —— 那是
> tarball 自带的低层 hook (只接 `disable|remove|help`),由本 skill 的 orchestrator
> 内部触发,直接调会绕过 plan/确认/软链清理/Skills 重新部署等流程。
>
> 如果用户说“从
> `https://gitcode.com/CayleyVanguard/GaussPD_Skills/tree/main/skills/celiaclaw/experimental-memory-uninstall`
> 跑”，应先 clone `GaussPD_Skills`，然后把 `SKILL_DIR` 设为 clone 下的
> `skills/celiaclaw/experimental-memory-uninstall`。这种场景下不得执行 workspace 旧副本。

**Step 1 — locale 检测**:见 experimental-memory-install SKILL.md。

**Step 2 — 跑 plan**:

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-uninstall}
ENTRY="$SKILL_DIR/scripts/uninstall.sh"
GSPD_LANG=$GSPD_LANG GSPD_UNINSTALL_MODE={disable|remove|purge} \
    bash "$ENTRY" \
    --mode=uninstall-plan
```

输出含 `[PLAN]…[/PLAN]`,会列出当前安装版本(无安装就直接结束)、模式、即将做的事。
**用 AskUserQuestion** 让用户选 yes/no。
**`purge` 模式必须额外问一次**:「确认删除所有历史记忆?此操作不可恢复。」

**Step 3 — execute**:

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-uninstall}
ENTRY="$SKILL_DIR/scripts/uninstall.sh"
GSPD_LANG=$GSPD_LANG GSPD_UNINSTALL_MODE=<same> \
    bash "$ENTRY" \
    --mode=uninstall-execute --confirmed
```

orchestrator 把模式作为位置参数传给 hook(`bash uninstall.sh disable|remove`),
hook 跑完后:`purge` 模式 orchestrator 还会按上表删 DB 文件,最后清掉
`~/.openclaw/extensions/gspd_memory/install/{current,previous}` 软链让 `memory-status` 正确反映"已卸载"。

**Step 4 — reboot 二次确认**(必做):

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-uninstall}
ENTRY="$SKILL_DIR/scripts/uninstall.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=reboot --confirmed
```

**为什么 uninstall 必须单独 reboot**(跟 install 不一样):tarball 的
`scripts/uninstall.sh` 只 `pkill gspd_mcp_server`,**不**会重启 openclaw-gateway。
gateway 进程里还缓存着 memory-gspd 的 plugin handle(虽然 openclaw.json 已经
disabled,但运行时 import 还在内存里),不重启就只是配置层的卸载,运行时还在挂着。

`reboot` 模式会跑 `supervisorctl restart openclaw-gateway`,把 plugin 从运行
中的 gateway 内存里彻底卸下来。重启会中断当前对话通道,**必须告知用户**。

## 默认模式 / Default

未指定 `GSPD_UNINSTALL_MODE` → `remove`。

## 不要做的事 / Don't

- **❌ 绝对不要直接调** `~/.openclaw/extensions/gspd_memory/install/current/scripts/uninstall.sh`。
  那是 tarball 自带的低层 hook,只接 `disable|remove|help` 位置参数,看到 `--mode=...`
  会立刻 `[ERROR] 未知子命令` 退出。生产实测(install-20260510 sandbox)agent 第一次
  尝试就走错路径,把 tarball hook 当 skill 入口调。**所有 plan/execute/reboot 调用都
  必须用 `$ENTRY`**(选中的本 skill 目录里那个 wrapper,exec 到 orchestrator.py)。
  如果用户明确给了 GitCode/GitHub tree URL，`$ENTRY` 必须来自 clone/定位后的
  URL 目录，不能再跳回 workspace 旧副本。
- 用户没说"清理所有数据"或"purge"时,**绝对不要**用 purge 模式。
- **不要省略 Step 4 reboot 询问**;plugin 文件移除后,gateway 进程还在引用
  旧 import,不重启 = 卸载不彻底。这一步跟 experimental-memory-install 不同,install hook
  会自己重启,uninstall hook 不会。
- 不要把 `purge` 当 `remove` 的同义词;`remove` 留 DB 给将来 install 重新
  启用,`purge` 是"我想把这台机器恢复成从未装过自研记忆系统的样子"。
