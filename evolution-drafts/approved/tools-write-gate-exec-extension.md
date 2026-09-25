# 进化提案：write-gate 增加 exec 写重定向覆盖

- **状态**：✅ approved（2026-09-23 用户确认）
- **进化项**：更新 TOOLS.md「write-gate」一节，补充 exec 写重定向覆盖
- **修改文件**：`TOOLS.md`

## 经验规则

1. **覆盖范围扩展**：write-gate 守卫除工具层（`write`/`edit`/`apply_patch`/`memory_workspace`）外，新增拦截 `exec` 对受保护文件名的写重定向（`>`/`>>`），同样要求令牌，否则 block。
2. **exec 检测策略（保守）**：正则以 `(?<![<>=!-])(>>|>)\s*["']?([^"'\s;&|()\n]+)` 提取重定向目标，`>` 前排除 `<>=!-` 降误伤；纯读命令、写往非受保护目标不拦；复杂 shell（变量展开/heredoc）宁漏不误伤。
3. **验证（2026-09-23 全过）**：exec 层 ①`>` 无令牌 block ②`>>` 无令牌 block ③读命令不误伤 ④非受保护目标放行 ⑤有令牌放行+消耗。

## 落盘位置

- `TOOLS.md`「write-gate」一节：拦截范围 + 验证测试补 exec 覆盖
- 备份：`TOOLS.md.bak-20260923-094814`
- 插件备份：`extensions/write-gate/index.js.bak-20260923-094516`

## 关联

配套 `tools-write-gate-plugin.md`（write-gate 初始实现），本提案为其 exec 扩展。
