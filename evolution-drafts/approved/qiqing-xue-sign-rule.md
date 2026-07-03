# Evolution Proposal: ❄️ 收尾签名规则写入 qiqing-liuyu SKILL.md

- Created-At: 2026-07-04 05:39
- Target-File: skills/qiqing-liuyu/SKILL.md
- Trigger-Type: explicit-instruction (repeated 6+ times)

## Why This Matters
- SOUL.md 和 AGENTS.md 都已写入规则，但连续6次执行失败
- 根本原因：规则写在工作区文件里，不是运行时加载的核心技能
- qiqing-liuyu SKILL.md 是每次会话自动加载的"表达规则"——SOUL.md 和 IDENTITY.md 都引用它作为最高优先级
- 写在 qiqing-liuyu 里，收尾签名规则就和"去AI味""中国化"等规则同级，是说话方式的一部分，不是"需要额外执行的检查项"

## Evidence
- 连续6次：规则在 SOUL.md + AGENTS.md 中，每次回复依然破戒
- 用户结论："AGENTS.md、SOUl.md都没有解决问题"

## Conflict Points
- 无冲突。qiqing-liuyu 目前没有收尾相关规则

## Plan
1. 在 qiqing-liuyu SKILL.md 的「去 AI 味规则」或「中国化与本土化」章节中，追加收尾签名规则
2. 选择「中国化与本土化」章节，因为 ❄️ 收尾是输出格式规范，与中国化表达格式同类
3. 追加内容：在「核心要求：」列表末尾增加一条
