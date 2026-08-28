# Gitee API v5 端点参考

Base URL: `https://gitee.com/api/v5`

## 认证

所有请求需要 `access_token` 参数：

```bash
curl -fsS "$GITEE_API/repos/owner/repo" --data-urlencode "access_token=$GITEE_ACCESS_TOKEN"
```

## 用户

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /user | 当前用户信息 |
| GET | /users/{username} | 用户信息 |
| GET | /user/repos | 当前用户仓库列表 |
| GET | /users/{username}/repos | 指定用户仓库 |
| GET | /user/followers | 当前用户粉丝 |
| GET | /user/following | 当前用户关注 |

## 仓库 (Repos)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /user/repos | 当前用户仓库 |
| GET | /users/{owner}/repos | 他人公开仓库 |
| GET | /repos/{owner}/{repo} | 仓库详情 |
| POST | /user/repos | 创建仓库 |
| POST | /orgs/{org}/repos | 组织下创建仓库 |
| POST | /repos/{owner}/{repo}/forks | Fork 仓库 |
| PATCH | /repos/{owner}/{repo} | 编辑仓库 |
| DELETE | /repos/{owner}/{repo} | 删除仓库 |
| GET | /repos/{owner}/{repo}/branches | 分支列表 |
| GET | /repos/{owner}/{repo}/tags | 标签列表 |
| GET | /repos/{owner}/{repo}/stargazers | Star 列表 |
| GET | /repos/{owner}/{repo}/subscribers | 订阅者 |
| GET | /repos/{owner}/{repo}/contents/{path} | 文件内容 |

### 仓库参数

| 参数 | 说明 |
|------|------|
| type | all/owner/member |
| sort | created/updated/pushed/full_name |
| direction | asc/desc |
| per_page | 每页数量 (max 100) |
| page | 页码 |

## Issue

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /repos/{owner}/{repo}/issues | Issue 列表 |
| GET | /repos/{owner}/{repo}/issues/{number} | Issue 详情 |
| POST | /repos/{owner}/issues | 创建 Issue（注意：需 owner 非 repo） |
| PATCH | /repos/{owner}/{repo}/issues/{number} | 编辑 Issue |
| POST | /repos/{owner}/{repo}/issues/{number}/comments | 评论 |

### Issue 参数

| 参数 | 说明 |
|------|------|
| state | open/closed/all |
| labels | 标签（逗号分隔） |
| assignee | 指派人 |
| since | 起始时间 (ISO 8601) |

## Pull Request

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /repos/{owner}/{repo}/pulls | PR 列表 |
| GET | /repos/{owner}/{repo}/pulls/{number} | PR 详情 |
| POST | /repos/{owner}/{repo}/pulls | 创建 PR |
| PATCH | /repos/{owner}/{repo}/pulls/{number} | 编辑 PR |
| PUT | /repos/{owner}/{repo}/pulls/{number}/merge | 合并 PR |
| POST | /repos/{owner}/{repo}/pulls/{number}/reviews | 审查 PR |
| GET | /repos/{owner}/{repo}/pulls/{number}/comments | PR 评论 |
| GET | /repos/{owner}/{repo}/pulls/{number}/diff | PR diff |
| GET | /repos/{owner}/{repo}/pulls/{number}/commits | PR commits |

### PR 参数

| 参数 | 说明 |
|------|------|
| state | open/closed/all |
| head | 源分支 |
| base | 目标分支 |
| sort | created/updated |

## Gist (代码片段)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /gists | Gist 列表 |
| GET | /gists/{gist_id} | Gist 详情 |
| POST | /gists | 创建 Gist |
| PATCH | /gists/{gist_id} | 编辑 Gist |
| DELETE | /gists/{gist_id} | 删除 Gist |
| POST | /gists/{gist_id}/star | Star |
| DELETE | /gists/{gist_id}/star | Unstar |

## 组织 (Orgs)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /user/orgs | 当前用户组织 |
| GET | /orgs/{org} | 组织详情 |
| GET | /orgs/{org}/members | 成员列表 |
| GET | /orgs/{org}/repos | 组织仓库 |
| GET | /orgs/{org}/issues | 组织 Issue |

## 标签 (Labels)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /repos/{owner}/{repo}/labels | 标签列表 |
| GET | /repos/{owner}/{repo}/labels/{name} | 标签详情 |
| POST | /repos/{owner}/{repo}/labels | 创建标签 |
| PATCH | /repos/{owner}/{repo}/labels/{name} | 编辑标签 |
| DELETE | /repos/{owner}/{repo}/labels/{name} | 删除标签 |

## 搜索

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /search/repos | 搜索仓库 |
| GET | /search/issues | 搜索 Issue |
| GET | /search/users | 搜索用户 |

### 搜索参数

| 参数 | 说明 |
|------|------|
| q | 搜索关键词 |
| sort | repositories/stars/forks/updated |
| order | asc/desc |

## Release

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /repos/{owner}/{repo}/releases | Release 列表 |
| GET | /repos/{owner}/{repo}/releases/{id} | Release 详情 |
| POST | /repos/{owner}/{repo}/releases | 创建 Release |
| PATCH | /repos/{owner}/{repo}/releases/{id} | 编辑 Release |
| DELETE | /repos/{owner}/{repo}/releases/{id} | 删除 Release |

## Webhook

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /repos/{owner}/{repo}/hooks | Webhook 列表 |
| GET | /repos/{owner}/{repo}/hooks/{hook_id} | Webhook 详情 |
| POST | /repos/{owner}/{repo}/hooks | 创建 Webhook |
| PATCH | /repos/{owner}/{repo}/hooks/{hook_id} | 编辑 Webhook |
| DELETE | /repos/{owner}/{repo}/hooks/{hook_id} | 删除 Webhook |
| POST | /repos/{owner}/{repo}/hooks/{hook_id}/tests | 测试 Webhook |

## 公共参数

| 参数 | 说明 |
|------|------|
| access_token | 访问令牌（必须） |
| per_page | 每页数量 (1-100, 默认 30) |
| page | 页码 (默认 1) |

## 响应头

| 头信息 | 说明 |
|--------|------|
| X-Total-Count | 总数（用于分页） |
| Link | 分页链接 |

## 错误码

| 状态码 | 说明 |
|--------|------|
| 401 | 未授权，需要登录 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 422 | 验证失败 |

## gitee-cli 直接调用

使用 gitee-cli 可直接调用任意 API：

```bash
# GET
gitee api GET /user
gitee api GET /user/repos?per_page=5

# POST
gitee api POST /user/repos --field name=test --field private=true

# 分页
gitee api GET /user/repos --paginate
```