# Heartbeat 规则

用 heartbeat 保持 `~/self-improving/` 整洁，既不制造折腾也不丢失数据。

## 事实来源

让工作区的 `HEARTBEAT.md` 片段保持精简。
把本文件视为自我进化 heartbeat 行为的稳定契约。
只把可变的运行态存入 `~/self-improving/heartbeat-state.md`。

## 每次 Heartbeat 开始时

1. 确保 `~/self-improving/heartbeat-state.md` 存在。
2. 立即以 ISO 8601 写入 `last_heartbeat_started_at`。
3. 读取上次的 `last_reviewed_change_at`。
4. 扫描 `~/self-improving/` 中该时刻之后变更的文件，排除 `heartbeat-state.md` 自身。

## 若没有任何变更

- 设置 `last_heartbeat_result: HEARTBEAT_OK`
- 若你保留操作日志，追加一条简短的"无实质变更"备注
- 返回 `HEARTBEAT_OK`

## 若发生了变化

只做保守的组织：

- 若计数或文件引用漂移，刷新 `index.md`
- 通过合并重复或摘要重复条目来压缩过大文件
- 仅当目标明确无误时，把明显放错位置的笔记移到正确命名空间
- 精确保留已确认规则与明确纠正
- 只在干净复核完变更文件后，才更新 `last_reviewed_change_at`

## 安全规则

- 多数 heartbeat 运行应当什么都不做
- 优先追加、摘要或索引修复，而非大改写
- 绝不删除数据、清空文件或覆盖不确定的文本
- 绝不重组 `~/self-improving/` 之外的文件
- 若范围模糊，保留文件不动，并记录一条建议的后续动作

## 状态字段

让 `~/self-improving/heartbeat-state.md` 保持简单：

- `last_heartbeat_started_at`
- `last_reviewed_change_at`
- `last_heartbeat_result`
- `last_actions`

## 行为标准

Heartbeat 的存在是为了让记忆系统整洁且可信。
若没有明确违反任何规则，就什么都不做。
