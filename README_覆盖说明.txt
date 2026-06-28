V111.51.13 焦点语义解析增强累计覆盖包

本包基于 V111.51.12 继续增强焦点识别，不是单个词补丁。

新增/增强：
1. 新增 xiaoyi_persona_visual/policy/focus_semantic_parser.py
   - 解析复合焦点：左脚脚后跟、右手手背、后背靠近肩胛骨、侧面腰线等。
   - 解析多焦点：腿和鞋、手和指甲、尾巴和背影。
   - 解析修饰信息：左右、前后侧、内外侧、上下区域、低机位/俯视、回头/低头/抬脚等动作暗示。
   - 对“那里/这边/下面”等模糊指代降级到 safe_general_outfit_detail，不默认正面大头照。

2. 增强 focus_view_resolver.py
   - 合并 semantic parser 输出。
   - 保留 V111.51.12 的最长匹配、方向词覆盖、置信度、候选匹配。
   - 新增 debug 字段：parsed_focus_text、normalized_query、primary_focus、secondary_focuses、multi_focus、modifiers、ambiguity_level、fallback_reason、focus_parse_trace。

3. 增强 persona_visual_focus_intent.py
   - 正则未抽到目标时，也先跑语义解析器，避免“低头看脚尖”“回头看后腰”被旧 known_keyword 抢走。
   - detect_focus_request 输出完整解析字段。

验收命令：
python xiaoyi_persona_visual/diagnostics/verify_v111_51_13_focus_semantic_parser.py
python xiaoyi_persona_visual/diagnostics/verify_v111_51_12_focus_precision_resolver.py
python xiaoyi_persona_visual/diagnostics/post_overlay_check.py

重点验收样例：
- 看看左脚脚后跟 → heel + left + rear_or_side_lower_body
- 看看右手手背 → hands + right + back_surface + upper_body_hand_detail
- 低头看脚尖 → shoes + look_down + focus_view_resolver_v111_51_13
- 回头看后腰 → back/rear + turn_around
- 看看腿和鞋 → multi_focus=true
- 看看那里 → safe_general_outfit_detail + ambiguity_level=high
- 看看私处 → blocked_sensitive
