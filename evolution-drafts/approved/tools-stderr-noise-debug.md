# Evolution Proposal: Stderr噪音排查流程——函数参数类型不匹配被try/except吞掉

- Created-At: 2026-08-07 06:15
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 每日维护报告频繁拖一长串 stderr（曾 170 条 `'>=' not supported between instances of 'str' and 'int'`），表面看是"一堆报错"，实则只有根因一个。
- 排查依赖实跑复现 + 逐帧抓 trace，而非读代码走读——踩坑有复用价值。

## Evidence
- 用户反馈"--- stderr ---，很长"，指向维护脚本输出尾部的大量重复报错。
- 根因：`scripts/_archived/memory_pipeline.py` 调用 `AutoMemory.force_consolidate(mid, "long_term")`，把参数 `target_layer` 传成字符串，函数内部 `elif target_layer >= 4:` 拿 str 与 int 比较抛 TypeError。
- 该异常被 distill 的大 try/except 捕获，只 `logger.warning` 计数累加，不中断流程 → 变成 stderr 噪音。
- 关键排查手段：直接 `python3 -c` 实跑复现，遍历全部 entries 单独调用 `force_consolidate` 打印 traceback，才定位到真正抛错函数。

## Conflict Points
- None

## Plan
1. 在 TOOLS.md 追加一条排错经验：**维护脚本 stderr 大量重复报错时，先实跑复现抓 traceback 定位根因函数，再检查跨模块调用参数类型是否与函数签名一致**；根因常藏在被 `try/except` 吞掉的 warning，而不是堆栈表面。
2. 写入方式：在 TOOLS.md "Git Pull失败排查规则" 之后新增小节，标题 `### 维护脚本 Stderr 噪音排查规则（2026-08-07）`，内容精简。
