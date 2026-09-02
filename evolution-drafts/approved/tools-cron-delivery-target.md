# cron 定时任务投递目标排查（tools）

- **日期**: 2026-08-31
- **来源**: 用户反馈定时任务"显示投递成功但对话框看不到"
- **适用**: 所有定时任务（含后续新增）通用

## 经验规则

cron 任务 announce 投递到 xiaoyi-channel 时，`to` 必须是用户当前对话的会话目标 id（`session_status` 的 `deliveryContext.to`），不能填 `default`。否则结果投进另一个会话（`direct:default`），系统标记 delivered 成功但用户当前对话框收不到。

## 排查步骤

1. `session_status` 查当前会话 `deliveryContext.to`
2. `cron list` 对比各 job 的 `delivery.to`
3. 不一致即根因；`cron update <jobId>` 改 `patch.delivery.to` 为当前会话 id
4. `cron run <jobId> runMode=force` 手动触发验证
5. 三个定时任务（每日维护/引擎初始化/沙箱清理）统一绑定当前会话

## 落地

已写入 TOOLS.md「定时任务 (Cron) 配置规则」强制要求4。
