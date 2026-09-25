# Evolution Proposal: 修改含记忆标记块文件前的边界预检

- Created-At: 2026-09-24 23:27
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- USER.md / MEMORY.md 含 Celia 记忆系统自动管理的 `CELIA_MEMORY_OVERVIEW/SCENES_BEGIN...END` 禁改块，手动编辑其中内容会被记忆系统重写覆盖、且违反既有"标记块禁改"纪律。
- 本次对"小艺Claw残留是否要改"做判断时，先核对标记边界发现 9 处目标行全部落在禁改块内（USER.md L56-126、MEMORY.md L10138-10160），及时收手，避免白改 + 违规。
- 真正该统一的正式规则文件（AGENTS/SOUL/TOOLS）已全部是"小艺Work"，无需手改；这印证"判断残留前先分辨正式规则文本 vs 记忆系统快照"。

## Evidence
- 目标行 USER.md L59/83/87/96/114/122/125 全在 OVERVIEW 块(L56-126)内；MEMORY.md L10152/10158 全在 SCENES 块(L10138-10160)内。
- AGENTS(2)/SOUL(1)/TOOLS(10) 已无"小艺Claw"残留。

## Conflict Points
- 与既有"MEMORY.md 标记块禁改"纪律为延伸补充，非冲突。

## Plan
1. 在 TOOLS.md 追加一条经验：修改 USER.md/MEMORY.md（或其他含 `CELIA_MEMORY_*_BEGIN/END` 标记的文件）前，先 `grep -n "CELIA_MEMORY_"` 核对标记边界，确认待改行不在禁改块内；命中则不做手动编辑，交由记忆系统刷新。
2. 追加到 TOOLS.md 记忆管理相关段落。
