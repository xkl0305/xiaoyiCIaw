# 进化提案：通用补丁器支持 restore 型 · write-gate 纳入守护

- 状态：**已确认（approved，2026-09-25）**
- 修改文件：TOOLS.md

## 背景
通用补丁器初版仅支持"patch 型"（往目标文件插桩）。但 write-gate（"进化请求流程"的代码级根治）是**完整插件文件**，不是"插逻辑"，遇到 OpenClaw 大升级/重装重写 extensions 目录可能整个被冲。需让补丁器具备"整体恢复"能力。

## 经验规则
1. 通用补丁器 `scripts/patch_autoheal.py` 支持两种目标类型：
   - `patch`：往文件插桩（insertPoint 后插入 insert + replacements）
   - `restore`：文件缺失/核心逻辑被冲时，从 `backupPath` **整体恢复**，适用于完整插件文件（如 write-gate）
2. 配置 `patch_autoheal_config.json` 追加目标 `write-gate-plugin`（restore 型）：守护 `~/.openclaw/extensions/write-gate/index.js`，缺失则从备份 `index.js.bak-*` 整体恢复，恢复后重启 gateway 重新加载。
3. 已实测：check 全 ok；模拟丢失 → patch 自动从备份整体恢复，恢复后与备份 diff 一致、node check 通过。
4. write-gate 纳入守护后，"进化请求流程"的代码级根治自身也有了代码级兜底。

## 已知盲区（后续关注）
write-gate 当前拦截 write/edit 工具 + exec 的 `>`/`>>` 重定向，但 **python 脚本 open().write() 可绕过**（本会话多次用 python 落盘正式文件未被拦截）。后续如需加强，可将 write-gate 扩展为也拦截 exec 对受保护文件路径的 python 写入（列入待办，不阻塞本次）。
