# Evolution Proposal: supervisord 一次性脚本需设 startsecs=0

- Created-At: 2026-08-09 16:29
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 排查 `watch_paired` 反复 FATAL 噪音时，根因是 supervisord 把一次性(one-shot)脚本当常驻服务管理，导致秒退被误判为"启动失败"反复重启。
- 该模式可复用：凡是"跑一遍就退出"的程序配进 supervisord，都可能踩此坑。
- 手动实测确认修复有效。

## Evidence
- 用户原话：「改」「记住固化进化一下」
- 工具踩坑：supervisord.conf 中 `watch_paired`（`/opt/bin/watch_paired.py`，one-shot 补权限脚本）默认 `startsecs=2`，脚本 0.5s 内正常退出，未撑过 2s 被判"启动失败"（exit 0; not expected），supervisord 反复拉起，5 次后进入 FATAL。
- 修复：`startsecs=2` → `startsecs=0`，更新后脚本 `spawned → RUNNING → exited (exit status 0; expected)`，不再 FATAL。gateway 未重启，会话未中断。

## Conflict Points
- None

## Plan
1. 在 TOOLS.md「OpenClaw 操作约束」小节下追加一条经验。
2. 追加文本：
```
### supervisord 一次性脚本配置坑点（2026-08-09）

**经验：** 用 supervisord 管理"跑一遍就退出"(one-shot)的程序（如 `/opt/bin/watch_paired.py` 这种补权限脚本）时，必须把 `startsecs` 设为 `0`。否则脚本秒退没撑过默认的 `startsecs=2`，会被误判为"启动失败"(exit 0; not expected)，supervisord 反复拉起，多次后进入 FATAL 状态刷噪音。

**修复：**
```ini
[program:watch_paired]
autorestart=false
startsecs=0        ; 一次性脚本必须设 0，正常退出即算完成
```

**生效命令（只重载受影响程序，不重启 gateway）：**
```bash
python3 -m supervisor.supervisorctl -c /home/sandbox/supervisord.conf update watch_paired
```

**验证：** 状态应为 EXITED（`exit status 0; expected`），而非反复 FATAL。改配置前先 `cp supervisord.conf supervisord.conf.bak-$(date +%Y%m%d-%H%M%S)` 备份。
```
