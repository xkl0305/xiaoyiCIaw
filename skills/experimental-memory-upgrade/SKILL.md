---
name: experimental-memory-upgrade
description: 当用户要求升级已安装的自研记忆系统到一个更新版本时使用。触发场景：「升级记忆」「升级自研记忆系统」「升级 gspd-memory」「upgrade memory plugin」「换个新版本」「用本地包升级」「离线升级记忆」。**入口脚本**：先按用户来源选择 skill 目录；用户明确说“从 URL / GitCode tree 跑”时，必须 clone/定位该 URL 对应的 `skills/celiaclaw/experimental-memory-upgrade` 目录，并执行其 `scripts/upgrade.sh`；只有未指定 URL 时才默认使用 `~/.openclaw/workspace/skills/experimental-memory-upgrade/scripts/upgrade.sh`。入口 exec orchestrator.py，接受 `--mode=upgrade-{plan,execute}`。**默认从本机 tarball 缓存目录升级，不联网**；远端只在用户明确说“联网升级 / 从远端升级 / 拉最新 / 指定远端版本 / 安装开发预览版（--dev / latest-dev / PR 预览包）”时通过 `--remote` / `--channel=stable|rc|dev` / `--dev` 显式启用。**绝对不要**直接调 `~/.openclaw/extensions/gspd_memory/install/current/scripts/upgrade.sh`——那是 tarball 自带的低层 hook（由 install.sh 的 `check_existing_installation` 自我委派触发，它做 stop/swap/start/health-probe），agent 直接调会绕过 DB 快照、contract 校验、orchestrator 备份逻辑等流程。技能在动手前自动备份 DB,升级走与 install 同一条流水(本地 tarball/显式远端 → 校验 → 解压 → 调 hook),hook 内部 `check_existing_installation` 检测到旧服务在跑会自动委派给 upgrade.sh,由它做 supervisorctl 停-启-健康检查;失败时 DB 快照保留供手动回滚。**强制确认**:动作前用 AskUserQuestion 询问。Read-write,会改本机文件。Should NOT be used for fresh install (use experimental-memory-install instead) or downgrade unless user explicitly passes --allow-downgrade.
---

# experimental-memory-upgrade 技能 / 升级自研记忆系统

## 用途 / Purpose

把当前安装的自研记忆系统升到一个新版本。比 experimental-memory-install 多做一件事:
**升级前先快照 DB**。升级流水本体跟 experimental-memory-install 完全一致 —— orchestrator
默认选本地 tarball → 解 tarball → 调 `scripts/install.sh`,install.sh 检测到 `gspd_mcp_server` 在跑
就内部委派给 `scripts/upgrade.sh`,由 upgrade.sh 做停服-换包-启服-健康检查。

Upgrade the currently installed self-developed memory system. The only thing
it adds on top of experimental-memory-install is a **DB snapshot before mutation**.
The local-tarball/extract/hook pipeline is identical: the platform `install.sh`
detects a running `gspd_mcp_server` and self-dispatches to `upgrade.sh`,
which handles the supervisorctl stop / swap / start / health-probe cycle.

## 调用流程 / Invocation flow

> **入口路径(必须用 absolute path,不能 cd 到别处用相对 `scripts/`):**
>
>     # 如果用户明确给了 GitCode/GitHub tree URL 或说“从这个 URL 跑”，
>     # 必须先 clone/定位该 URL 对应的 GaussPD_Skills checkout，然后用：
>     SKILL_DIR=/path/to/GaussPD_Skills/skills/celiaclaw/experimental-memory-upgrade
>
>     # 只有用户没有指定 URL/外部来源时，才使用本机 workspace 默认副本：
>     SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-upgrade}
>
>     ENTRY="$SKILL_DIR/scripts/upgrade.sh"
>
> 下面 Step 2 / Step 3 都是这个 `$ENTRY`。**永远不要**用
> `~/.openclaw/extensions/gspd_memory/install/current/scripts/upgrade.sh` ——
> 那是 tarball 自带的低层 hook(由 install.sh 的 `check_existing_installation`
> 自我委派触发,做实际的 stop/swap/start/health-probe),agent 直接调会绕过
> DB 快照、contract 校验、orchestrator 备份与熔断保护等流程。
>
> 如果用户说“从
> `https://gitcode.com/CayleyVanguard/GaussPD_Skills/tree/main/skills/celiaclaw/experimental-memory-upgrade`
> 跑”，应先 clone `GaussPD_Skills`，然后把 `SKILL_DIR` 设为 clone 下的
> `skills/celiaclaw/experimental-memory-upgrade`。这种场景下不得执行 workspace 旧副本。

