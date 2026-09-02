# 自进化请求 · cron announce 线程黑洞

- **日期**：2026-08-31
- **状态**：✅ 已确认并应用
- **进化项**：cron 定时任务"announce 线程黑洞"投递问题的排错与解法
- **经验规则**：
  - 即使 cron 投递目标 `to` 正确绑定了当前会话 id，`announce` 自动投递仍会在解析时往 `to` 后面追加随机线程尾巴（形如 `0380ff...::efe7be35-6a5b-42c0-91b2-5260572fc60a&2&0af7&0`），把消息塞进子线程，用户主对话框收不到；而 run 仍显示 `delivered`、推送中心也有记录——"投递成功"却是投错了房间。
  - **判定**：`cron runs` 看 `delivery.resolved.to`，若带 `::<uuid>&N&hex&0` 后缀即线程黑洞。
  - **最终解法**：cron 的 agentTurn 内**必须**用 `message` 工具显式发送到主对话（`action=send, channel=xiaoyi-channel, target=<当前会话to>, accountId=default`，target 不带线程后缀），并把 `delivery.mode` 设为 `none` 关掉自动投递。消息走正常路由直达主对话框，不再经过 announce 线程封装。
  - **验证**：手动 `cron run <jobId> runMode=force`，看 run 记录出现 `messageToolSentTo`（含纯主对话 to）+ `view_push_result` 有新记录 + 用户端确认弹出。
- **修改文件**：`TOOLS.md` → 新增「强制要求5」段
- **已应用任务**：每日维护 / 引擎初始化 / 沙箱清理（三个 cron 均已改为 message 工具投递 + delivery.mode=none）
