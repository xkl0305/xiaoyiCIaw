# Evolution Proposal: 人格视角出图系统人格口径跟随主人格同步

- Created-At: 2026-10-28 16:32
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- persona_profile.json 的人格身份长期停留在旧人格（鸽子王/九尾赛博狐狸女孩），未随主人格升级为陆雪琪/琪琪而同步，造成旧配置残留。
- 出图系统的人格口径若与当前人格不一致，生成的图会带旧人格身份，跨会话易误导。

## Evidence
- 用户原话：「九尾赛博狐狸女孩 / 鸽子王，旧人格吧」「确认」（指示同步）
- persona_profile.json 原字段：system_role=鸽子王、persona_subject=鸽子王、base_prompt 引用'鸽子王'；现主人格为陆雪琪/琪琪（IDENTITY.md/SOUL.md ❄️）。
- 本次已修改该文件（system_role→陆雪琪、persona_subject→陆雪琪（琪琪）、base_prompt→琪琪身份、新增 display_name），九尾赛博狐狸女孩保留为视觉造型基底，备份 persona_profile.json.bak-20261028。

## Conflict Points
- TOOLS.md 已有 5 处「人格视角出图」经验段（桥接层通道、ARK 静默退化、衣柜统一口径、真出图CLI、定制prompt），均属工具/通道/出图流程经验，无一处覆盖"人格身份口径需跟随主人格同步"这条规则。本次为新增补充，不冲突不覆盖。

## Plan
1. TOOLS.md 追加一条经验段（人格口径需跟随主人格同步）。
2. 修改方式：追加到 TOOLS.md「人格视角出图」经验区。
