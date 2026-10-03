---
name: wacx-novel-writer
description: "长篇小说创作与审阅一体化技能（含Phase2.5前10章试读仿真）。适用：写长篇/逐章/全自动/十维评分/逻辑审计。不适用：短篇。触发词：写长篇|长篇大纲|写小说|逐章写|长篇审阅|长篇评分|全卷逻辑审计|写单章|小说十维评分|长篇去AI味。"
---

# 长篇小说技能

## TL;DR（5 步）

1. **定题型**：用 `references/genre-profiles-detail.md` 12 题材选 1 + 篇幅（50-100万字）
2. **写开局**：第1章首句三件事（世界观+冲突+主角）+ 前50字四要素同爆；前3000字出高潮
3. **埋节奏**：321 公式（3章一小爽/2章一中爽/1章一大爽）+ 每章末钩（`references/chapter-end-hook.md` 5 类）
4. **逐章写**：单章 1800-2200 字，对话≥30%；前10章后**自动触发Phase 2.5 试读**（5人读者+共性P0+圣经硬线）
5. **跑闸门**：8 个机械闸 + 十维（每维≥90）全过才交付

## 6 大框架入口

- 框架1 立项与门面 → `references/premise-frontend-gate.md`
- 框架2 十维评分 → `references/novel-quality-hardlines.md`
- 框架3 去AI味 → `references/deai-banned-words.md` `references/deai-structures.md` `references/deai-examples.md`
- 框架4 期待感与节奏 → `references/expectation-engine.md` `references/rhythm-climax-plus.md` `references/rhythm-tension.md`
- 框架5 人设与逻辑 → `references/character-integrity.md` `references/logic-audit-33.md`
- 框架6 全自动 → `references/boundary-fallback.md` `references/reader-simulation.md`（Phase 2.5 试读）

## 零基础上手（5 分钟快速路径）

适合第一次用、不了解长篇写作方法论的场景。按此顺序执行即可获得专业产出：

1. **只想先出结果**：直接说目标（如「写第一章」「生成长篇大纲」），本技能会带你走一遍。
2. **要立项**：从 `references/genre-profiles-detail.md` 12 题材里选 1 个，接着给主角一句话人设 + 世界观一句话，剩下交给框架 1。
3. **要审阅/去AI味**：把章节贴上来或给出章节路径，本技能会用 8 个机械闸脚本 + 去AI味规则 + 十维评分过一遍并给逐点证据。
4. **要全卷把控**：说「全卷逻辑审计」/「长篇评分」，本技能用 `references/logic-audit-33.md` / `novel-quality-hardlines.md` 出结果。
5. **不确定怎么开口**：说「从头带我写一部长篇」，本技能自动走 Phase 0 立项流程。

> 不需要你懂术语——只要描述你的目标，本技能负责按专业标准执行。

## 审阅容错（短文本 / 孤例）

审阅与评分时，按可评定维度执行并如实说明，不硬凑评分：

- 面对**短文 / 孤例 / 片段**（如仅一段文字、无情节对话可评），十维评分只对**可评定**的维度给出分数（如文笔质感、去水/节奏），对无可评材料的维度标注「孤例无可评」并说明原因，不强行打分、不编造证据。
- 机械闸脚本照常全量运行；依赖外部事实锚（fact_anchor）的反幻觉闸在缺锚时降级为 LLM 自评并注明，不阻断其余检查。
- 交付时在报告中清晰区分「已实测」与「按规则判断」两类结论。

## 本技能相对直接提示的增值

本技能不只是"让 AI 写小说"，而是把职业网文方法论固化为**可验证、可复现**的过程：

- **8 个机械闸脚本**（`scripts/`）自动检测水词、AI 味、重复句、字数、引号、钩子、幻觉等，无本技能时无法自动执行，逐项给出 exit 码与证据。
- **十维评分硬线**（每维 ≥90）量化"好与不好"，直接提示往往只能给主观意见。
- **全卷逻辑审计 / 去AI味禁词表 / 节奏公式 / 章末钩分类**等专业知识已编码到 79 个 references，开箱即用。
- **Phase 2.5 试读仿真**：前 10 章后自动模拟 5 位读者 + 共性 P0 过滤，直接提示无法复现。

