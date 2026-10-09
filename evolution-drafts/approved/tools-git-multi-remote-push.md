# 种子提案: Git 多 remote 提交后分别推送

- **日期**: 2026-09-26
- **状态**: approved
- **进化项**: 固化「git 多 remote 需分别推送各 remote」经验到 TOOLS.md
- **修改文件**: TOOLS.md(新增「Git 多 remote 提交后分别推送」段,位于 Git Push 失败排查规则之后)

## 经验规则
1. 本仓库 3 remote:origin(cnb.cool) / gitee / github;无参 `git push` 只推 upstream(origin)。
2. 多端同步须分别 `git push gitee main` + `git push github main`。
3. commit 后先 `git remote -v` 看全 remote 数,逐个 push,勿默认只推 origin。
4. 各 remote 历史起点可能不同但都能快进到最新 commit。
5. 触发场景:用户问"X 个仓库都推送了吗"/提交后要求多端备份同步。

## 依据
- 实测:push 无参只推 origin(gitee/github 停旧),补推后三端对齐到 8c188be。
