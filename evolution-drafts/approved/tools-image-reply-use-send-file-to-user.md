# Evolution Proposal: 出图后回传必须用 send_file_to_user（xiaoyi-channel 不渲染 MEDIA 附件）

- Created-At: 2026-08-08 11:27
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- 用 seedream-image-gen 等技能出图后，用 `MEDIA:路径` 附件回传在 xiaoyi-channel 对话框不渲染，用户看不到图
- 必须改用 `send_file_to_user` 直接推文件到用户设备才能送达
- 现在规则只写了"文件回传用 send_file_to_user"，没点透"出图后回传图"这个高频场景，容易再次踩 MEDIA 附件坑

## Evidence
- 用户两次问"图呢 / 对话框里没有"，说明 MEDIA 附件未送达
- 改用 send_file_to_user 后 `成功发送 3 个文件到用户设备`

## Conflict Points
- 已有「文件回传场景接口使用要求」规则（用 send_file_to_user），本次是补充"出图后回传 + MEDIA 附件不渲染"的具体坑，非冲突

## Plan
1. 在 TOOLS.md「文件回传场景接口使用要求」小节内补充一条：生成图片/文件后回传，不要用 MEDIA: 附件（xiaoyi-channel 不渲染），必须用 send_file_to_user
