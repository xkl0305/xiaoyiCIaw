# Evolution Proposal: galaxyos worker 通信故障排查经验

- Created-At: 2026-08-29 13:00
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- galaxyos 插件 claw_health/claw_events 长期故障，最终定位并修复了「worker 通信模式不匹配」「方法注册缺失」「DAG 版本 API 差异」三个独立根因。这套排查手法对未来排查类似插件/worker 集成故障有直接复用价值，避免再次走弯路。

## Evidence
- claw_health/claw_events 长期 `Work call timeout`，超过 5 次 tool call + 多次失败重试后才成功
- 根因1（核心）：index.js spawn worker 设 `WORKER_UDS:'1'` → worker 主线程走 UDS 模式只 `sys.stdin.read()` 干等、不解析 stdin 命令；但 index.js 却用 `proc.stdin` 发命令 → 通道不匹配 → 所有命令无人处理 → 全 timeout。修复：`WORKER_UDS` 改空，worker 走 stdin 降级循环（for sys.stdin 解析命令），匹配 index.js 的 stdin RPC。
- 根因2：worker 方法表未注册 `events` 方法，claw_events 报 `unknown method`。修复：在 `_init_methods` 注册 `_rpc_events`，从 temporal_kg（`~/.openclaw/workspace/temporal_kg.db` 的 temporal_edges 表）查询事件。
- 根因3：health() 调 `get_all_session_keys()`，官方 v8 的 `DAGIntegration` 已无此方法 → 抛 AttributeError 被 except → 误报 `dag_unavailable`。修复：health 内层 try 兼容（实例化成功即视为可用）。
- 定位手法：在 worker `main()` 加 `faulthandler.dump_traceback_later(20, repeat=True)`，worker 处理命令卡住时自动 dump 所有线程栈 → 看到主线程卡在 `sys.stdin.read()`（没进命令循环），一击定位根因。

## Conflict Points
- None

## Plan
1. 在 `TOOLS.md` 的「Git push 远端归属检查」之后、文件末尾末尾追加新小节「galaxyos 插件 worker 故障排查（2026-08-29）」，包含三条核心经验 + 一条定位手法。
2. 追加文本（精简，符合 TOOLS.md 风格）：
```md
### galaxyos 插件 worker 通信故障排查（2026-08-29）

**核心：worker 报 `Work call timeout` 先看通信模式是否匹配**
- claw_health/claw_events 长期 timeout 的根因：`index.js` spawn worker 设了 `WORKER_UDS:'1'`，会让 worker 主线程走 UDS 模式只 `sys.stdin.read()` 干等、不处理 stdin 命令；但 index.js 自己却用 `proc.stdin` 发命令 → 通道不匹配 → 命令全没人处理 → 全部 timeout。
- 修复：把 spawn env 里 `WORKER_UDS:'1'` 改为空字符串，worker 走 stdin 降级循环匹配 index.js 的 stdin RPC，即恢复。
- 排查手法：给 worker `main()` 加 `faulthandler.dump_traceback_later(20, repeat=True)`，卡住时自动 dump 所有线程栈，能定位主线程卡在哪一行。
- 已知坑：worker(v1.0) 代码与官方 v8 引擎 API 不匹配——`DAGIntegration` 已无 `get_all_session_keys` 方法，health() 调用会抛错误报 `dag_unavailable`，需做兼容判断。
</md>
```
