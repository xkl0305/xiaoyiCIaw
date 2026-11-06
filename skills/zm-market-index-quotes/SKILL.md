---
name: zm-market-index-quotes
description: >
  查询上证指数、沪深300、创业板指、恒生指数、纳斯达克指数等指数行情数据，
  支持涨跌幅、成交量等指标查询，返回相关指数数据结果。
  当用户询问指数数据、上证指数、沪深300、创业板指、恒生指数、纳斯达克指数、
  指数行情、指数涨跌幅等问题时，必须使用此技能。
env:
  - 118599757_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取华为账号登录凭证（login-token）；若为空，或当前时间大于 ${118599757_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=118599757，skillName=zm-market-index-quotes）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 118599757_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 指数行情查询

查询上证指数、沪深300、创业板指、恒生指数、纳斯达克指数等主要指数的实时行情数据，
支持涨跌幅、成交量、开收盘价等多维度指标。

## 认证（小艺 loginToken → MCP token，必读）

本 Skill 采用**华为账号登录 + 新浪 MCP token 换取**：依据华为官方文档《Skill接入华为账号》与新浪侧「小艺 token 换取 MCP token」接口说明。

**完整链路：**
小艺 authorize（用户授权绑定，含手机号）→ 返回 loginToken（7 天有效）→ 用 loginToken 调 `xy_exchange_token` 换取 MCP token → 用 MCP token 调 `mcp.finance.sina.com.cn` 接口。

**① 登录凭据（loginToken）与刷新：**
1. 小艺华为账号授权后，loginToken 注入到 `/home/sandbox/.openclaw/.xiaoyienv` 文件，变量为 `{clientId}_login_token` 与 `{clientId}_login_token_expire_time`（本 skill clientId 为 `118599757`，可经 `HUAWEI_CLIENT_ID` 环境变量覆盖）。
2. 运行时由 `scripts/auth.py` 读取该文件中的 loginToken 并判断是否有效（非空 且 未过期）。
3. **若 `{clientId}_login_token` 为空，或当前时间大于 `{clientId}_login_token_expire_time`（即已过期）**：调用**一次** `huawei_id_tool` 工具（参数：`clientId=118599757`、`skillName=zm-market-index-quotes`）刷新凭证（需小艺 APP / 小艺 Claw 为最新版本）。刷新成功后**重新读取** `.xiaoyienv`，再继续后续业务逻辑。**仅调用一次，不可重复调用。**

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

## 触发条件

当用户询问以下内容时必须使用此 skill：

- 指数行情、指数涨跌幅、指数数据
- 上证指数、上证综指
- 沪深300
- 创业板指
- 深证成指
- 科创50
- 恒生指数、港股指数
- 纳斯达克指数、美股指数

## 常用指数代码速查

| 指数名称 | market | symbol |
| --- | --- | --- |
| 上证指数 | `cn` | `sh000001` |
| 沪深300 | `cn` | `sh000300` |
| 深证成指 | `cn` | `sz399001` |
| 创业板指 | `cn` | `sz399006` |
| 科创50 | `cn` | `sh000688` |
| 恒生指数 | `hk` | `HSI` |
| 纳斯达克指数 | `us` | `.IXIC` |
| 道琼斯指数 | `us` | `.DJI` |
| 标普500 | `us` | `.INX` |

## API 信息

| 项目 | 值 |
| --- | --- |
| API Code | `globalStockQuoteRealtime` |
| 调用地址 | `https://mcp.finance.sina.com.cn/api-call/globalStockQuoteRealtime` |
| HTTP 方法 | `GET` |
| 认证方式 | Header `X-Auth-Token`（由 `scripts/auth.py` 统一构造） |

## 参数说明

| 参数名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `market` | string | ✅ | 市场代码：`cn`=沪深、`hk`=港股、`us`=美股、`gi`=全球指数 |
| `symbol` | string | ✅ | 股票/指数代码，如 `sh000001`、`HSI` |

> 每次请求查询**单个**指数，查询多个指数需发起多次请求。

## 使用步骤

1. 根据用户询问的指数，从速查表选择对应的 `market` 和 `symbol`
2. 若用户未指定，默认查询 A 股三大指数：上证指数、沪深300、创业板指
3. 使用 Bash 工具执行 `scripts/call_api.py`（支持批量查询，内部循环多次请求）
4. 解析返回结果，向用户展示：指数名称、当前价格、涨跌额、涨跌幅(%)、成交量、成交额

## 调用示例

### 查询单个指数

```bash
python3 /root/.claude/skills/zm-market-index-quotes/scripts/call_api.py \
    --market cn --symbol sh000001
```

### 批量查询多个指数

```bash
python3 /root/.claude/skills/zm-market-index-quotes/scripts/call_api.py \
    --batch "cn:sh000001,cn:sh000300,cn:sz399006,hk:HSI,gi:IXIC"
```

### Python 内联调用（单个）

```python
import urllib.request, urllib.parse, json
from auth import get_auth_headers

base  = "https://mcp.finance.sina.com.cn/api-call/globalStockQuoteRealtime"
url   = base + "?" + urllib.parse.urlencode({"market": "cn", "symbol": "sh000001"})

headers = {"Accept": "application/json"}
headers.update(get_auth_headers())

req = urllib.request.Request(url, headers=headers, method="GET")
with urllib.request.urlopen(req, timeout=15) as resp:
    result = json.loads(resp.read())
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

## 返回字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `symbol` | string | 指数代码 |
| `name` | string | 指数名称 |
| `price` | number | 当前价格/点位 |
| `preClose` | number | 昨收价 |
| `percent` | number | 涨跌幅（%） |
| `change` | number | 涨跌额 |
| `openPrice` | number | 今日开盘价 |
| `high` | number | 今日最高价 |
| `low` | number | 今日最低价 |
| `volume` | number | 成交量 |
| `amount` | number | 成交额 |
| `hqDate` | string | 行情日期 |
| `hqTime` | string | 行情时间 |

## 结果展示格式建议

```
📊 主要指数行情（HH:MM）

指数名称    当前点位   涨跌幅    涨跌额
上证指数    3,XXX.XX  +X.XX%   +XX.XX
沪深300     X,XXX.XX  +X.XX%   +XX.XX
创业板指    X,XXX.XX  -X.XX%   -XX.XX
恒生指数   XX,XXX.XX  -X.XX%  -XXX.XX
纳斯达克   XX,XXX.XX  +X.XX%   +XX.XX
```

## 错误处理

- **登录凭据缺失或过期（脚本启动即报错，退出码 3）**: `{clientId}_login_token` 为空或已过期，说明未授权或授权过期，调用一次 `huawei_id_tool`（clientId=118599757、skillName=zm-market-index-quotes）刷新凭证后重读 `.xiaoyienv`；仅调用一次，失败则提示用户在平台重新完成华为账号授权
- **换取 MCP token 失败（脚本启动即报错，退出码 2）**: 按 `xy_exchange_token` 返回的 `status.code` 处理——`-1` 参数错误；`-2` loginToken 无效/过期（**先 huawei_id_tool 刷新并重读 `.xiaoyienv` 后重试换取一次；仍 -2 说明 refreshToken 也已失效，才需重新拉起用户授权**）；`-3` 绑定信息中无手机号（需在小艺重新授权）；`-4` zyhub 侧无 token（需在 zyhub.finance.sina.cn 申请 regular token）；`-500` 系统错误（稍后重试）
- **401 Unauthorized**: 当前 MCP token（X-Auth-Token）已失效或不存在。**本次运行作废，重新运行业务脚本即可**——MCP token 缓存是进程级的，新进程无缓存会自动重新走 `xy_exchange_token` 兑换；若兑换环节又报 -2，再按上述 loginToken 刷新流程处理
- **403 Forbidden**: 当前 token 无权访问此 API
- **返回数据为空**: 可能为非交易时间，说明当前市场已休市
- **5xx**: 服务端错误，建议稍后重试
