# 进化提案：skill-sync-heal 误恢复"错误命名残留"的排查与定性法

- **日期**: 2026-11-01
- **状态**: pending → approved（俞哥 05:08 确认）
- **落盘目标**: TOOLS.md「环境重建技能丢失 → git 对账自愈」区（skill-sync-heal 机制条目下）

## 背景

2026-11-01 05:00 skill-sync-heal 日志报 `restored deleted files: 2 files`，恢复 `getdevicedetails.js`、`getdevicedetail/SKILL.md`（均为错误命名残留，正确为 `get_device_details.js` / `get_device_*` 系列）。排查确认：磁盘 / git index / git HEAD 三处均无这 2 文件 = 当前干净，属 heal 把历史残留误恢复了一下。

## 规则（排查与定性法）

1. **机制理解**：skill-sync-heal 每天 05:00 按 git `status --porcelain` 找 skills/ 下 D（删除未提交）状态文件，`git restore --source=HEAD --worktree` 自动拉回，并群发"已自动恢复 N 项"。
2. **收到恢复通知先定性，别急着处理**：恢复的文件可能本就是"错误命名/冗余残留"（该删而不该留）。
3. **三处排查法（磁盘 / index / HEAD）**：
   - 磁盘：`ls -la <path>` 看是否存在
   - index：`git ls-files <path>` 看是否被暂存跟踪
   - HEAD：`git ls-tree -r HEAD --name-only | grep <关键词>` + `git log --all -- <path>`
4. **判定**：三处均不存在 = 当前干净，被恢复的是历史残留；若 HEAD 存在 = 已被正式跟踪需判断是否该删。
5. **处理**：错误命名冗余文件当前已不在、git 无 D 标记 → 保持现状无需处理，观察明早 05:00 是否复发；复发则 `git rm` + commit 从 HEAD 移除跟踪记录根治。
6. **对照正常命名**：被恢复文件常是正确命名的变体（少下划线/错目录），对比同目录正确命名文件即可秒判。
