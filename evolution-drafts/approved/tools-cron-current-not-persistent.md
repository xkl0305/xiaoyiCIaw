# Evolution Proposal: cron current 不持久 + 投递ID实测结论

- Created-At: 2026-09-21 12:41
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 实测 `sessionTarget=current` 不持久：今早(09-21 07:04)设为 current，10:02 cron list 显示已自动回退成 isolated。文档缺失此坑，会误导后续配置。
- 端侧会话映射实测：当前会话内稳定ID唯一是 `0380ff`，更早是 `8e6fb15f...`，佐证 0380ff 亦非永久 → 三层兜底必要。

## Evidence
- 三任务设 `sessionTarget=current`+`delivery.to=00000000`，4分钟后 cron list 显示 sessionTarget 全回落 isolated（delivery.to=00000000 保留）。
- sessions_list / cron-push-map 实测：主对话框稳定地址现为 0380ff，曾为 8e6fb15f...。
- 用户确认（"确认"）采纳：固定命名会话 + 0380ff + default 兜底为最优组合。

## Conflict Points
- 与现有「强制要求6/7」「投递目标建议(170行)」同向，补充实测佐证，无逻辑冲突。

## Plan
1. 新增强制要求条目：`sessionTarget=current` 是"创建时活绑定"，不持久，job 重载/下次调度后自动回退默认 isolated，勿当持久方案；后台 cron 首选固定命名会话。
2. 投递目标建议补充：当前会话内稳定ID唯一是 0380ff，历史为 8e6fb15f...，证 0380ff 亦非永久 → 三层兜底必要。
3. 更新背景案例：current 已回落 isolated，最终结论回到「固定命名会话 + 0380ff + default」。
