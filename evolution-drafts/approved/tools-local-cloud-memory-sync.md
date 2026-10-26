# 提案: 本地(Windows/端侧)与云电脑记忆互通现状与路径

- 日期: 2026-10-16
- 状态: approved
- 进化项: TOOLS.md 新增「本地与云电脑记忆互通」经验段
- 修改文件: TOOLS.md(「记忆系统 autoFlush」段前)

## 规则
1. 云记忆单存云端 main.sqlite + workspace 记忆文件;端侧/本地只是入口不持有库
2. 当前未配对 nodes,不能直接实时互通
3. 间接互通: git 仓库同步(最推荐) / export-import / 文件打包回传
4. 需直接互通须 nodes 配对 + 装环境,授权才动
