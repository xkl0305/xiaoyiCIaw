# Evolution Proposal: qiqi-persona-display-order

- Created-At: 2026-07-09 16:51
- Target-File: AGENTS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 用户反复纠正"琪琪人格内容"的展示顺序——IDENTITY.md应在前，SOUL.md应在后
- 没有明确规则时我每次随机排序，导致反复踩坑
- 用户明确要求"需不需要固化进化一下"

## Evidence
- 用户问"为什么 IDENTITY.md 在后面"（2026-07-09 16:50）
- 用户曾多次纠正展示格式：精简版→原文→代码块→顺序
- AGENTS.md 第317行已有"输出规范"的占位，但没有具体规则

## Conflict Points
- AGENTS.md 第317行提到「回答'琪琪人格内容'的完整结构」但未定义具体顺序和格式
- SOUL.md 第175行"连续性"提到文件顺序但不涉及展示顺序

## Plan
1. 在 AGENTS.md §输出规范（第317行附近）追加具体规则
2. 规则内容：当用户问"琪琪人格内容"时，IDENTITY.md内容在前，SOUL.md内容在后，直接贴文件原文不作精简
