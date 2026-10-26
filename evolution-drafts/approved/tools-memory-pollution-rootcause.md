# Evolution Proposal: MEMORY.md 污染根因与治本

- Created-At: 2026-10-27 07:20
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- MEMORY.md 反复被记忆固化引擎污染膨胀（本次到 1.19MB/2万行），仅靠清理会复发。已定位根因并完成治本（落点重定向），这套"根因→排查→瘦身→治本"方法论对未来同类记忆文件治理有长期复用价值。

## Evidence
- 用户："MEMORY.md 瘦身"、"之前是记忆系统持续往 MEMORY.md 写固化记录导致再膨胀"、"记住固化进化一下"
- 排查：grep "📝 固化"/"🧠 核心锚点" 命中 `core/engines/memory/auto_memory.py:2193/2189`；long_term_file(994行) 直指 MEMORY.md；触发为会话内 hook 而非 cron；确认 slots.memory=memory-celia 与残留引擎并存双写。
- 治本：long_term_file 重定向到 `data/auto_memory_l3.md`（994+2314 两处），grep 确认 core 无其他直接写 MEMORY.md，py_compile 通过，commit 5079660，重启生效。

## Conflict Points
- TOOLS.md 已有「长期记忆文件(MEMORY.md)健康体检(2026-09-17)」条目（讲体检清单+清理纪律），本次为**补充**污染根因与治本方案，不覆盖原条目。

## Plan
1. 在 TOOLS.md「长期记忆文件(MEMORY.md)健康体检」条目后补充子条目「MEMORY.md 污染根因与治本（2026-10-27）」。
2. 追加到 TOOLS.md 该条目末尾，不改动其他内容。
