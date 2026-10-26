# Evolution Proposal: 流式 partial 发送收尾归一补丁固化

- Created-At: 2026-10-25 06:56
- Target-File: TOOLS.md
- Trigger-Type: user-confirmed（俞哥指出"流式发送固化流程没了"，确认补固化）

## Why This Matters
- 09-22 固化的「代码级兜底」只记了 final 帧归一，今天为流式 partial 帧加的收尾归一补丁未独立固化记录，导致"流式发送"修复史缺失。补记完整修复链（final→流式 partial→formatter 源头），供未来排错溯源。

## Evidence
- 10-25 补 reply-dispatcher partial 归一（行 678-680，`text: partialText`）；最终根治在 formatter.js sendA2AResponse() 源头统一归一（覆盖流式+final 全路径）。备份：formatter.js.bak-20261025-064856、reply-dispatcher.js.bak-20261025-064230。

## Conflict Points
- None（对既有「xiaoyi-channel ❄️ 收尾代码级兜底（2026-09-22）」条目的补充完善，不冲突）。

## Plan
- 在 TOOLS.md 既有「xiaoyi-channel ❄️ 收尾代码级兜底（2026-09-22 根治）」条目后补充「· 流式 partial 归一（2026-10-25）」：说明流式 partial 帧同样 `\s*❄️\s*$` 归一（reply-dispatcher.js 行 678-680）；最终根治点在 formatter.js sendA2AResponse() 公共出口源头统一归一，覆盖流式+final 全路径；附备份文件名与重启流程。
