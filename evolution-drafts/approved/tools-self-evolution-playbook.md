# 种子提案: 自进化固化操作全流程 Playbook

- 日期: 2026-10-02
- 状态: approved
- 进化项: TOOLS.md 新增「自进化固化操作全流程 Playbook」段
- 修改文件: TOOLS.md(「自进化请求标准格式」段前)

## 操作顺序(step 1→7)
1. 发现经验 → 展示「🧠 小艺Claw进化请求」+ 等确认,禁止先落盘
2. 写一次性令牌 .write-gate-allow.json(exp 必须毫秒)
3. 先备份再 edit 落盘
4. 归档提案副本到 evolution-drafts/approved/
5. 清理令牌
6. grep 校验写入成功/结构完整
7. 回复带确认句 + ❄️ 收尾

## 关键纪律
令牌≠流程确认;确认句在 xiaoyi-channel 自动注入不可行,靠纪律保障。
