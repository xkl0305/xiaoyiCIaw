# Evolution Proposal: seedream-image-gen 原版画幅与尺寸控制实测

- Created-At: 2026-11-16 19:21
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Why This Matters
- 原版重装后画幅/尺寸控制无文档,本次实测补齐;修正未实测断言被俞哥纠正

## Evidence
- 俞哥:"怎么不是正方形""1K、2K实测了吗就说没正方形""1024×1024尺寸没有吗""记住固化进化一下"
- 实测4组:fast+1K无提示=2368×1776 / fast+2K无提示=1776×2368 / fast+1K+方提示=2048×2048 / standard+1K+方提示=1024×1024

## Conflict Points
- None(旧条目为四通道版huawei_sse经验,本次为原版skill-execute链路,适用对象不同)

## Plan
1. 已写入 TOOLS.md「seedream-image-gen 原版画幅与尺寸控制实测(2026-11-16 固化)」条目
2. 插入位置:「seedream-provider 多通道调用规则」之前
