# Evolution Proposal: 技能与仓库一致性对账排查流程

- Created-At: 2026-09-22 10:31
- Target-File: TOOLS.md
- Trigger-Type: workflow

## Why This Matters
- 今天反复核对多个技能（xiaoyi-docx/xiaoyi-pdf/web-design-guidelines/webapp-testing/huawei-browser-news）与仓库一致性，发现几类差异（权限位漂移、tests 本地删除、未跟踪新技能），各有不同解读与处置。
- 这类排查会重复发生，值得固化为可复用流程，避免每次重新摸索。

## Evidence
- xiaoyi-docx、xiaoyi-pdf：26+ 文件 `M` 但 diff 统计 0 行 → `--summary` 确认是 `mode change 100755=>100644`（权限漂移，内容未变）。
- xiaoyi-pdf：tests/ 15 个测试文件本地被删（git 标 `D`），需用户确认删除是否有意。
- huawei-browser-news：`??` 未跟踪，需 git add。
- webapp-testing / web-design-guidelines：git status 全空，一致。

## Conflict Points
- 无冲突；与现有「技能数量统计口径」互补（一个讲数量怎么数，一个讲单技能差异怎么排查）。

## Plan
TOOLS.md 新增独立条目「技能与仓库一致性对账（2026-09-22 固化）」：
1. 对账命令：
   - `git status --porcelain <dir>` → 看 `M`(改)/`D`(删)/`??`(未跟踪)
   - `git diff HEAD --stat -- <dir>` → 看内容增删行数
   - `git diff HEAD --summary -- <dir>` → 看是否 mode change
2. 差异解读：
   - status `M` 但 diff 统计 0 行 → mode 权限漂移（多为 100755→100644，技能安装/同步流程抹掉执行位），内容未变，`--summary` 确认后提交归一即可（`bash` 调用不需要执行位）。
   - status `D` → 本地删了文件（常见 tests/），需用户确认删除是否有意，涉及删除先问、不擅自 commit。
   - status `??` → 未跟踪新技能，需 `git add`。
   - status 全空 → 一致，无需处理。
3. 处置纪律：改仓库配置/删除前先备份；权限归一可安全提交；tests 类删除保守恢复（保留完整性）；commit 后按需 push 三端（cnb.cool/gitee/github）。
