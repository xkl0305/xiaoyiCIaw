# Evolution Proposal: cron update 同传 patch 防覆盖

- Created-At: 2026-09-21 07:08
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 改 cron 配置时只传单个字段（如只传 delivery），会导致未传字段被静默重置回默认值（实测 sessionTarget 从 current 变回 isolated），极易造成配置被悄悄破坏、难排查。
- 固化后可避免后续同类踩坑。

## Evidence
- 用户要求三个定时任务 sessionTarget 改 current + delivery.to 改 00000000。
- 中途只传 delivery patch → 返回中三处 sessionTarget 全被重置为 isolated，需二次同传修复。
- 用户认可该经验值得固化（"记一下"）。

## Conflict Points
- None（TOOLS.md 现有 cron 规则无冲突，新增一条独立经验条目）

## Plan
1. 内容：
   - 坑：cron update/edit 只传单字段 → 未传字段被重置回默认（实测 sessionTarget: current→isolated）。
   - 规则：必须一次同时带上所有相关字段（sessionTarget + delivery 一起传）；改后核对返回的 sessionTarget 是否符合预期，被重置立即同传修复；改前先 cp -r ~/.openclaw/cron 备份。
2. 写入位置：TOOLS.md 的「定时任务 (Cron) 配置规则」区块末尾追加章节。
