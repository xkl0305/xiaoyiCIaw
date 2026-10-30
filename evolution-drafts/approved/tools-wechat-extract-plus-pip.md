# Evolution Proposal: 微信/网页正文提取排错 + pip配置坑(2026-10-30实测)

- Created-At: 2026-10-30 17:22
- Target-File: TOOLS.md
- Status: approved

## Evidence
- pip坑: pip.conf prefix + PIP_PREFIX → Cannot set --home and --prefix together; 解法 env -u PIP_PREFIX PIP_CONFIG_FILE=/dev/null
- scrapling[fetchers] 含playwright/patchright,下载慢易被杀
- 微信正文: web_fetch/browser/Jina全失败,curl抓原始HTML抽js_content最稳
- 关联: 工具选型见354行

## Plan
- TOOLS.md 1346后新增小节
