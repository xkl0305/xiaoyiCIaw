# Evolution Proposal: 火山引擎 ARK 多画幅实测

- Created-At: 2026-10-24 18:29
- Target-File: TOOLS.md

## Why This Matters

ARK 直连支持多 size，画幅实测补齐，避免以后不确定竖屏/横屏/正方形能不能出图。

## Evidence

- 用户问「火山引擎测试过横屏、竖屏、正方形不」「竖屏怎么不是4K」→ 补测确认
- 实测（2026-10-24，channel=ark 全部 status=generated）：`2K`(1440x2880 竖)、`4K-portrait`(3072x4096 竖)、`4K-wide`(3840x2160 横)、`4K-square`(4096x4096 方) 全通；均满足 ARK ≥3686400 像素门禁
- 用户「记住固化进化一下」→ 触发本次固化

## Conflict Points

TOOLS.md 无多画幅实测内容（在定制 prompt 绕过条目后新增）→ 不冲突

## Plan

TOOLS.md「定制 prompt 绕过主管线覆盖」条目后新增小节「火山引擎 ARK 多画幅实测（2026-10-24）」，含 _SIZE_MAP 全映射 + 四画幅实测结果 + 像素门禁对照。
