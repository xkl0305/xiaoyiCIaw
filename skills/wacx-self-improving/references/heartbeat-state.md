# Heartbeat 状态模板

把本文件作为 `~/self-improving/heartbeat-state.md` 的基线。
它只存储轻量的运行标记与维护备注。

```markdown
# 自我进化 Heartbeat 状态

last_heartbeat_started_at: never
last_reviewed_change_at: never
last_heartbeat_result: never

## 最近动作
- 暂无
```

## 规则

- 每次 heartbeat 开始时更新 `last_heartbeat_started_at`
- 只在干净复核完变更文件后，才更新 `last_reviewed_change_at`
- 保持 `last_actions` 简短且基于事实
- 绝不让本文件变成又一个记忆日志
