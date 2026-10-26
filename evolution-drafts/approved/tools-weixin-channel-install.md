# 提案: 微信 channel 安装配置全流程

- 日期: 2026-10-18
- 状态: approved
- 进化项: TOOLS.md 新增「微信 channel 安装配置全流程」段
- 修改文件: TOOLS.md(「插件安装规则」段前)

## 规则
1. 装前必走 plugin-audit;微信包审计🟢安全
2. 版本坑: install.sh写死2.4.4,应改装已审计版本
3. 扫码: Node API生成二维码→发图→后台轮询DONE/DUP/FAIL;验证码须用户告知手动输入
4. 持久化坑: 重启前必须 ensure_weixin_config.py;重启用supervisorctl不用gateway restart
5. 重启核实坑: 工具层"中断"可能实际成功,以supervisord status的pid/uptime判断
6. 临时文件 /tmp/wx_stdout.txt 和 /tmp/wx_stderr.txt
