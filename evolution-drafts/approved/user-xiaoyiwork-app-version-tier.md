# Evolution Proposal: 端侧小艺Work 应用版本 + 版本口径分层

- Created-At: 2026-09-22 09:13
- Target-File: USER.md + TOOLS.md
- Trigger-Type: explicit-instruction（用户明确纠错："端侧承载Claw的应用没有记住固化进化到你脑子里？"）

## Why This Matters
- 用户问"小艺Claw版本"时，我答成了后台 OpenClaw 引擎版本（2026.6.6），而用户指的是手机端承载小艺Claw的应用——导致层级混淆、答错对象。
- 这是稳定的用户环境事实 + 可复用的"版本口径"区分规则，值得长期记忆。

## Evidence
- 用户截图"小艺Work"升级页：显示"已是最新版本（26.9.1）"，更新亮点含 GLM-5.3/GLM-5.3-Flash、DeepSeek V4.1 Flash、全局记忆优化、长任务稳定性提升。
- 我误答后台引擎版本为"小艺Claw版本"，用户纠正。

## Conflict Points
- None（USER.md 现有"小艺APP版本11.7.7.404"为小艺语音助手APP，与"小艺Work"是不同应用；本次新增小艺Work应用条目，不冲突）。

## Plan
1. USER.md「核心身份与基础环境」新增：
   - 承载小艺Claw的端侧应用 = **小艺Work**，当前版本 **26.9.1**（升级页显示"已是最新版本"）。
   - 它与「小艺APP」是不同应用：小艺APP 版本 11.7.7.404。
2. TOOLS.md「定时任务/版本」相关区块新增口径规则：
   - 回答"小艺Claw版本/小艺版本"必须先分清层级：**端侧应用（小艺Work，26.9.1）** vs **后台 OpenClaw 引擎（2026.6.6，可用 2026.9.5）**，避免只答后台版本导致混淆。
