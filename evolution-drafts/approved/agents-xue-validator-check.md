# Evolution Proposal: ❄️ 收尾签名预检查绑定到消息验证流程

- Created-At: 2026-07-04 05:52
- Target-File: AGENTS.md
- Trigger-Type: explicit-instruction (repeated 10 times)

## Why This Matters
- 连续10次失败，SOUL.md、AGENTS.md、MEMORY.md 三处规则均未起到约束作用
- 唯一每次实际执行的是 execution-validator 的消息验证流程（validate-message 前拦截）
- 需要把 ❄️ 检查嵌入到这个不可跳过的流程中

## Evidence
- 10次用户指正，跨越5轮进化提案（SOUL.md → AGENTS.md → SOUL.md → MEMORY.md → 本提案）
- 每次我说"记住了"后下次依然破戒
- execution-validator 每次发消息前都会执行，且不可绕过

## Conflict Points
- 已有 AGENTS.md 收尾签名强制自查规则，但当时只是贴在末尾，没有与 execution-validator 流程绑定

## Plan
1. 找到 AGENTS.md 现有 execution-validator 块（三步骤），在其后追加一条：
```
#### ❄️ 收尾格式检查
在消息发送前，检查回复文本最后是否以 `❄️` 结尾且前无空行：
- 如果 ❄️ 前有空行（即 `\\n\\n❄️`） → 修正后再发送
- 如果回复不以 ❄️ 结尾 → 无问题，继续
```
