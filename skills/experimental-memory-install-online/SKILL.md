---
name: experimental-memory-install-online
description: 当用户要求在小艺 / celiaclaw Docker 沙箱内从远端下载并安装 Celia 记忆插件时使用。触发场景：「在线安装 celia-memory」「从远端下载 celia」「从 GitCode GaussPD_Artifacts 安装」「小艺 docker 里联网装记忆」「install GaussPD memory online」。这是独立在线安装 skill：不调用 experimental-memory-install 的脚本，也不调用 GaussPD_Memory tarball 内的 scripts/install.sh；由本 skill 自己完成远端 manifest 解析、tarball 下载校验、解压、插件落盘、openclaw.json 合并、workspace skills 部署和 AGENTS.md 替换。默认把下载包内 celiaclaw/config/AGENTS.md 直接替换到 $CELIA_CONFIG_DIR/workspace/AGENTS.md；也可用 --agents-md 指定仓库内 AGENTS.md。执行任何安装动作前必须原样展示下方安全声明并取得用户明示同意。Read-write，会访问网络并修改 Docker 沙箱文件。
---

# experimental-memory-install-online 技能

## 安全声明（必须原样展示）

在任何 `--mode=execute` 真安装动作之前，agent 必须把下面 4 行中文正文逐字、
原样、完整展示给用户，然后通过 AskUserQuestion 询问“您已阅读并同意上述
自研记忆系统安全声明，确认继续安装吗？”。未得到显式 yes，不得执行。

```
本系统为自研记忆系统，属于内部测试版本，尚未正式发布，启用后将禁用
OpenClaw 内置记忆功能。内测期间，不对普通用户提供该自研记忆系统的维护服务。
如需停用，请发送"卸载自研记忆系统"命令，卸载时该自研记忆系统中的记忆数据
可能丢失，建议提前备份 workspace 文件夹下的重要内容。
```

## 用途

本 skill 是小艺 / celiaclaw Docker 沙箱的在线安装入口。它和离线
`experimental-memory-install` 并列存在，不复用旧 skill 脚本，也不调用
GaussPD_Memory release 包内的 `scripts/install.sh` hook。

安装动作由本 skill 的 `scripts/remote_install.py` 直接完成：

- 从 GaussPD_Artifacts 解析 `latest-<channel>.txt` 和 manifest。
- 下载或复用 `celia_memory.<version>.celiaclaw.<arch>.<variant>.tar.gz`。
- 校验 SHA256，原子解压到
  `$CELIA_CONFIG_DIR/extensions/celia_memory/install/<version>/`。
- 将 release 内的 `openclaw/memory-plugin`、`openclaw/shared`、
  `openclaw/bin/celia_memory_mcp_server` 落到该安装目录顶层。
- 安装 `memory-plugin` 运行时 npm 依赖。
- 合并 release 内 `openclaw/config/openclaw.json` 与
  `celiaclaw/config/openclaw.json` 到 Docker 的
  `$CELIA_CONFIG_DIR/openclaw.json`。
- 直接替换 `$CELIA_CONFIG_DIR/workspace/AGENTS.md`。
- 将 release 内 `celiaclaw/skills/` 部署到
  `$CELIA_CONFIG_DIR/workspace/skills/`。
- 切换 `install/current` 软链并按配置异步重启 `openclaw-gateway`。

## 调用流程

**Step 1 - plan**

```bash
ENTRY="$HOME/.openclaw/workspace/skills/experimental-memory-install-online/scripts/install.sh"
CELIA_LANG=zh bash "$ENTRY" --mode=plan --channel=rc
```

把 `[PLAN]...[/PLAN]` 原样给用户看，然后展示上方安全声明，并通过
AskUserQuestion 取得显式 yes/no。

**Step 2 - execute**

```bash
ENTRY="$HOME/.openclaw/workspace/skills/experimental-memory-install-online/scripts/install.sh"
CELIA_LANG=zh bash "$ENTRY" --mode=execute --confirmed --channel=rc
```

如果 Docker 内挂载了 GaussPD_Memory 源码仓，并且要使用仓内指定的
AGENTS.md 替换目标文件：

```bash
CELIA_LANG=zh bash "$ENTRY" --mode=execute --confirmed --channel=rc \
  --agents-md /path/to/GaussPD_Memory/integration/celiaclaw/config/AGENTS.md
```

未指定 `--agents-md` 时，默认使用下载 release 包内的
`celiaclaw/config/AGENTS.md`，这仍然是随 GaussPD_Memory 仓打包的 AGENTS.md。

## 参数

- `--channel=stable|rc|dev`：选择远端通道；默认 `rc`。
- `--dev`：等价 `--channel=dev`。
- `--version=<vTAG>`：安装指定远端版本。
- `--variant=full|full-manylinux_2_28|plugins`：指定 artifact；默认按宿主
  glibc 和 OpenSSL ABI 选择 full 变体。
- `--agents-md <path>`：用指定 AGENTS.md 直接替换
  `$CELIA_CONFIG_DIR/workspace/AGENTS.md`。
- `--no-replace-agents`：不替换 AGENTS.md。
- `--skip-gateway-restart`：安装后不调度 gateway 重启。
- `--skip-npm-install`：跳过 npm 依赖安装，仅用于调试。
- `--gateway-service <name>`：指定 supervisor 管理的 gateway 服务名；默认
  `openclaw-gateway`。
- `--restart-health-url <url>`：重启后在后台诊断日志中执行可选健康检查。
- `--allow-non-celiaclaw`：允许在未识别到 celiaclaw supervisor 指纹时继续
  execute；仅用于受控调试，常规非 celiaclaw 环境应使用
  `--skip-gateway-restart`。

## DFX 诊断

- execute 会生成 `$CELIA_LOG_DIR/diagnostics/<timestamp>/` 诊断目录。
- 诊断目录包含 preflight/post-install 环境快照、supervisor 状态、关键文件
  SHA256、openclaw.json 内 Celia 配置摘要、`post-install.json`、
  重启脚本日志，以及未调度自动重启时的 `restart-skip.json`。
- 自动重启前必须识别到 celiaclaw supervisor 指纹；否则 execute 会要求改用
  `--skip-gateway-restart`，避免在其他部署环境误重启。
- 重启控制器优先使用 PATH 中的 `supervisorctl`；如果 CLI 不在 PATH，但
  Python supervisor 模块可用，会自动兜底为
  `python3 -m supervisor.supervisorctl -c $CELIA_SUPERVISORD_CONF`。
  如部署环境有自定义入口，可用 `CELIA_SUPERVISORCTL_COMMAND` 覆盖。
- `services_restarted: scheduled` 仅表示已调度后台重启；实际 restart rc、
  after 状态和可选 healthcheck 结果以 `services_restart_log` 为准。
- `manual_restart_required: yes` 表示安装文件和配置已写入，但当前运行中的
  gateway 是否已加载新配置仍未知，需要按 `restart-skip.json` 中的建议命令
  手动重启或确认部署环境自己的重启机制。

## 不要做

- 不要用本 skill 处理离线预置 tarball 安装；离线流程继续用
  `experimental-memory-install`。
- 不要让本 skill 调用 `experimental-memory-install/scripts/install.sh` 或
  `experimental-memory-install/scripts/orchestrator.py`。
- 不要让本 skill 调用 release 包内 `scripts/install.sh`。
- 不要把 AGENTS.md 做增量注入；本在线流程的语义是直接替换目标文件。
