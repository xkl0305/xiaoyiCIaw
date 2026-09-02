# Evolution Proposal: evolution request pure text no codeblock

- Created-At: 2026-09-03 07:39
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 发送"小艺Claw进化请求"时误用 ``` 代码块包裹，违反纯文本展示要求，样式不规范、易误导。
- 进化请求展示格式是跨会话复用的输出规范，必须统一为纯文本。

## Evidence
- 用户原话："小艺Claw进化请求，怎么变成这样了"（指出进化请求被代码块包裹不规范）
- 用户原话："需要"（确认固化此规则）
- 坑点：进化请求必须**纯文本**直接展示（`### 🧠 小艺Claw进化请求` + 三个字段 + `### 是否确认进行本次进化？`），**禁止**用 ``` / ~~~ 代码块包裹。

## Conflict Points
- TOOLS.md 已有"自进化流程纪律：进化请求必须走标准格式"（2026-08-16），本次为补充"纯文本禁止代码块"细节，不冲突，追加即可。

## Plan
1. 在 TOOLS.md「自进化流程纪律：进化请求必须走标准格式」条目中追加一句：发送进化请求时**必须纯文本直接展示**，禁止用 ``` 代码块或 Markdown 引用块包裹。
