# Evolution Proposal: default 是推送标记，区别于会话ID

- Created-At: 2026-09-20 14:14
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- `default` 与 `00000000`/`0380ff` 本质不同，之前只模糊说"都能投递"，未解释差异
- 源码确认：`default` 走 push 通知通道（通知栏），会话ID 走 WebSocket 会话通道

## Evidence
- 用户重复追问"default 和 00000000 不一样吗"，触发源码核查
- outbound.js 源码：`DEFAULT_PUSH_MARKER = "default"`，无目标时用此标记；sendText 里 `if(to===marker) actualTo=config.defaultSessionId`，走 XYPushService 推送（通知栏广播到所有 pushId）
- 会话ID（00000000/0380ff）走 WebSocket 会话通道，落到具体会话内

## Conflict Points
- TOOLS.md"投递目标建议"已提"default 作投递目标也能落主对话框"——本次补充其本质（推送标记/推送通道），属补充非冲突。

## Plan
1. 在 TOOLS.md"投递目标建议"段落后追加一条：
   - `default` 是 outbound 层的**推送标记**（`DEFAULT_PUSH_MARKER`），非端侧会话ID；走 push 通知通道，映射 `config.defaultSessionId`，广播到所有 pushId（通知栏推送）
   - `00000000`/`0380ff...` 是**端侧会话ID**，走 WebSocket 会话通道，落到具体会话内（会话内回复）
   - 三者通道/层级不同：default=推送层，会话ID=会话层。投到"会话内"用会话ID，投"通知栏"用 default。