**Step 1 — 决定 locale**:扫用户最近 5 条消息;中文字符 ≥30% → `GSPD_LANG=zh`,
否则 `en`。celiaclaw 默认 zh。

**Step 2 — 跑 plan,明示要升到哪一版本 + 备份策略**:

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-upgrade}
ENTRY="$SKILL_DIR/scripts/upgrade.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=upgrade-plan <user_args>
```

输出 `[PLAN]…[/PLAN]` 块,会列出:当前安装版本、目标版本、是否 downgrade
(如果是会提示要 `--allow-downgrade`)、DB 快照路径、tarball 来源、hook
内部依次会做的副作用、以及 hook 失败时的回滚提示。**用 AskUserQuestion** 让
用户选 yes/no。

**Step 3 — 用户 confirm 后执行升级**:

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-upgrade}
ENTRY="$SKILL_DIR/scripts/upgrade.sh"
GSPD_LANG=$GSPD_LANG \
    bash "$ENTRY" \
    --mode=upgrade-execute --confirmed <user_args>
```

orchestrator:
1. 从 `$GSPD_DB_PATH` / `~/.openclaw/workspace/memory/gspd_memory/gspd_memory.db`
   /（fallback：旧路径 `workspace/memory/gspd_memory.db` 或 `memory/gspd_memory.db`）
   按优先级取第一个真存在的 DB，复制到
   `~/.openclaw/extensions/gspd_memory/backups/upgrade_<ts>/`
2. 调 experimental-memory-install 的 execute 路径,contract 通过后调 `scripts/install.sh`
3. install.sh 的 `check_existing_installation` 看到 mcp 在跑 → 委派 upgrade.sh
4. upgrade.sh:supervisorctl stop → 拷贝新插件 → supervisorctl start → 健康探针

完成后 `[POST_INSTALL]` 块里报 `services_restarted: yes`(由 hook 完成),不需要
单独问用户「是否重启」 —— 服务在 hook 里就重启完了。

如果 hook 失败:DB 快照仍在 `~/.openclaw/extensions/gspd_memory/backups/upgrade_<ts>/`
留着,orchestrator **不做自动回滚**,需要手动 `experimental-memory-install --version=<旧版本>`
回去然后从快照恢复 DB。

## 用户参数 / User args

同 experimental-memory-install。默认从 `$GSPD_TARBALL_DIR` 本地离线升级；
`--version=<vTAG>` 默认只筛本地包。远端升级必须显式传 `--remote` /
`--channel=stable|rc|dev` / `--dev`。加上:

| Arg | Meaning |
|---|---|
| `--allow-downgrade` | 允许从新版降到旧版(默认拒绝;会丢更新版引入的能力) |
| `--rollback` | (保留;暂未实装)直接回滚到上一份备份。当前请改用手动 install + 复制快照 DB |

## 不要做的事 / Don't

- **❌ 绝对不要直接调** `~/.openclaw/extensions/gspd_memory/install/current/scripts/upgrade.sh`
  当 skill 入口。那是 tarball 自带的低层 hook(由 install.sh 的
  `check_existing_installation` 自我委派触发,做 stop/swap/start/health-probe);agent
  直接调会绕过 DB 快照、contract 校验、orchestrator 备份与熔断保护等流程,且
  其同步 `supervisorctl stop` 还会触发 self-kill(install/uninstall 同 pattern,
  生产实测过)。**所有 plan/execute 调用都必须用
  `$ENTRY`**(选中的本 skill 目录里那个 wrapper,exec 到 orchestrator.py)。
  如果用户明确给了 GitCode/GitHub tree URL，`$ENTRY` 必须来自 clone/定位后的
  URL 目录，不能再跳回 workspace 旧副本。
- 不要拿 experimental-memory-install 模拟 upgrade —— 那不会做 DB snapshot,hook 失败后没材料回滚。
- 不要在用户没明示的情况下传 `--allow-downgrade`。
- 不要在 hook 已经自己重启过服务(`[POST_INSTALL] services_restarted: yes`)
  的情况下再追问 reboot;`--mode=reboot` 是兜底,不是默认动作。
