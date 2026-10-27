# 提案：write-gate 代码级根治——确认判定权移交插件（2026-10-27）

- **状态**：approved
- **进化项**：固化 write-gate 从"agent 可自建 JSON 令牌"改为"用户真实确认词驱动一次性放行"
- **修改文件**：TOOLS.md（新增「write-gate 代码级根治」记录，标注流程变化）
- **代码**：`~/.openclaw/extensions/write-gate/index.js`（备份 `index.js.bak-p0-confirm-20261027-231200`）
- **核心**：on("message_received") 识别俞哥确认词并排除 agent 来源 → 授予受保护文件一次性放行(10min)；停用 agent 可自建的 .write-gate-allow.json
- **验证**：拦截/放行/一次性 三路径端到端实测全通过
- **流程变化**：建令牌步骤废弃，改为「展示请求 → 俞哥发确认词 → 写入」
