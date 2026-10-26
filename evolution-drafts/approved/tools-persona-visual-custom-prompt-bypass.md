# Evolution Proposal: 定制 prompt 绕过主管线覆盖

- Created-At: 2026-10-24 18:21
- Target-File: TOOLS.md

## Why This Matters

用户定制造造型 prompt 走 cli_generate 主管线会被 build_persona_prompt 整个覆盖成九尾展示模板；绕过法可保留定制内容 + ARK 保脸。这是反复会踩的坑，固化成可复用方法。

## Evidence

- 用户原话（2026-10-24）：给出月白旗袍+太极束发冠+仙门背景定制 prompt，要求人格系统出图
- 实测：cli_generate dry_run 显示 prompt 被强改成 gown 模板，用户旗袍描述全丢；guard 拦裸调；用「补全 ctx + 双人脸参考 + 真实 proof」后 `status=generated`、channel=ark、image_reading 六要素全符合
- 用户：「记住固化进化一下」→ 触发本次固化

## Conflict Points

TOOLS.md 无此内容（ARK 直连修复条目后新增）→ 不冲突

## Plan

TOOLS.md「火山引擎 ARK 直连修复」条目后新增小节「人格视角出图·定制 prompt 绕过主管线覆盖（2026-10-24）」，含坑点、绕过法 4 步、实测、注意。
