# 进化请求（标准格式归档）· seedream 出图 SSE 假成功 + 9:16 档

- **日期：** 2026-11-06
- **status：** approved
- **进化项：** seedream 出图双通道经验固化 + 9:16 竖屏尺寸档（补正：此前固化/修正未走标准三字段格式，本次按标准格式规范化归档闭环）
- **经验规则：**
  1. seedream-image-gen 走 huawei_sse 通道时，返回 status=generated 但图可能未落盘（.persona_visual/generated/ 或 generated-images/ 目录为空）即为假成功；判断标准以落盘文件为准，不看 status；SSE 假成功时切 ARK 通道可真实出图+落盘。通道顺序关联：人格视角出图桥接层本就 ARK 优先（channel="ark,huawei_sse"）；seedream-image-gen skill 默认 huawei_sse→ark→siliconflow，此处"切ark"即回到人格系统第一顺位主通道。
  2. 原 --size 枚举无精确 9:16（最接近 4K-portrait=3:4、2K/3K=1:2）；已给 seedream_provider._SIZE_MAP 补 '9:16':'2304x4096'，generate_seedream.py --size 增 '9:16' 选项，备份 .bak-20261106；用 --size 9:16 --channel ark 出严格 9:16（2304×4096）。
- **修改文件：** TOOLS.md（seedream 出图「SSE 假成功」与 9:16 竖屏档 条目）+ evolution-drafts/approved/ 本归档
