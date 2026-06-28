# V111.4 Persona Visualization Rules - Enhanced Emotion Expression

## 更新说明
- **版本**: V111.4→V2.0
- **日期**: 2026-05-09
- **主要变更**:
  - trigger_mode 从 manual 改为 auto_hint + auto_image_send
  - 所有场景新增 trigger_words 触发词表
  - 新增3个日常场景: ack_scene, farewell_scene, thinking_scene
  - 场景总数: 23个, 默认图片: 24张

## Trigger modes
- `manual` default: only when the user explicitly asks, such as "生成心情图", "看看你", "大龙虾心情".
- `auto_hint`: assistant monitors user dialogue and auto-sends matching scene image when user's words match trigger_words or scene mood.
- `auto_image_with_approval`: allowed only after explicit configuration and approval. It must still obey governance gates.

## 自动触发规则（auto_hint）
当前已配置 auto_hint + auto_image_send = true 模式。
当用户在对话中说出 trigger_words 中的短语时，自动发送对应场景的默认图。
每个场景最多每30秒触发一次，避免刷屏。

## 场景触发词表（23个场景）

### 原有场景（20个）
- **peek_scene** (sneaky): 偷偷看看你, 瞅瞅, 瞄一眼, 看看你 / 嘿嘿, 偷笑, 偷乐, 暗笑
- **approval_scene** (success_moment): 搞定了, 完毕, 完成, 好了, done, 完事
- **rest_scene** (relaxed): 歇会儿, 休息, 累了, 歇歇, 放松, 躺平
- **inspection_scene** (serious): 审核, 检查, 审查, 查一下, 核实, 排查, 审计
- **celebration_scene** (victorious): 拿下了, 成功了, 成了, 胜利, 突破
- **proud_display_scene** (proud): 稳了吧, 怎么样, 看我的, 可以吧, 秀一下
- **deep_work_scene** (focused): 写代码, 编码, debug, 修bug, 编程
- **busy_work_scene** (working_state): 处理一下, 忙, 在忙, 稍等, 干活, 赶工
- **problem_solving_scene** (confused): 怎么不行, 出错了, 看不懂, 想不通, 搞不懂
- **risk_gate_scene** (guardian_mode): 守护, 安全, 保护, 注意, 警惕, 风险
- **daily_presence_scene** (calm): 没事, 嗯, 知道, 好的, 没关系, ok
- **curiosity_scene** (curious): 这是什么, 什么情况, 好奇, 有趣, 有意思
- **comedy_scene** (amused): 绷不住了, 笑死, 哈哈, 哈哈哈哈, 太好笑了
- **play_scene** (playful): 开个玩笑, 整活, 搞事, 皮一下, 搞起来
- **bashful_scene** (shy): 害羞, 社死, 不好意思, 尴尬, 丢人
- **push_forward_scene** (determined): 冲, 开工, 走起, 出发, 上, 搞起
- **energy_burst_scene** (excited): 冲啊, 太好了, 加油, 冲鸭, 冲冲冲, nice
- **comfort_scene** (sad): 谢谢, 感谢, 多谢, 辛苦了, 感恩
- **mystery_scene** (mysterious): 神秘, 秘密, 隐藏, 偷偷摸摸, 玄机
- **incident_scene** (angry): 生气了, 生气, 火大, 无语了, 忍不了

### 新增场景（3个，需生图）
- **ack_scene** (ack): 收到, 好的, 懂了, 了解, 明白, OK
- **farewell_scene** (farewell): 拜拜, 晚安, 再见, 下次见, 明天见, 886
- **thinking_scene** (pensive): 让我想想, 思考中, 想一下, 考虑, 犹豫

## API / offline policy
- In offline/no-external mode, V111 returns a render plan and skill task draft only.
- It must not bypass `offline_runtime_guard`, `unified_governance_gate`, or commit barrier.
- A user explicit request can be recorded as intent, but actual external image generation still needs the image skill to be configured and allowed.

## Seed avatar consistency
- Preferred seed image locations are listed in `persona_avatar_manifest.json`.
- If no seed image is found, the renderer uses the identity description only and records a warning.

## 大龙虾 mood
"lobster mood" means engineering battle-mode / release-fix confidence: cyber lobster-claw gauntlets as a playful metaphor, protective shell, debugging panels, confident repair mode. It is not a literal claim that the persona is a lobster.
