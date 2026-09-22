# Evolution Proposal: cron delivery target 00000000 not always fail

- Created-At: 2026-09-22 06:17
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- 修正一条会被错误复用的旧结论：后台 cron 会话投递 `00000000` 并非必失败。

## Evidence
- 2026-09-21 实测后台 cron 解析不出 00000000（ALS miss），自动回退 0380ff。
- 2026-09-22 01:00/05:00 实测后台 cron 会话 to=00000000 → resolved.ok=true、resolved.to=00000000、delivered=true（engine-init 与 daily-maintenance 均成功），未回退。
- 三任务 sessionTarget 已从 isolated 改成固定命名会话 session:xxx（engine-init / daily-maint / sandbox-weekly-cleanup），改时同传 delivery 防覆盖。

## Conflict Points
- TOOLS.md 强7「修正」+「语义修正」段（约 line 162/168/170）断言"后台 cron 解析不出 00000000、必回退 0380ff"。本次实测与其冲突，需更新为"以每次 resolved.to 实测为准"，并标注 09-22 反例。

## Plan
1. 在 TOOLS.md 强7「投递目标建议」段补充 09-22 反例：后台 cron 用 to=00000000 本次解析成功（resolved.ok=true、delivered=true），证明"00000000 后台必回退"结论不成立——端侧 target 随上下文演化，结论应以每次实测 resolved.to 为准，能用 00000000 就保留、失灵再切 0380ff。
2. 在「强制要求6」段补充落地记录：存量三任务 09-22 已改为固定命名会话，改时同传 delivery 防覆盖。
