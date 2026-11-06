---
name: zm-finance-news-search
description: 财经新闻搜索引擎，支持关键词搜索财经资讯和快讯，以及按股票代码查询个股新闻。囊括官媒、主流财经媒体、垂直行业网站、知名上市/非上市公司官网等多类媒体，可帮助了解最新财经事件、政策动态、行业革新、企业业务进展。当用户需要搜索财经新闻、查询事件动态、了解政策/行业/企业资讯，或查看某只股票的相关新闻时使用此 skill。
env:
  - 118599757_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取华为账号登录凭证（login-token）；若为空，或当前时间大于 ${118599757_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=118599757，skillName=zm-finance-news-search）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 118599757_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# finance-news-search

财经领域资讯搜索引擎，支持自然语言关键词搜索，覆盖官媒、主流财经媒体、垂直行业网站、知名上市/非上市公司官网等多类媒体；同时支持按股票代码精准查询个股新闻。

## 认证（小艺 loginToken → MCP token，必读）

本 Skill 采用**华为账号登录 + 新浪 MCP token 换取**：依据华为官方文档《Skill接入华为账号》与新浪侧「小艺 token 换取 MCP token」接口说明。

**完整链路：**
小艺 authorize（用户授权绑定，含手机号）→ 返回 loginToken（7 天有效）→ 用 loginToken 调 `xy_exchange_token` 换取 MCP token → 用 MCP token 调 `mcp.finance.sina.com.cn` 接口。

**① 登录凭据（loginToken）与刷新：**
1. 小艺华为账号授权后，loginToken 注入到 `/home/sandbox/.openclaw/.xiaoyienv` 文件，变量为 `{clientId}_login_token` 与 `{clientId}_login_token_expire_time`（本 skill clientId 为 `118599757`，可经 `HUAWEI_CLIENT_ID` 环境变量覆盖）。
2. 运行时由 `scripts/auth.py` 读取该文件中的 loginToken 并判断是否有效（非空 且 未过期）。
3. **若 `{clientId}_login_token` 为空，或当前时间大于 `{clientId}_login_token_expire_time`（即已过期）**：调用**一次** `huawei_id_tool` 工具（参数：`clientId=118599757`、`skillName=zm-finance-news-search`）刷新凭证（需小艺 APP / 小艺 Claw 为最新版本）。刷新成功后**重新读取** `.xiaoyienv`，再继续后续业务逻辑。**仅调用一次，不可重复调用。**

**② 换取 MCP token：**
- 用有效 loginToken 调 `POST https://ai.finance.sina.cn/skill/api/v1/xy_exchange_token`，body 为 `{"loginToken": "<loginToken>"}`。
- 响应 `result.data.token` 即为 **MCP token**（zyhub regular token），作业务接口调用凭证。
- 失败响应按 `status.code` 处理：`-1` 参数错误；`-2` loginToken 无效或过期（**先调 huawei_id_tool 刷新重试一次，仍 -2 才判定 refreshToken 失效、需重新拉起用户授权**）；`-3` 绑定信息无手机号（需重新授权）；`-4` zyhub 侧无可用 token（需在 zyhub.finance.sina.cn 申请 regular token）；`-500` 系统错误（稍后重试）。

**③ 业务接口调用：**
- `mcp.finance.sina.com.cn/api-call/<api_code>` 接口认证头统一使用 `X-Auth-Token: <MCP token>`（推荐），亦可用 query `?token=<MCP token>`。请求头由 `scripts/auth.py` 的 `get_auth_headers()` 统一构造。
- 通用请求头示例：
```
--header 'X-Auth-Token: <MCP token（由 xy_exchange_token 换取）>'
```
- **登录凭据（loginToken）只从 `.xiaoyienv` 文件读取，禁止写死到代码或固定位置。**
- 换取到的 **MCP token 会写入环境变量 `X-AUTH-TOKEN`**（`scripts/auth.py` 的 `store_mcp_token()`）供复用；`get_auth_headers()` 优先读取该环境变量（存在则直接使用，避免重复换取）。

> loginToken 只从 `.xiaoyienv` 读取；MCP token 由换取获得并存入环境变量 `X-AUTH-TOKEN`，不落盘、不外传；`scripts/auth.py` 不打印任何 token 值。

## API 信息

| API | Code | 调用地址 | 适用场景 |
| --- | --- | --- | --- |
| 新闻搜索 | `newsSearch` | `https://mcp.finance.sina.com.cn/api-call/newsSearch` | 关键词搜索深度报道 |
| 快讯搜索 | `qNewsSearch` | `https://mcp.finance.sina.com.cn/api-call/qNewsSearch` | 关键词搜索实时快讯 |
| 个股新闻 | `stockNewsSearch` | `https://mcp.finance.sina.com.cn/api-call/stockNewsSearch` | 指定股票的相关新闻 |

HTTP 方法统一为 `GET`，所有参数通过 Query String 传递，认证方式：Header `X-Auth-Token`（由 `scripts/auth.py` 统一构造）。

## 参数说明

### newsSearch / qNewsSearch（关键词搜索）

| 参数 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `keyword` | ✅ | string | 关键词，多个用英文逗号分隔，最多 10 个，每个最长 15 字符。示例：`"关税政策,贸易战"` |
| `page` | 否 | int | 页码，默认 1 |
| `num` | 否 | int | 每页条数，默认 10，最大 20 |

### stockNewsSearch（个股新闻）

| 参数 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `market` | ✅ | string | 市场代码：`cn`（沪深）、`hk`（港股）、`us`（美股） |
| `symbol` | ✅ | string | 股票代码，沪深需带前缀：`sh600519`、`sz000002`；港股/美股示例：`00700`、`AAPL` |
| `page` | 否 | string | 页码，默认 `"1"`，最大 `"100"` |
| `num` | 否 | string | 每页条数，默认 `"10"`，最大 `"20"` |

## 返回格式

**newsSearch / qNewsSearch：**
```json
{
  "result": {
    "status": { "code": 0, "msg": "成功" },
    "data": [{ "title": "新闻标题", "content": "内容摘要" }],
    "extra": { "tips": "提示", "total_num": 42 }
  }
}
```

**stockNewsSearch：**
```json
{
  "result": {
    "status": { "code": 0, "msg": "成功" },
    "data": [{ "title": "新闻标题", "url": "PC链接", "wapurl": "移动端链接" }]
  }
}
```

## 使用方式

### 何时用哪个 API

| 用户意图 | 使用 API |
| --- | --- |
| "最新财经新闻"、"政策动态"、"行业进展" | `newsSearch` |
| "今天有什么快讯"、"盘中消息" | `qNewsSearch` |
| "茅台最近的新闻"、"查一下苹果公司新闻" | `stockNewsSearch` |

用户明确提到某只股票/公司名（且为上市公司）时，优先使用 `stockNewsSearch`。若对 symbol 不确定，先用 `globalStockSearchSymbols` 接口搜索确认。

**操作步骤：**
1. 确认华为账号凭据有效（由 `scripts/auth.py` 自动完成 loginToken → MCP token 换取，见「认证」章节）
2. 判断用户意图，选择对应脚本
3. 解析并向用户展示标题和内容摘要，给出总条数

## 调用示例

```bash
# 关键词搜索新闻
python3 scripts/call_api.py --keyword "新能源汽车,补贴政策" --num 10

# 关键词搜索快讯
python3 scripts/call_qnews_search.py --keyword "美联储降息" --num 5

# 个股新闻 —— 贵州茅台（A股）
python3 scripts/call_stock_news_search.py --market cn --symbol sh600519 --num 10

# 个股新闻 —— 腾讯（港股）
python3 scripts/call_stock_news_search.py --market hk --symbol 00700 --num 10

# 个股新闻 —— 苹果（美股）
python3 scripts/call_stock_news_search.py --market us --symbol AAPL --num 10
```

## 错误处理

- **登录凭据缺失或过期（脚本启动即报错，退出码 3）**: `{clientId}_login_token` 为空或已过期，说明未授权或授权过期，调用一次 `huawei_id_tool`（clientId=118599757、skillName=zm-finance-news-search）刷新凭证后重读 `.xiaoyienv`；仅调用一次，失败则提示用户在平台重新完成华为账号授权
- **换取 MCP token 失败（脚本启动即报错，退出码 2）**: 按 `xy_exchange_token` 返回的 `status.code` 处理——`-1` 参数错误；`-2` loginToken 无效/过期（**先 huawei_id_tool 刷新并重读 `.xiaoyienv` 后重试换取一次；仍 -2 说明 refreshToken 也已失效，才需重新拉起用户授权**）；`-3` 绑定信息中无手机号（需在小艺重新授权）；`-4` zyhub 侧无 token（需在 zyhub.finance.sina.cn 申请 regular token）；`-500` 系统错误（稍后重试）
- **401 Unauthorized**: 当前 MCP token（X-Auth-Token）已失效或不存在。**本次运行作废，重新运行业务脚本即可**——MCP token 缓存是进程级的，新进程无缓存会自动重新走 `xy_exchange_token` 兑换；若兑换环节又报 -2，再按上述 loginToken 刷新流程处理
- **403 Forbidden**: 当前 token 无权访问此 API
- **404 Not Found**: api_code 不存在，检查拼写
- **5xx**: 服务端错误，建议稍后重试
