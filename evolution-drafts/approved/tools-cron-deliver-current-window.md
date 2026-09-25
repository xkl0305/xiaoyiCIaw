# 进化提案：cron 定时任务主动投递到"当前对话窗口"的正确配置

- **状态**：✅ approved（2026-09-23 用户确认）
- **进化项**：cron 定时任务主动投递到当前对话窗口的正确配置组合
- **修改文件**：`TOOLS.md`

## 经验规则

要让 cron 报告稳定落到用户当前对话窗口，必须是三件套：

1. `sessionTarget = "isolated"`（每次 run 新建临时会话；**不可用** `session:xxx` 固定持久会话——announce 会落在任务会话而非主会话）
2. `delivery.mode = "announce"`（系统自动投递 final 回复；任务内**不要**用 message 工具手动投——isolated cron 后台会话里 message 工具投递会被 cron 框架吞掉，永远返回 `cron-swallowed-` 占位符，到不了用户）
3. `delivery.to = "00000000"`（当前对话窗口标识 = direct 会话的 to；会 resolved 到真实线程如 `00000000::<uuid>&n&xxxx&0`，落在用户当前查看的对话窗口）

**核心难点：** `delivered=true` 不一定是真到用户端，存在多种假成功（真实 chatId、固定 session、任务内 message 工具投递均假成功或失败）。

**判定链路：** 查 `cron get` 的 `resolved.to`——若 resolved 到 `00000000::<当前窗口线程>`（如 `45b9d4ba...`），即已进当前会话；配合用户端实际确认（请用户翻窗口历史确认是否收到 cron 自动投递的报告，注意区分 announce 自动投 vs message 手动投）。

## 对比试验结论（实测）

| 配置 | 结果 |
|------|------|
| to=真实 chatId（0380ff...） | delivered=true 假成功，用户收不到 |
| session:xxx 固定会话 + announce + to=00000000 | 用户收不到 |
| isolated + 任务内 message 工具投 default | cron-swallowed 占位，被吞 |
| **isolated + announce + to=00000000** | ✅ 正确，落到用户当前窗口 |

## 落盘

- 已写入 `TOOLS.md` 新增一节「cron 定时任务主动投递到当前对话窗口的正确配置」
- 备份：`TOOLS.md.bak-20260923-070955`
