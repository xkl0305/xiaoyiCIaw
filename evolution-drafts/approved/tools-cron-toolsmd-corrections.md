# 进化提案：TOOLS.md cron 相关内容修正

- **状态**：✅ approved（2026-09-23 用户确认）
- **进化项**：TOOLS.md cron 相关内容的修正与沉淀
- **修改文件**：`TOOLS.md`

## 经验规则

1. **新增「推荐做法（投递组合）」**：cron 投递到当前对话窗口的正确组合 = `sessionTarget=isolated` + `delivery.mode=announce` + `delivery.to=00000000`。任务内**禁用** message 工具手动投递（isolated 后台会话会被 cron 框架吞成 `cron-swallowed-` 占位符，到不了用户）；不要用固定 `session:xxx` 或真实 chatId（假成功、用户收不到）。
2. **修正「Cron Update 同传 Patch 防覆盖」**：改 cron 用 `action=update`/`edit` 时必须一次带全相关字段（`sessionTarget` + `delivery` 一起传）防覆盖；正确目标为 `isolated + to=00000000`。
3. **标注旧结论推翻**：09-21 曾判"固定命名会话 `session:` + `delivery.to=0380ff` 为最优"——已被 **2026-09-23 实测推翻**（0380ff 与固定 session 均假成功、用户收不到），正确组合改为 **`isolated` + announce + `to=00000000`**。

## 落盘位置

- `TOOLS.md` 第 144 行（推荐做法）、第 505 行（防覆盖规则 2 措辞）、第 508 行（09-21 结论标注推翻）
- `TOOLS.md` 第 659 行新增完整段落「cron 定时任务主动投递到当前对话窗口的正确配置」
- 备份：`TOOLS.md.bak-20260923-070955`、`...-071734`、`...-072149`

## 说明

上一轮针对 497-506 段补发"09-23 推翻标注"的 edit 因文本已是新版而未生效、无实际改动，均以本提案确认的实际落盘内容为准。
