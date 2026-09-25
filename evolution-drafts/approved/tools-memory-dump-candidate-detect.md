# Evolution Proposal: memory_dump 候选恢复检测工具固化

- Created-At: 2026-09-22 22:21
- Target-File: TOOLS.md + tools/check_memory_dump.py
- Trigger-Type: user-confirmed（俞哥判定该工具"可用、有用"，要求固化进化）

## Why This Matters
- 手动盘点 memory_dump 与正式区的差异耗时且易漏。此脚本自动比对"转储中的关键正式区块 vs 正式文件"，标出"转储有、正式区缺失"的候选，将体检/恢复流程的差异检测环节自动化（判断/落笔仍人工）。

## Evidence
- 脚本 /tmp/check_memory_dump.py 实测通过：正确标出「记忆引擎切换记录」为候选待恢复、其余已存在区块不误报；已据此恢复该记录到 MEMORY.md。

## Conflict Points
- None（新增工具 + 体检补充项；与「memory_dump 恢复/清理流程」「MEMORY.md 体检清单」互补，脚本是它们的差异检测手段）。

## Plan
1. 将脚本固化到 `tools/check_memory_dump.py`（WORKSPACE/tools 目录）。
2. 在 TOOLS.md 补充一条「memory_dump 候选恢复检测工具」：说明脚本用途、运行命令、输出解读（⚠️候选=机械差异，是否恢复仍人工判断），并与既有「体检清单」「恢复/清理流程」衔接为"差异检测环节"。
