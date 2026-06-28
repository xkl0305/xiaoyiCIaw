---
name: experimental-memory-status
description: 当用户想看当前自研记忆系统运行状态时使用 —— 安装版本号、mcp_server / openclaw-gateway 进程是否在跑、DB 路径与大小、记忆条数、最近一次 install/upgrade 日志的末尾。入口脚本先按用户来源选择 skill 目录；用户明确说“从 URL / GitCode tree 跑”时，必须 clone/定位该 URL 对应的 `skills/celiaclaw/experimental-memory-status` 目录，并执行其 `scripts/status.sh`；只有未指定 URL 时才默认使用 `~/.openclaw/workspace/skills/experimental-memory-status/scripts/status.sh`。Read-only,**不需要确认**:直接跑就好。触发:「memory 现在啥情况」「memory-status」「查记忆状态」「查 gspd 状态」「are memories running」。
---

# experimental-memory-status 技能 / 自研记忆系统状态查询

## 用途 / Purpose

只读查询当前安装的自研记忆系统状态。一次 Bash 调用全部输出,
agent 把结果转给用户即可,**无需确认 prompt**。

Read-only status query. One Bash call, agent forwards output to user, no
confirmation needed.

## 调用 / Invocation

如果用户说“从
`https://gitcode.com/CayleyVanguard/GaussPD_Skills/tree/main/skills/celiaclaw/experimental-memory-status`
跑”，应先 clone `GaussPD_Skills`，然后把 `SKILL_DIR` 设为 clone 下的
`skills/celiaclaw/experimental-memory-status`。这种场景下不得执行 workspace 旧副本。

```bash
SKILL_DIR=${SKILL_DIR:-$HOME/.openclaw/workspace/skills/experimental-memory-status}
ENTRY="$SKILL_DIR/scripts/status.sh"
bash "$ENTRY"
```

可选参数:

```bash
bash "$ENTRY" --platform=celiaclaw   # 显式指定平台(默认按主机环境自动检测)
```

## 输出格式 / Output format

`key: value` 一行一项,机器可读,agent 可以直接复述。包含三段:

**orchestrator 自身报的:**
- `platform` — celiaclaw / openclaw / celiapro
- `installed_version` — `~/.openclaw/extensions/gspd_memory/install/current` 软链指向的版本号(无安装则 `none`)
- `install_root` — 实际安装目录

**tarball 自带 `scripts/status.sh` 报的**(orchestrator 通过 `GSPD_EXTRACT_ROOT` 透传路径):
- `plugin_dir` / `config_dir` — celiaclaw 默认 `/home/sandbox/.openclaw/extensions/gspd_memory/install/current` / `/home/sandbox/.openclaw`
- `memory_plugin_present` / `memory_plugin_version`
- `mcp_binary_present` / `mcp_binary_size_kb`
- `mcp_pid` / `mcp_starttime_jiffies`
- `gateway_pid` — openclaw-gateway 进程
- `db_path` / `db_size_kb` — 默认 `$CONFIG_DIR/workspace/memory/gspd_memory/gspd_memory.db`
- `mem_count_l0` — 如果机器装了 sqlite3,直接 select count

**最近一次操作的日志尾巴:**
- `latest_log: ~/.openclaw/logs/gspd_memory/<verb>-<ts>.log`
- `--- tail ---` 后面是该日志末 10 行

## 不要做的事 / Don't

- 不要替用户解读"健康/不健康" —— 把 raw output 给出来,让用户自己判断。
- 不要在这里调 install / upgrade / uninstall 的 mode。读不到状态是正常的
  (比如还没安装,`installed_version: none`),原样转给用户即可。
- 不要因为 `mcp_pid: none` 就建议 reboot —— 用户可能就是有意 disable 了。
  如果他确实在排查"装好了为什么不工作",才指向 `experimental-memory-install` 或 `--mode=reboot`。
