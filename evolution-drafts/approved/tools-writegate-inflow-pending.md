# Evolution Proposal: write-gate 窗口内放行也登记 pending 修复经验固化

- Created-At: 2026-10-30 10:30
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- 2026-10-30 10:24 实测事故:窗口内写 evolution-drafts 放行但未登记 pending→俞哥 10:25 确认时 pending 空→确认词落空→正式文件被拦需二次确认
- 修复: evolution-drafts 窗口内放行时也登记 pending,确认命中正常授予+续窗

## Evidence
- 修复代码: write-gate/index.js 纯 evolution-drafts 分支,登记移到 inFlow 判断前(两分支都登记)
- 修复后链路: 窗口内写提案(放行+登记)→确认(pending 非空,命中,授予+开新窗)→正式文件(新窗 inFlow 放行),一次确认全程通
- 备份: index.js.bak-inflow-pending-20261030-1028;重启验证 pid 17390

## Conflict Points
- 与 560 行「write-gate 流程窗口机制」为补充关系,追加第⑥条,不冲突

## Plan
- TOOLS.md 560 行条目末尾追加 ⑥:窗口内放行也登记 pending 修复
