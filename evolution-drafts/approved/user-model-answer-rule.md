# Evolution Proposal: 答当前模型正确口径

- Created-At: 2026-10-27 19:16
- Target-File: USER.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 用户连续追问"当前模型"，发现单报一个值不准确。需固化正确口径：Auto-Model 自动路由 + 实际落点 DeepSeek V4 系，避免只报单一模型误导。

## Evidence
- 用户多次问"现在的模型/当前模型/你确定吗"，要求"记住固化进化一下"。
- 配置 primary=xiaoyiprovider/Auto-Model（自动路由）；session_status 实际=LLM_DeepSeekV4_Think；runtime 标识=DeepSeek_V4.1_Flash_VE；统属 DeepSeek V4 系。

## Conflict Points
- 无。

## Plan
在 USER.md 系统事实/环境区（第1节）追加「答当前模型口径」条目。
