# Evolution Proposal: 回答技能/配置类问题前先查 TOOLS.md

- Created-At: 2026-07-06 09:58
- Target-File: AGENTS.md
- Trigger-Type: explicit-instruction

## Why This Matters

连续两次（channel 配置、seedream-image-gen 通道数量）我凭记忆回答出错，但数据实际已在 TOOLS.md 中有明确定义。核心问题不是缺文档，是回答前没有去确认。

## Evidence

- 我回答 seedream-image-gen 通道配置时凭记忆说成"双通道"，实际 TOOLS.md 里明确写着三通道
- 用户指出错误后，我检查 TOOLS.md 发现数据已存在
- 用户坚持"那也是需要记住，固化进化的"

## Conflict Points

AGENTS.md 已有 "Skills provide your tools. When you need one, check its SKILL.md" （第 125 行），但措辞侧重"使用工具时"，没有明确覆盖"回答关于技能/工具/配置的提问前先查文档确认"这个场景。新规则不冲突，是补充强化。

## Plan

在 AGENTS.md 的适当位置（比如"Every Session"节或"External vs Internal"节附近）追加一条规则：

回答涉及技能能力、通道配置、系统参数、工具使用方式等已经文档化的事实时，必须先查阅 TOOLS.md（或相关 SKILL.md）确认后再回答，不得凭记忆作答。
