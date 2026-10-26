# 提案: channel/插件安装通用纪律

- 日期: 2026-10-18
- 状态: approved
- 进化项: TOOLS.md 新增「channel/插件安装通用纪律」段(由微信段泛化)
- 修改文件: TOOLS.md(「插件安装规则」段前)

## 规则
1. 装审计版本=审计版本
2. 重启前确保配置已持久化(防内存覆盖丢失)
3. 工具层"中断"≠真失败,以supervisord status pid/uptime判断
4. 重启用supervisorctl不用gateway restart
5. 验证: channels status显示enabled, configured, running

---
## 补确认闭环(2026-10-21 20:35)
- 落盘时漏先展示提案,违反 Playbook step1,俞哥已确认本次内容,补记确认闭环。
