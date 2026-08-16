# Evolution Proposal: 技能不做自动归档/活跃分类

- Created-At: 2026-08-16 07:45
- Target-File: MEMORY.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 技能被维护脚本按"SKILL.md 超过90天未用"自动搬到 .archive，产生"活跃/归档/过期"分类，造成报告数字混乱（312 虚高、163 活跃等），用户多次困惑。
- 用户明确要求技能统一留在 skills/，不搞这些分类。

## Evidence
- 用户原话："技能就不要搞这种活跃不活跃的了"
- 用户原话："那就长期，记住固化进化一下"
- 已修改 `scripts/_archived/daily_maintenance.py` 的 `skill_curator_maintenance()`，移除 shutil.move 自动归档逻辑，技能全部留在 skills/。

## Conflict Points
- None

## Plan
1. 在 MEMORY.md 记录长期偏好：技能统一保留在 skills/ 目录，不做自动归档/活跃/过期分类。
2. 说明维护脚本已关闭自动归档机制（2026-08-16 已改），以后维护报告技能部分只显示全部活跃。
