# Evolution Proposal: git 三端同步推送补充 github HTTP/2 坑点

- Created-At: 2026-10-30 06:29
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle
- Status: approved

## Why This Matters
- 三端同步主规则已固化(TOOLS.md 371-385行),但 github 的 HTTP/2 网络坑点未记录
- 2026-10-30 实操:github 推送报 `HTTP/2 stream 1 was not closed cleanly`(curl 16),换 HTTP/1.1 一次成功

## Evidence
- 用户纠正:"刚刚为什么没有一起推三仓"——规则在但执行不到位
- github 首推失败(HTTP/2 framing/stream 错误),`git -c http.version=HTTP/1.1 push github HEAD:main` 重推成功

## Conflict Points
- 与 TOOLS.md 371-385「三端同步推送」同段补充,不覆盖原文,只追加 github HTTP/1.1 坑点

## Plan
- 在 371-385 段"正确操作(三端同步)"代码块后追加 github HTTP/2 坑点说明
