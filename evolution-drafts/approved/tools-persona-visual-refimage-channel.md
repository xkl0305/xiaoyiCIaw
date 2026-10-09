# Evolution Proposal: 人格视角出图·参考图通道差异

- Created-At: 2026-09-30 23:19
- Target-File: TOOLS.md

## Why This Matters

人格视角出图"保脸/带参考图"取决于走哪个通道：SSE 代理通道 `_call_seedream_sse` 里"传参考图"是 TODO、实际不生效，产出纯 prompt 图；只有 ARK 直连才真正注入两张 ref_images。不清这点会误以为所有出图都带参考图。

## Evidence

- 用户原话：「人格视角出图系统的参考图是」「参考图呢」「需不需要记住固化进化一下」
- 代码证据：`xiaoyi_persona_visual/helpers/cli_generate.py` 内 `_call_seedream_sse` 注释"参考图：SSE 代理需要公网 URL 或 OSMS 上传，先跳过参考图测试核心生图；TODO: OSMS 上传参考图" → SSE 通道不带参考图
- ref_images 构成：`assets/persona/seed_avatar.jpg`（人脸种子图，persona_profile.reference / visual_identity_profile.face_reference_image）+ `assets/persona/outfits/{outfit_id}_reference.jpg`（穿搭参考）
- 2026-09-30 实测：SSE 代理通道出的图（generation_channel=sse_proxy）无参考图注入

## Conflict Points

- TOOLS.md「人格视角出图·真出图 CLI 与 MAINCHAIN_PROOF_KEY」条目第4点只写"无 ARK 直连环境时自动走 SSE 代理"，未提及"SSE 通道参考图不生效、ARK 才带参考图" → 同条目补充，不构成冲突。

## Plan

在该条目「**验证**」段之前插入「**参考图通道差异**」小节：

```
**参考图通道差异(2026-09-30 补充):**
- **SSE 代理通道(`_call_seedream_sse`)实际不传参考图**——代码注释标明"参考图需公网 URL 或 OSMS 上传,先跳过参考图测核心生图;TODO: OSMS 上传参考图",出的是**纯 prompt 图**。
- **只有 ARK 直连通道才真正注入两张 ref_images**:`assets/persona/seed_avatar.jpg`(人脸种子图,persona_profile.reference / visual_identity_profile.face_reference_image)+ `assets/persona/outfits/{outfit_id}_reference.jpg`(穿搭参考,默认 moonfeather_robe 月羽云裳)。
- **含义**:若关心保脸/带参考图,必须走 ARK 直连;SSE 通道仅测核心生图。
```
