# Evolution Proposal: USER.md 固化小艺Work 版本分层

- Created-At: 2026-09-24 23:46
- Target-File: USER.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 小艺Work 对应版本 26.9.1、OpenClaw 运行时 2026.6.6、端侧承载壳小艺APP 11.7.8.301 三层版本号易混淆。
- 本次会话先误判"小艺Work=独立应用"、又误否定"小艺Work 对应 26.9.1"，经俞哥纠正后才理清版本分层。

## Evidence
- session_status: OpenClaw 2026.6.6；openclaw.json lastTouchedVersion 2026.6.6；最新可用 2026.9.5。
- 用户确认：小艺Work 对应版本 26.9.1；端侧小艺APP 11.7.8.301、Rom 26。

## Conflict Points
- USER.md 手写区现无版本分层描述（L12 已有身份/承载壳关系，版本分层为新增补充），无冲突。

## Plan
1. 在 USER.md 手写区「核心身份与基础环境」追加版本分层条目。
2. 内容：小艺Work（系统整体）= 26.9.1；OpenClaw（底层运行时内核）= 2026.6.6（最新 2026.9.5 待升级）；端侧承载壳小艺APP = 11.7.8.301（Rom 26）；三层版本号不同、层级不同不冲突。
