# Evolution Proposal: xiaoyi-channel 长消息截断规避纪律

- Created-At: 2026-09-22 16:30
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- 多次出现 xiaoyi-channel 长消息被截断（含用户消息与助手消息），影响信息完整传递。

## Evidence
- 长回复+大表格+多段落 → 端侧丢尾（"任务归档"回复在表格处截断）。
- 用户消息偶发截断（输入发送中途断开）。
- 后台 cron 长文本投递有丢失风险（含 cron-swallowed- 假成功）。

## Conflict Points
- None

## Plan
- 在 TOOLS.md 末尾新增「xiaoyi-channel 长消息截断规避纪律」小节。
