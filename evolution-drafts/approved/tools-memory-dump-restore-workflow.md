# Evolution Proposal: memory_dump 归档内容恢复/清理标准流程

- Created-At: 2026-09-22 21:54
- Target-File: TOOLS.md
- Trigger-Type: user-request（俞哥确认固化该可复用流程）

## Why This Matters
- 本次从 memory_dump 恢复六章合并版的过程暴露了"归档内容恢复"的可复用方法论（先盘点分级、对照现有、列清单二次确认、按定位落文件），可避免未来重复踩坑（整包回灌退回臃肿、重复恢复、落错文件）。

## Evidence
- 实战：回填六章合并版前先盘点转储标题、区分三段式结构、对比 MEMORY.md 现有覆盖、向用户列删除/保留清单、确认后写入，全程带备份。
- 与既有「MEMORY.md 深度瘦身标准流程」为互补：瘦身负责"怎么压缩归档"，本流程负责"怎么从归档恢复/清理"。

## Conflict Points
- None（新增条目，与既有流程互补，不冲突）。

## Plan
- 在 TOOLS.md 追加「memory_dump 归档内容恢复/清理标准流程」条目：先盘点分级 → 三分类 → 对比现有覆盖 → 精读列清单二次确认 → 按定位落文件，附备份/结构验证纪律。
