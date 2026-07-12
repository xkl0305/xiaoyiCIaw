# Evolution Proposal: maintenance-trigger-dream-consolidation

- Created-At: 2026-07-12 07:40
- Target-File: MEMORY.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 每日维护脚本扫描到新记忆后只写了"可梦境固化"的note，但从未实际触发dream_trigger_now，导致用户误以为固化未完成
- 用户明确指出现状不合理，要求修复

## Evidence
- 用户指出："为什么不写梦境固化完成"
- 代码显示：llm_dream步骤status="done"但note="扫描到XX条新记忆，可梦境固化"，仅做了扫描未触发实际固化
- 用户确认"需要"修复

## Conflict Points
- None

## Plan
1. 修改 `scripts/_archived/daily_maintenance.py` 中 `dream_consolidation()` 函数，在扫描到新记忆大于3条时调用 `dream_trigger_now()` 异步触发实际梦境固化
2. 将note从"可梦境固化"改为"已触发梦境固化"
3. 在MEMORY.md中记录此修复作为技术决策
