# Evolution Proposal: write-gate 二次确认缺陷修复(inFlow)——确认后流程窗口内正式文件自动放行

- Created-At: 2026-10-29 20:39
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- 用户连续踩坑:"write-gate机制又两次确认"——一次进化要确认两遍,体验差
- 根因:确认命中只把"已登记 pending"的路径转 granted;若只登记 evolution-drafts 而目标正式文件(TOOLS.md)确认前未写尝试登记,确认后它不获授权 → 二次确认
- 修复:确认命中开启的流程窗口内,正式文件落盘也自动放行并授予(inFlow 分支),一次确认全覆盖

## Evidence
- 用户原话:"write-gate机制又两次确认"
- 2026-10-29 实操:固化"真实现场避坑"时,先 write pending(evolution-drafts)被拦登记,展示请求→俞哥确认→evolution-drafts放行,但 edit TOOLS.md 仍拦(TOOLS.md未在确认前登记 pending)→需二次确认。定位源码后修复 index.js 加 inFlow 分支
- gateway.restart 工具首启失败(只发signal,进程uptime不变),改用 supervisorctl restart 真重启(pid变+uptime短)才加载新代码

## Conflict Points
- 与 TOOLS.md 559「write-gate 流程窗口机制(2026-10-28)」冲突:原①⑤"正式文件须事前列明(占位edit登记)才授予,未列明仍拦截";新修复"确认后流程窗口内正式文件直接放行授予(inFlow),无需事前占位",窗口外仍拦截

## Plan
- TOOLS.md 559 段后追加更新说明(2026-10-29 inFlow 修复),不删改原文
