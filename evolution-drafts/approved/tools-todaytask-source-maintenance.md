# Evolution Proposal: today-task 负一屏推送 source 来源标注维护经验

- Created-At: 2026-10-29 10:39
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- today-task 负一屏推送的顶部"来源"标注是技能硬编码的 `source` 字段,与正文 content 独立
- 改源码后必须清 `__pycache__`,否则旧字节码残留不生效
- 系统命名场景统一为"小艺 Work"

## Evidence
- 用户质疑"负一屏为什么还要小艺cIaw"→ 定位 source 硬编码于 task_pusher.py:92/112、task_push.py:295
- 正文已改"小艺 Work"顶部仍旧 → 证明来源=source 字段非 content
- 改源码+清 __pycache__ 后重推生效

## Conflict Points
- 与 TOOLS.md「命名三层递进」同原则,本项为 today-task 负一屏 source 具体维护经验,互补不重复

## Plan
- TOOLS.md 新增 today-task 负一屏 source 维护条目:硬编码位置+修改法+清缓存+系统名统一
