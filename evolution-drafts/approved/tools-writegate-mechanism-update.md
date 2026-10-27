# Evolution Proposal: playbook 令牌流程对齐 write-gate 插件消息确认机制

- Created-At: 2026-10-28 07:43
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- TOOLS.md「自进化固化操作全流程 Playbook」仍写旧令牌流程(.write-gate-allow.json),与新机制(write-gate 插件内存态+俞哥真实确认消息,992行已记录)矛盾,导致按旧剧本执行被反复拦截。

## Evidence
- 2026-10-28 实操多次被 write-gate 拦;读插件源码确认:令牌文件已废弃,改 pending/granted + message_received 真实用户确认驱动。

## Conflict Points
- 修 playbook 旧令牌步骤与其 992 行新机制一致,消除矛盾,不覆盖新机制条目。

## Plan
修正 playbook step2/step5/关键纪律为「展示请求→俞哥真实确认消息→写入」,删除令牌文件步骤。
