# Evolution Proposal: git push 前远端归属检查（防误推上游第三方仓库）

- Created-At: 2026-08-26 10:05
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 推送 daily-hot-api 时发现其 submodule 远端是 `github.com/imsyy/DailyHotApi`（上游第三方公共项目），不是己方仓库
- 若盲目 `git push`，会把本地改动推给陌生作者、污染他人仓库，属越界且可能造成负面影响
- 主仓库同时挂着 gitee / github / cnb.cool 三个己方远端，容易让人误以为"远端都是自己的"而放松警惕
- 该规则通用、可复现，对任何涉及 git 推送的任务都有防错价值

## Evidence
- `git remote -v`（daily-hot-api）：`origin https://github.com/imsyy/DailyHotApi.git (fetch/push)`，非己方仓库
- 主仓库三远端均为己方：gitee(starry-sky-love)、github(xkl0305)、cnb.cool，push 无碍
- daily-hot-api 内部有 `M package.json`、`D pnpm-lock.yaml` 等依赖文件改动（由 `npm install` 顺带产生，非有意源码变更）
- 已还原：`git checkout -- package.json` + `git checkout HEAD -- pnpm-lock.yaml`，submodule working tree 恢复干净

## Conflict Points
- None（TOOLS.md 此前无 git 远端归属检查经验）

## Plan (已执行)
1. TOOLS.md 追加「git push 远端归属检查」经验：
   - push 前必须先 `git remote -v` 确认归属
   - 主仓库己方多远端可放心推；submodule 若指向上游第三方项目则不可推
   - 非有意产生的依赖改动用 checkout 还原，保持 submodule 干净
   - 还原要点：staged 改动先 `git reset HEAD` 再 `git checkout`；被删文件用 `git checkout HEAD -- <file>` 恢复
2. 归档至 evolution-drafts/approved/
