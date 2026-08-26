# Evolution Proposal: PM2 服务进程路径残留 & NODE_ENV 跳过 devDeps 的排查

- Created-At: 2026-08-26 09:58
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- daily-hot-api 服务 7/30 启动的旧进程停留在已删除的 `skills/daily-hot-api` 旧路径，导致路由全部 `Cannot find module`，大部分接口 500，仅个别路由（如 bilibili）恰好存在而 200，极易误判为"网络/上游问题"
- 修复时又遇到 `cross-env: command not found`，根因是 `NODE_ENV=production` 使 `npm install` 跳过 devDependencies
- 两者都是可复现、通用、对未来服务排错有价值的坑

## Evidence
- `curl localhost:6688/{weibo,baidu,zhihu,thepaper,36kr}` 全 HTTP 500，`/bilibili` 200
- error.log：`Cannot find module '.../skills/daily-hot-api/dist/routes/weibo.js' imported from .../dist/registry.js`
- `ps -ef`：进程启动命令指向已删除的 `skills/daily-hot-api/dist/index.js`，父进程为 PM2 God Daemon
- 新目录 `workspace/daily-hot-api` 数据完整（56 个路由 js），`start` 脚本用相对路径 `node dist/index.js`
- 修复后 `npm start` 报 `cross-env: command not found`（cross-env 在 devDependencies）
- `echo $NODE_ENV` = production → `npm install --include=dev` 后 cross-env 装上，服务经 pm2 重启后全部接口恢复 200

## Conflict Points
- None（TOOLS.md 无 PM2 路径残留 / devDeps 跳过相关经验）

## Plan (已执行)
1. TOOLS.md 追加「PM2 服务进程路径残留 & NODE_ENV 跳过 devDeps 排查」两条经验：
   - 路径残留：服务报 Cannot find module 时先查进程启动命令指向路径 vs 实际数据目录；`ps -ef` → `pm2 delete` → 新目录 `pm2 start ecosystem.config.cjs`；pm2 二进制不在 PATH 时从 `/proc/<pid>/environ` 找
   - devDeps：`NODE_ENV=production` 导致 `npm install` 跳过 devDeps，报 cross-env not found 时用 `npm install --include=dev` 补齐
2. 已写入 TOOLS.md 末尾，经用户确认后归档至 approved/
