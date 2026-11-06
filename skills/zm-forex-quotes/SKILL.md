---
name: zm-forex-quotes
description: 查询实时外汇汇率行情，支持单货币对查询和批量多货币对查询。返回买入价、卖出价、涨跌幅、52周高低价等核心数据，适用于汇率行情查询、carry策略分析、货币对筛选等场景。当用户询问外汇汇率、货币对行情、汇率涨跌、买入价卖出价等问题时使用此 skill。
env:
  - 118599757_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取华为账号登录凭证（login-token）；若为空，或当前时间大于 ${118599757_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=118599757，skillName=zm-forex-quotes）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 118599757_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 外汇实时汇率行情

查询指定货币对的实时汇率行情，支持单货币对精确查询和批量多货币对查询。

## 认证（小艺 loginToken → MCP token，必读）

本 Skill 采用**华为账号登录 + 新浪 MCP token 换取**：依据华为官方文档《Skill接入华为账号》与新浪侧「小艺 token 换取 MCP token」接口说明。

**完整链路：**
小艺 authorize（用户授权绑定，含手机号）→ 返回 loginToken（7 天有效）→ 用 loginToken 调 `xy_exchange_token` 换取 MCP token → 用 MCP token 调 `mcp.finance.sina.com.cn` 接口。

**① 登录凭据（loginToken）与刷新：**
1. 小艺华为账号授权后，loginToken 注入到 `/home/sandbox/.openclaw/.xiaoyienv` 文件，变量为 `{clientId}_login_token` 与 `{clientId}_login_token_expire_time`（本 skill clientId 为 `118599757`，可经 `HUAWEI_CLIENT_ID` 环境变量覆盖）。
2. 运行时由 `scripts/auth.py` 读取该文件中的 loginToken 并判断是否有效（非空 且 未过期）。
3. **若 `{clientId}_login_token` 为空，或当前时间大于 `{clientId}_login_token_expire_time`（即已过期）**：调用**一次** `huawei_id_tool` 工具（参数：`clientId=118599757`、`skillName=zm-forex-quotes`）刷新凭证（需小艺 APP / 小艺 Claw 为最新版本）。刷新成功后**重新读取** `.xiaoyienv`，再继续后续业务逻辑。**仅调用一次，不可重复调用。**

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

### 1. 单货币对查询 — `forexQuoteLatest`

| 项目 | 值 |
| --- | --- |
| API Code | `forexQuoteLatest` |
| 调用地址 | `https://mcp.finance.sina.com.cn/api-call/forexQuoteLatest` |
| HTTP 方法 | `GET`（参数通过 Query String 传递） |
| 认证方式 | Header `X-Auth-Token`（由 `scripts/auth.py` 统一构造） |

**参数说明：**

| 参数名 | 必填 | 格式 | 示例 | 描述 |
| --- | --- | --- | --- | --- |
| symbol | 是 | 全大写字符串 | `USDCNY` | 货币对代码，如 `EURUSD`、`GBPUSD`、`USDJPY` 等 |

**返回字段：**

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| updateTime | string | 数据更新时间 |
| symbol | string | 货币对代码 |
| tickTime | string | 报价时间 |
| askPrice | number | 卖出价（卖出基础货币的价格） |
| bidPrice | number | 买入价（买入基础货币的价格） |
| price | number | 当前现价 |
| priceAdjustFactor | number | 价格调整因子 |
| open | number | 开盘价 |
| high | number | 最高价 |
| low | number | 最低价 |
| close | number | 收盘价 |
| pctChg | number | 涨跌幅 |
| chg | number | 涨跌额 |
| yestTradeClose | number | 昨日收盘价 |
| high52Week | number | 52周最高价 |
| low52Week | number | 52周最低价 |

### 2. 批量货币对查询 — `forexQuotesBatch`

| 项目 | 值 |
| --- | --- |
| API Code | `forexQuotesBatch` |
| 调用地址 | `https://mcp.finance.sina.com.cn/api-call/forexQuotesBatch` |
| HTTP 方法 | `GET`（参数通过 Query String 传递） |
| 认证方式 | Header `X-Auth-Token`（由 `scripts/auth.py` 统一构造） |

**参数说明：**

| 参数名 | 必填 | 格式 | 示例 | 描述 |
| --- | --- | --- | --- | --- |
| from | 是 | ISO 4217 三字母代码 | `USD` | 基础货币代码 |
| to | 是 | 逗号分隔的货币代码 | `CNY,JPY,EUR` | 目标货币代码列表 |

**返回字段：** 与单货币对查询一致，返回数组，每个元素对应一个货币对。

## 使用方式

1. 确认华为账号凭据有效（由 `scripts/auth.py` 自动完成 loginToken → MCP token 换取，见「认证」章节）
2. 根据用户请求选择合适的查询方式：
   - **查询单个货币对**：使用 `scripts/call_api.py`，传入 `--symbol` 参数
   - **批量查询多个货币对**：使用 `scripts/call_forexQuotesBatch.py`，传入 `--from` 和 `--to` 参数
3. 解析并向用户展示返回结果

若用户提供的标的信息不明确（如仅说"美元汇率"、"欧元对日元"等），先调用 `globalStockSearchSymbols` 搜索并向用户确认货币对代码，再调用本接口。该接口支持股票、基金、ETF、指数、债券等多种金融标的搜索。

## 调用示例

### 单货币对查询

```bash
# 查询 USDCNY 实时汇率
python3 scripts/call_api.py --symbol USDCNY

# 查询 EURUSD 实时汇率
python3 scripts/call_api.py --symbol EURUSD
```

### 批量查询

```bash
# 查询 USD 兑 CNY、JPY、EUR 的汇率
python3 scripts/call_forexQuotesBatch.py --from USD --to CNY,JPY,EUR

# 查询 EUR 兑 USD、GBP 的汇率
python3 scripts/call_forexQuotesBatch.py --from EUR --to USD,GBP
```

### 直接 curl 调用

```bash
# 单货币对
curl -s -H "X-Auth-Token: <MCP token（由 xy_exchange_token 换取）>" \
  "https://mcp.finance.sina.com.cn/api-call/forexQuoteLatest?symbol=USDCNY"

# 批量查询
curl -s -H "X-Auth-Token: <MCP token（由 xy_exchange_token 换取）>" \
  "https://mcp.finance.sina.com.cn/api-call/forexQuotesBatch?from=USD&to=CNY,JPY"
```

## 常用货币对参考

| 货币对 | 含义 |
| --- | --- |
| USDCNY | 美元/人民币 |
| EURUSD | 欧元/美元 |
| GBPUSD | 英镑/美元 |
| USDJPY | 美元/日元 |
| AUDUSD | 澳元/美元 |
| USDCAD | 美元/加元 |
| USDCHF | 美元/瑞郎 |
| NZDUSD | 新西兰元/美元 |
| EURGBP | 欧元/英镑 |
| EURJPY | 欧元/日元 |

## 错误处理

- **登录凭据缺失或过期（脚本启动即报错，退出码 3）**: `{clientId}_login_token` 为空或已过期，说明未授权或授权过期，调用一次 `huawei_id_tool`（clientId=118599757、skillName=zm-forex-quotes）刷新凭证后重读 `.xiaoyienv`；仅调用一次，失败则提示用户在平台重新完成华为账号授权
- **换取 MCP token 失败（脚本启动即报错，退出码 2）**: 按 `xy_exchange_token` 返回的 `status.code` 处理——`-1` 参数错误；`-2` loginToken 无效/过期（**先 huawei_id_tool 刷新并重读 `.xiaoyienv` 后重试换取一次；仍 -2 说明 refreshToken 也已失效，才需重新拉起用户授权**）；`-3` 绑定信息中无手机号（需在小艺重新授权）；`-4` zyhub 侧无 token（需在 zyhub.finance.sina.cn 申请 regular token）；`-500` 系统错误（稍后重试）
- **401 Unauthorized**: 当前 MCP token（X-Auth-Token）已失效或不存在。**本次运行作废，重新运行业务脚本即可**——MCP token 缓存是进程级的，新进程无缓存会自动重新走 `xy_exchange_token` 兑换；若兑换环节又报 -2，再按上述 loginToken 刷新流程处理
- **403 Forbidden**: 当前 token 无权访问此 API
- **404 Not Found**: api_code 不存在，检查拼写
- **5xx**: 服务端错误，建议稍后重试或联系管理员
