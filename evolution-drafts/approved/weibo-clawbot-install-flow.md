# 进化提案：微博 ClawBot 插件安装流程

- **日期**：2026-09-04
- **进化项**：微博 ClawBot 插件安装配置流程（凭证配置位 + 重启 + 验证）
- **修改文件**：TOOLS.md
- **状态**：approved（用户已确认"需要记住固化进化一下"）

## 经验规则
1. 插件用 npm 官方 `@wecode-ai/weibo-openclaw-plugin`，安装源走 `cn.clawhub-mirror.com` + npmmirror，装前须 plugin-audit 审计
2. 客户端 `clientId/Secret` 对应 `AppId/AppSecret`，写入 `openclaw.json → channels.weibo`
3. 装后改配置 → supervisor 重启（`python3 -m supervisor.supervisorctl restart openclaw-gateway`）→ `openclaw status` 验证 `Weibo ON · OK · configured`
4. 重启前先备份 openclaw.json 并提示用户会短暂断连

## 验收
- 微博通道 ON·OK·configured
- weibo_hot_search 实测连通（解决微博热搜接口 403 问题）
