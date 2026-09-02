# Evolution Proposal: skill count statistical method

- Created-At: 2026-09-03 07:36
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 报告"技能数量"时用了错误口径（SKILL.md 文件数 474），与维护脚本（SkillScanner 顶层技能目录数 330）冲突，导致对不上、误导用户。
- 技能数是跨会话常被问的文件级数据，口径必须统一，否则每次都会重新踩坑。

## Evidence
- 用户原话："474个技能，之前不是329吗"（直接指出数量对不上）
- 坑点：`find skills -name "SKILL.md" | wc -l` = 474（含嵌套子 SKILL.md，如 xiaoyi-health 下有多个 SKILL.md），误当技能数；权威口径是 `SkillScanner().scan().get_stats()['total_skills']` = 330（顶层技能目录，排除 .archive），维护脚本 `daily_maintenance.py` 同款。
- 正确：330（当前）= 上次维护 329 + 1（新增 wind-stock-mcp），仓库同步后同为 330，两边一致。

## Conflict Points
- None

## Plan
1. 在 TOOLS.md 新增一条规则：报告"技能数量"一律按"顶层技能目录"口径（SkillScanner 同款，当前 330 个），**禁止**用 SKILL.md 文件数（会含嵌套子 SKILL.md、偏大，误导用户）。
2. 插入到 TOOLS.md 合适位置（如新增小节"技能数量统计口径"），内容精简一句规则 + 一句口径对比。
