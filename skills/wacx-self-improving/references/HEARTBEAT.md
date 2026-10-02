## 自我进化检查

- 读取 `./skills/wacx-self-improving/heartbeat-rules.md`
- 用 `~/self-improving/heartbeat-state.md` 记录上次运行标记与操作备注
- 若自上次已复核的变更以来 `~/self-improving/` 内无任何文件变化，返回 `HEARTBEAT_OK`