> 一句话：直接提示给你"一个结果"，本技能给你"结果 + 为什么好 + 怎么持续保证质量"。

## 5 道检查点闸

| 闸 | 触发 | 动作 |
|----|------|------|
| C1 路径 | 意图未明 | 走 Mode 选择 |
| C2 锚点 | 灵魂锚点空 | 退回采集 |
| C3 决策 | 确认未回 | 暂停等用户 |
| C4 交付 | 文件跑完 | 机械全 0+逐维证据 |
| C2.5 试读 | Phase 2 前 10 章后 | 5人画像+共性P0+圣经过滤+报告输出 |

## 5 条 P0 硬线

1. 中文双引号唯一（禁英文/日式/单引号）
2. 第1章首句＝世界观+冲突+主角；第1章末主角主动决策
3. 灵魂锚点非空
4. 零确认硬线：Phase 0 后全自动不询问
5. 巧合单向：巧合只能给主角制造麻烦

## 验收铁律

- 8 个机械闸脚本全 exit=0
- 十维评分每维≥90
- H 类全卷逻辑审计通过
- 命中 P0 毒点（送女/绿帽/历史虚无/政治影射/公职负面/宗教民族敏感）→ 不交付
- Phase 2.5 试读：5人读者+共性P0（≤5条）+圣经过滤，通过P0 ≤前10章10%字数改动

## References 速查（79 个）

- 评分：`review-scoring.md` `gh-audit.md` `logic-audit-33.md` `novel-quality-hardlines.md` `consistency.md` `foreshadowing-system.md` `scene-transition-guide.md` `quality-checklist.md` `human-behavior-baseline.md`
- 去AI：`deai.md` `deai-banned-words.md` `deai-structures.md` `deai-methods.md` `deai-examples.md` `pov-verb-gate.md` `water-quality-thinking.md`
- 钩子：`opening-hooks.md` `hook-techniques.md` `golden-opening.md` `chapter-guide.md` `chapter-end-hook.md`
- 节奏：`rhythm-tension.md` `rhythm-climax-plus.md` `tension-spring.md` `emotion-curve.md` `emotion-promise.md` `emotion-tears.md` `structure-engines.md` `outline-engineering.md` `outline-blueprint.md` `volume-planning.md` `worldbuilding.md` `plot-engine-foreshadow.md` `mainline-navigation.md` `outline-5-archetypes.md`
- 人物：`character-integrity.md` `character-relationship-map.md` `character-profile-template.md` `villain-wildcraft.md` `golden-finger.md`
- 题材：`genre-craft.md` `genre-profiles.md` `genre-lexicon-extra.md` `feature-words.md` `feature-words-extra.md` `positive-lexicon.md` `narrative-style-lexicon.md` `naming-lexicon.md`
- 平台：`contract-platform.md` `platform-tomato.md` `industry-intel.md` `master-mindset.md` `meta-playbook.md`
- 深度：`psychology-techniques.md` `action-scene-directing.md` `romance-tension.md` `group-narrative-directing.md` `beauty-strong-tragic.md` `scene-test-method.md` `focus-writing.md` `cinematic-narration.md` `ultimacy-crisis.md` `european-chinese.md` `reader-simulation.md`
- 拆书：`book-deconstruction.md` `adaptation-playbook.md` `bestseller-methodology.md` `bestseller-tactics.md` `methodology-breakout.md` `breakout-methodology-extra.md`
- 特殊：`forensic-details.md` `dog-path-system.md` `endurance-worldbuild.md` `expectation-engine.md` `twist-conflict.md` `story-validity.md` `content-expansion.md` `experience-summary.md` `self-improve.md` `auto-creation.md` `module-one-prescreen.md` `premise-frontend-gate.md` `fallback-rules.md` `boundary-fallback.md` `endurance-scene.md`

## 触发词

`写长篇` `长篇大纲` `写小说` `长篇创作` `逐章写` `长篇审阅` `长篇评分` `全卷逻辑审计` `写单章` `单场景写作` `小说十维评分` `长篇去AI味`
