# Evolution Proposal (approved): 新建 cron 默认投递标准（0380ff + default 兜底）

- Created-At: 2026-09-21 03:23
- Approved-At: 2026-09-21 03:23
- Target-File: TOOLS.md (强制要求7) + 三个 cron 任务配置
- Trigger-Type: explicit-instruction

## Fix
- 原规则：新建 cron 默认投 `to=00000000`（当前对话窗口）→ 实测后台解析不出、必回退，名存实亡
- 新标准：后台/新建 cron 主投递 `to=0380ff5fd8f64722a93e28596a6cb9a7`（后台可解析）+ `failureDestination=default`（推送兜底，通知栏必达）
- `00000000` 仅限实时对话

## Applied
- TOOLS.md 强制要求7 已更新为 2026-09-21 修正版（含兜底标配 + 推荐配置模板）
- 三个 cron 已改：crusheart-engine-init / crusheart-daily-maintenance / 沙箱清理-每周检查
  → delivery: to=0380ff..., failureDestination: to=default
