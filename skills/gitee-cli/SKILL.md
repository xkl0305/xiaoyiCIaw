---
name: gitee-cli
description: "Gitee CLI 工具操作：仓库管理、Issue、PR、代码片段等。用于：(1) 使用 gitee-cli 工具进行 Gitee 操作，(2) 仓库/Issue/PR 管理，(3) 代码片段(gist)操作，(4) 调用 gitee 命令行工具。NOT for: 不使用 gitee-cli 工具的纯 API 调用（用 gitee skill），或 GitHub 操作（用 github skill）。"
---

# gitee-cli

使用 gitee-cli 工具操作 Gitee，功能对标 GitHub `gh`。

## 快速开始

```bash
# 认证登录（OAuth2 自动获取 token）
gitee auth login

# 或使用已有 token
echo "your_token" | gitee auth login --with-token

# 查看帮助
gitee --help
gitee repo --help
```

## 命令列表

| 命令 | 功能 |
|------|------|
| `gitee auth` | 认证管理（login/logout/status/token） |
| `gitee repo` | 仓库管理（list/create/view/fork/clone/browse/branches） |
| `gitee issue` | Issue 管理（list/create/view/edit/close/reopen/comment） |
| `gitee pr` | PR 管理（list/create/view/merge/review/diff） |
| `gitee gist` | 代码片段（list/create/view/edit/delete/star） |
| `gitee org` | 组织管理（list/view/members/repos/issues） |
| `gitee search` | 搜索（repos/users/issues） |
| `gitee api` | 直接调用 Gitee API v5 |
| `gitee config` | 配置管理（set/get/list/unset） |
| `gitee completion` | Shell 自动补全（bash/zsh/fish/powershell） |
| `gitee version` | 版本信息 |

## 认证

### 登录方式

```bash
# 交互式登录（自动打开浏览器授权）
gitee auth login

# 使用已有 token
gitee auth login --with-token

# 或通过环境变量
export GITEE_TOKEN=your_access_token

# 查看登录状态
gitee auth status

# 登出
gitee auth logout
```

### Token 存储

- 配置文件：`~/.gitee-cli/settings.json`
- 优先级：`--token` > `GITEE_TOKEN` 环境变量 > 配置文件

### 企业私有部署

```bash
gitee auth login --hostname your-company.gitee.com
# 或
export GITEE_HOSTNAME=your-company.gitee.com
```

## 常用示例

### 仓库管理

```bash
gitee repo list                          # 我的仓库
gitee repo list --owner torvalds         # 他人公开仓库
gitee repo create --name my-project --description "项目描述" --private
gitee repo clone owner/repo-name
gitee repo fork owner/repo-name
gitee repo browse owner/repo-name        # 浏览器打开
gitee repo branches owner/repo           # 分支列表
```

### Issue 管理

```bash
gitee issue list                        # 当前仓库 open Issue
gitee issue list --state all --labels bug,enhancement
gitee issue view 42                     # 查看详情
gitee issue create --title "Bug报告" --body "复现步骤..." --labels bug
gitee issue close 42
gitee issue comment 42 --body "感谢报告"
```

### Pull Request

```bash
gitee pr list
gitee pr create --title "feat: 新功能" --source feature-branch --target main
gitee pr view 18
gitee pr diff 18
gitee pr merge 18 --squash --delete-branch
gitee pr review 18 --approve
```

### 搜索

```bash
gitee search repos "web framework" --language go --sort stars
gitee search users "用户名"
gitee search issues "关键词" --state open
```

### 直接调用 API

```bash
gitee api GET /user
gitee api GET /user/repos?per_page=10
gitee api POST /user/repos --field name=test --field private=true
gitee api GET /user/repos --paginate   # 自动分页
```

### 配置管理

```bash
gitee config set editor vim
gitee config set protocol ssh
gitee config get protocol
gitee config list
gitee config unset editor
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--token` | Access Token |
| `--hostname` | Gitee 实例（默认 gitee.com） |
| `--api-url` | API 基础 URL |
| `--repo` | 目标仓库 owner/repo |
| `-o, --output` | 输出格式 table/json/csv |
| `-P, --paginate` | 自动分页获取全部 |
| `--verbose` | 显示 HTTP 请求/响应 |
| `--no-color` | 禁用颜色 |
| `--timeout` | 超时秒数（默认 30） |

## 环境变量

| 变量 | 说明 |
|------|------|
| `GITEE_TOKEN` | Access Token |
| `GITEE_HOSTNAME` | Gitee 实例 |
| `GITEE_OUTPUT` | 默认输出格式 |
| `GITEE_API_URL` | API 根地址 |

## 输出格式

```bash
# 默认 table 格式
gitee repo list

# JSON 格式
gitee repo list --output json

# CSV 格式
gitee repo list --output csv
```

## 调试

```bash
# 查看详细 HTTP 日志
gitee --verbose repo list

# 直接测试 API
gitee api GET /user

# 查看版本
gitee version
```

## API 参考

详见 [api.md](references/api.md)（端点列表、参数说明、错误码）

## 参考

- 项目地址：https://gitee.com/andershsueh/gitee-cli