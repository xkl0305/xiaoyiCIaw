# Evolution Proposal: B站 账号关注列表抓取经验(B站 API/space 均需登录态,最靠谱=用户直接提供UP主)

- Created-At: 2026-10-30 11:21
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- 用户给 B站 账号(星空恋love)让查关注列表里 Excel/Word/PPT UP主,3 条抓取路径全部受阻,实测记录
- 可复用经验:查 B站 账号关注需登录态,隔离浏览器无登录 cookie

## Evidence
- 搜索用户 API 可用 / 关注列表 API -101 / space 关注页"出错啦" / 隔离浏览器无登录cookie
- 最靠谱: 用户直接文字提供 UP主名字,逐个 B站 搜索爬

## Conflict Points
- 无重复;新增独立小节

## Plan
- TOOLS.md 在 1321 Power Query 深度条目后新增小节
