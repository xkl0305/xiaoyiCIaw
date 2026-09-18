# Evolution Proposal: 技能数量多口径差异核对方法

- Created-At: 2026-09-18 11:39
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
用户反复追问"技能数量与仓库是否一致"。技能数存在多个口径（329 目录 / 332 含文件 / 333 含隐藏 / 328 索引缓存 / 219 OpenClaw加载），每次都用不同数字核对会自相矛盾，且 git 对账命令选错会得出错误结论（ls-files 会因嵌套文件数出偏差）。固化成统一核对方法，避免反复踩坑。

## Evidence
- 用户多次问"技能数量与仓库一致吗""不是332个吗""需不需要记住固化"
- ls -1 skills/ 数出 332（含 README.md/__init__.py/残留 .zip 三个非技能文件），而技能目录仅 329
- 维护报告写 328，实际来自 skill_index 索引缓存，非实时目录数
- git ls-files 'skills/*' 会因嵌套子 SKILL.md 数出 471/331，必须用 git ls-tree -d 才准（328/329）

## Conflict Points
原 TOOLS.md「技能数量统计口径（2026-09-03 固化）」一节写 330 个（旧值），且未覆盖：skills/ 顶层非技能文件、索引缓存口径、git ls-tree 对账法。本次需更新该节、补充多口径差异与正确对账命令。

## Plan
1. 在 TOOLS.md「技能数量统计口径」节补充以下要点：
   - 报告"技能数量"始终用"顶层技能目录"口径（find skills -maxdepth 1 -mindepth 1 -type d 排除 . 开头与 __pycache__），当前 329。
   - 数字来源差异：332=含 skills/ 顶层非技能文件（README.md/__init__.py/残留 .zip）；333=再加隐藏 .archive；328=维护脚本读 skill_index 索引缓存(非实时)；219/150=OpenClaw 框架加载计（另一套口径）。
   - git 对账必须用 `git ls-tree -d --name-only HEAD skills/`（只列实际跟踪目录），禁止用 `git ls-files 'skills/*'`（因嵌套文件数出 4xx 偏差）；本地用 find -type d 同口径。
2. 将旧"当前 330 个"更新为当前实际值（以实际 find 为准，本次为 329），并删除/注明过期数字。
