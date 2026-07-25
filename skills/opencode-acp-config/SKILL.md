---
name: opencode-acp-config
description: opencode安装使用问题修复，当涉及本地opencode相关操作时，必须先阅读此skill
---

# OpenCode 基于 ACP 接入 OpenClaw 配置

一键完成 opencode 通过 ACP 协议接入 openclaw 的全部配置，包括 ACPX 插件安装、opencode-ai 依赖安装、provider 配置、ACP 启用和服务重启。

## 适用场景

- 用户需要将 opencode 通过 ACP 协议接入 openclaw
- 用户需要配置 xiaoyi provider 连接 openclaw 服务
- 用户需要启用 openclaw 的 ACP 功能

## SKILL 目录结构

```
opencode-acp-config/
├── SKILL.md              ← 本文件，功能介绍与使用说明
└── scripts/
    ├── setup_acp.sh      ← 一键配置脚本
    ├── check_acp.sh      ← 环境检查脚本
    └── reinstall_opencode.sh ← OpenCode 跨架构恢复脚本
```

## 前置条件

- 已安装 openclaw、npm、python3
- `~/.openclaw/.xiaoyienv` 文件中已配置以下环境变量：
  - `SERVICE_URL`：openclaw 服务地址
  - `PERSONAL-UID`：个人用户 UID
  - `PERSONAL-API-KEY`：个人 API 密钥

## 使用方法

### 场景一：首次配置 / 重新配置

执行一键配置脚本。

调用 `exec` 工具执行以下命令，并设置：

- `timeout: 0`
- 不使用后台执行（`background: false`）

命令：

```bash
bash scripts/setup_acp.sh
```

### 场景二：检查是否已安装成功

当用户询问"安装好了没"、"是否配置成功"、"ACP 能不能用"等问题时，或在 gateway 重启后需要确认环境状态时，优先执行检查脚本，而非重复执行安装脚本。

调用 `exec` 工具执行以下命令，并设置：

- `timeout: 0`
- 不使用后台执行（`background: false`）

命令：

```bash
bash scripts/check_acp.sh
```

脚本会逐项检查以下 11 项，输出每项的 PASS/FAIL 状态：

1. openclaw 命令可用
2. npm 命令可用
3. python3 命令可用
4. .xiaoyienv 文件存在
5. SERVICE_URL 已配置
6. PERSONAL-UID 已配置
7. PERSONAL-API-KEY 已配置
8. ACPX 插件已安装
9. opencode-ai 已安装
10. opencode xiaoyiprovider 已配置
11. ACP 配置已启用
12. ACPX 插件参数已配置
13. openclaw-gateway 运行中

**退出码**：`0` 表示全部就绪，`1` 表示存在缺失项。

- 如果检查全部通过，直接告知用户"环境已就绪"，无需再执行安装脚本
- 如果存在缺失项，根据缺失内容判断：少量项缺失可执行安装脚本自动修复；如果是 gateway 未运行，尝试单独重启

脚本会自动按顺序完成以下所有步骤，并在 stdout 输出每一步的执行结果：

1. **前置条件检查** — 验证 openclaw、npm、python3 命令可用，环境变量文件存在
2. **读取环境变量** — 从 `~/.openclaw/.xiaoyienv` 读取 SERVICE_URL、PERSONAL-UID、PERSONAL-API-KEY
3. **安装 ACPX 插件** — 检查是否已安装，未安装则自动安装并启用，设置 npm 目录权限
4. **安装 opencode-ai** — 在 `~/` 目录下安装 opencode-ai npm 包
5. **配置 opencode provider** — 读取环境变量，自动写入或合并 `~/.config/opencode/opencode.jsonc` 中的 xiaoyiprovider 配置
6. **启用 ACP 配置** — 自动写入或合并 `~/.openclaw/openclaw.json` 中的 acp 配置
7. **重启 openclaw-gateway** — 执行 `python3 -m supervisor.supervisorctl restart openclaw-gateway`
8. **配置验证** — 检查插件状态和配置文件是否就绪

## 脚本行为说明

- 已安装的 ACPX 插件会自动跳过，不会重复安装
- 已存在的配置文件会以合并方式更新，不会覆盖已有配置
- API Key 在输出中会被隐藏显示为 `****`
- 任何步骤失败时脚本会立即终止并输出错误信息
- 如果脚本没有停止，即使中间结果有异常error后者warn，均不需要干涉，直至模型处理完成，尤其是acpx安装时文件夹权限问题不需要处理，脚本会自动处理
- 你需要把中间执行的状态告知用户，并且需要在脚本执行之前告知用户最后一步是重启gateway，会出现相关重启提示，重启之后可以通过执行 `bash scripts/check_acp.sh` 来验证是否安装成功
- 当用户在 gateway 重启后询问”安装好了没”时，**必须先执行 check_acp.sh 检查环境状态**，根据检查结果回答用户，不要猜测或仅凭记忆判断
- 

## OpenCode 使用说明

配置脚本执行成功后，即可通过以下方式使用 opencode：

- 使用acp协议基于openclaw的subagent机制调度opencode,可以直接对小艺claw说：“用openclaw帮我实现xxxx功能”
- 直接输入/acp spawn opencode --bind here实现绑定，绑定之后可以直接和opencode对话，记得使用完成之后使用/acp close关闭链接
- 如需将代码提交到 GitHub，请参考使用 **github-cli** skill
- 如需使用云空间保存相关代码，请参考使用 **huawei-drive** skill


## 异常处理：OpenCode 无法启动（跨架构恢复）

### 触发条件

满足以下条件时，认为可能发生了跨架构恢复：

- 源机器与当前机器 CPU 架构不同（如 x86 与 ARM）；
- OpenCode 启动失败，或提示二进制/原生模块加载失败。

### 处理方式

调用 `exec` 工具执行以下命令，并设置：

- `timeout: 0`
- 不使用后台执行（`background: false`）

命令：

```bash
cd /home/snadbox/node_modules/opencode-ai && node postinstall.mjs
```

执行完成上述命令之后，需要执行重启保证安装生效，重启之前需告知用户即将重启保证修复生效，请重启成功之后再次尝试任务执行，重启命令如下：

```bash
python3 -m supervisor.supervisorctl restart openclaw-gateway
```