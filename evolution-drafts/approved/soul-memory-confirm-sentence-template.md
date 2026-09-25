# Evolution Proposal: 确认句模板去掉多余《》占位

- Created-At: 2026-09-24 23:52
- Target-File: SOUL.md + MEMORY.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 今天固化确认句项时，门禁模板写成"进化内容已写入《文件》"，但与历史实际用法"进化内容已写入 SOUL.md/TOOLS.md"（直接写具体文件名、无《》）不一致。
- 用户指出《》为画蛇添足，要求去。

## Evidence
- 历史确认句（MEMORY.md.bak-20260923/20260924）："进化内容已写入 SOUL.md""写入 TOOLS.md"——无《》。
- 当前 SOUL.md L58 / MEMORY.md L193 标准模板含《文件》。

## Conflict Points
- 无，纯修正今天引入的不一致占位写法。

## Plan
1. SOUL.md L58：`进化内容已写入《文件》` → `进化内容已写入 <文件名>`，并注明 <文件名> 替换为实际落盘文件。
2. MEMORY.md L193：同上。
3. 两处同步，保持门禁模板一致。
