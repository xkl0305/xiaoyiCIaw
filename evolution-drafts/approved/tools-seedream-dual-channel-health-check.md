# Evolution Proposal: Seedream 双通道体检与补回

- Created-At: 2026-08-08 11:15
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- `.xiaoyienv` 不在 git 里，系统升级可能被静默覆写，导致 SEEDREAM_API_URL/KEY/ENDPOINT_ID 丢失
- 丢后 provider 静默退化成单通道（huawei_sse），bridge 传 "ark,huawei_sse" 只剩一根线裸奔，无任何报错提示
- 之前一直误以为双通道生效，实际名存实亡

## Evidence
- 用户："人格视角出图系统" → 排查发现 `.xiaoyienv` 无 ARK 配置，`_load_all_channel_configs()` 仅返回 1 通道
- 补回 ARK 三件套后验证返回 2 通道，bridge 双通道正确 match

## Conflict Points
- 已有「Seedream 通道配置备份」小节是兜底 data，本小节是「体检 + 补回」流程，补充而非冲突

## Plan
1. 在 TOOLS.md「Seedream 通道配置备份」小节后新增「Seedream 双通道体检与补回」小节
2. 内容：体检方法（跑 `_load_all_channel_configs()` 数通道，<2 即补）+ 补回来源（TOOLS.md 备份）+ 验证方法
