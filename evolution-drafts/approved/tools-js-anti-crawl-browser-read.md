# 种子提案: JS 反爬/动态渲染网页读取方法

- 日期: 2026-10-01
- 状态: approved
- 进化项: TOOLS.md 新增「JS 反爬/动态渲染网页读取方法」经验段
- 修改文件: TOOLS.md(「技能发现与安装规范」段后)

## 经验规则
1. web_fetch 读到的是原始 HTML,遇 JS 混淆/动态渲染反爬站会拿不到正文(状态200但无内容)。
2. 改用 browser 工具(真实 Chromium),JS 真实执行后内容正常渲染,snapshot 可读。
3. 批量抓多 tab/面板:用 browser act evaluate 执行 JS(document.querySelectorAll 提取 innerText)一次导出,比逐个 click+snapshot 高效。
4. 适用:车展日历、动态渲染资讯页等 JS 反爬站点。
