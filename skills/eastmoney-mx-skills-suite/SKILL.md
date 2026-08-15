---
name: eastmoney-mx-skills-suite
display_name: 妙想金融skill (MXSKILLS)
title: 妙想金融skill
description: 聚合妙想金融数据、资讯搜索、智能选股、自选股管理、模拟组合管理、综合诊股、综合诊基、股市热点发现八类能力的综合skill，统一使用华为合作侧 login-token 请求头与开放接口路径。
homepage: https://dl.dfcfs.com/m/itc4
author: 东方财富妙想团队
version: 1.0.0
env:
  - 117437361_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取账号凭证；若为空，或当前时间大于 ${117437361_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=117437361，skillName=eastmoney-mx-skills-suite）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 117437361_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
  - MX_APIKEY: "可选；适用于金融数据、资讯搜索、智能选股、自选股管理、模拟组合管理五类能力。当无法获取 117437361_login_token 且无法通过 huawei_id_tool 刷新时，作为请求头 apikey 调用接口"
---

# eastmoney-mx-skills-suite 妙想金融skill

本 Skill 聚合 8 类东方财富妙想能力：金融数据、资讯搜索、智能选股、自选股管理、模拟组合管理、综合诊股、综合诊基、股市热点发现。适合在一个统一入口下，根据用户问题自动选择最合适的金融能力进行调用。

## 能力概览

| 能力模块 | 适用场景 | 代理接口 |
|----|----|----|
| 金融数据 | 查询股票行情、财务指标、公司关系、经营数据 | `POST /api/open/huawei/skills/query-data` |
| 资讯搜索 | 查询新闻、公告、研报、政策、事件信息 | `POST /api/open/huawei/skills/news-search` |
| 智能选股 | 根据自然语言条件筛选股票 | `POST /api/open/huawei/skills/stock-screen` |
| 自选股管理 | 查询自选、添加自选、删除自选 | `POST /api/open/huawei/skills/self-select/get` `POST /api/open/huawei/skills/self-select/manage` |
| 模拟组合管理 | 查询持仓、下单、撤单、查委托、查资金 | `POST /api/open/huawei/skills/mock-trading/*` |
| 综合诊股 | 对单只 A 股做整体诊断与持仓判断 | `POST /api/open/huawei/skills/stock-analysis` |
| 综合诊基 | 对单只基金做整体诊断与持有判断 | `POST /api/open/huawei/skills/fund-analysis` |
| 股市热点发现 | 发现市场热点、热股、热门赛道 | `POST /api/open/huawei/skills/hotspot-discovery` |

## 凭据说明

- 统一使用.xiaoyienv文件 `117437361_login_token` 和 `117437361_login_token_expire_time`。
- 若 `117437361_login_token` 为空，或当前时间大于 `117437361_login_token_expire_time`，调用一次 huawei_id_tool工具（工具参数：clientId=117437361，skillName=eastmoney-mx-skills-suite） 刷新凭证。
- 刷新成功后重新读取.xiaoyienv文件，再继续后续业务逻辑。
- 所有请求头统一使用 `login-token: ${117437361_login_token}`。
- 凭据只从.xiaoyienv文件读取，禁止写死到代码或示例以外的固定位置。
- 兼容逻辑（仅适用于 §1~§5：金融数据 / 资讯搜索 / 智能选股 / 自选股管理 / 模拟组合管理）：当无法获取或无法刷新 `117437361_login_token` 时，读取环境变量 `MX_APIKEY`；存在则改为通过请求头 `apikey: ${MX_APIKEY}` 调用接口；若 `MX_APIKEY` 也不存在，提示用户前往妙想Skills页面 `https://dl.dfcfs.com/m/itc4` 创建 API Key 并将其配置为环境变量 `MX_APIKEY` 后重试。
- §6~§8（综合诊股 / 综合诊基 / 股市热点发现）仅支持 `login-token` 认证，不支持 `apikey` 兜底。

## 调用规范

1. 所有接口均使用 `POST`。
2. 所有请求头均包含 `Content-Type: application/json` 和 `login-token`；§1~§5 在 `login-token` 不可用时可改用 `apikey` 头。
3. 先根据用户意图选择能力模块，再调用对应代理接口。
4. 查询结果为空时，优先提示用户收窄或细化条件。
5. 若遇到登录状态异常，优先检查凭证是否缺失或过期，huawei_id_tool工具（工具参数：clientId=117437361，skillName=eastmoney-mx-skills-suite）；§1~§5 仍异常时，可读取 `MX_APIKEY` 改用 `apikey` 头调用，缺失则引导用户创建 API Key。

通用请求头示例：

```javascript
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}'
```

## 能力路由建议

| 用户意图 | 推荐能力 |
|----|----|
| 查询行情、估值、财务、公司关系 | 金融数据 |
| 查询最新新闻、公告、研报、政策 | 资讯搜索 |
| 根据条件找股票 | 智能选股 |
| 查自选、加自选、删自选 | 自选股管理 |
| 查持仓、买卖、撤单、查委托、查资金 | 模拟组合管理 |
| 问单只股票整体怎么样、还能不能拿 | 综合诊股 |
| 问单只基金整体怎么样、是否适合继续持有 | 综合诊基 |
| 问今日热点、最热股票、热门赛道 | 股市热点发现 |

## 1. 金融数据

适用于股票、行业、板块、指数、基金、债券、期货等多品种的行情、估值、财务及关联关系查询。

- **接口**：`POST /api/open/huawei/skills/query-data`
- **请求体**：`{"toolQuery":"贵州茅台最新价"}`
- **核心入参**：`toolQuery`，传自然语言查询内容

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/query-data' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"toolQuery":"贵州茅台最新价"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `toolQuery` | Body | 是 | 自然语言查询内容，例如股票行情、财务指标、公司信息 |

**适合的问题：**

- 贵州茅台最新价
- 东方财富近三年净利润
- 宁德时代主营业务是什么

**主要返回：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `data.questionId` | String | 单次查询唯一标识 |
| `data.dataTableDTOList` | Array | 标准化后的证券指标数据列表 |
| `data.rawDataTableDTOList` | Array | 原始未加工数据列表 |
| `data.condition` | Object | 本次查询条件 |
| `data.entityTagDTOList` | Array | 关联证券主体汇总信息 |
| `data.dataTableDTOList[].code` | String | 证券完整代码，含市场标识 |
| `data.dataTableDTOList[].entityName` | String | 证券名称，通常包含代码 |
| `data.dataTableDTOList[].title` | String | 当前指标结果标题 |
| `data.dataTableDTOList[].table` | Object | 标准化表格数据，适合渲染 |
| `data.dataTableDTOList[].rawTable` | Object | 原始表格数据 |
| `data.dataTableDTOList[].nameMap` | Object | 字段编码到业务中文名的映射 |
| `data.dataTableDTOList[].indicatorOrder` | Array | 指标列展示顺序 |
| `data.dataTableDTOList[].field` | Object | 指标元信息，如编码、名称、时间范围、粒度 |
| `data.dataTableDTOList[].entityTagDTO` | Object | 证券主体属性，如证券类型、市场、简称 |

**限制说明：**

- 避免一次查询过长时间区间的大规模明细数据，防止结果过大。

## 2. 资讯搜索

适用于搜索金融新闻、公告、研报、政策和事件影响分析等时效性信息。

- **接口**：`POST /api/open/huawei/skills/news-search`
- **请求体**：`{"query":"立讯精密的资讯"}`
- **核心入参**：`query`，传搜索内容

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/news-search' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"query":"立讯精密的资讯"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `query` | Body | 是 | 搜索内容，支持新闻、公告、研报、政策、事件等自然语言查询 |

**适合的问题：**

- 格力电器最新研报
- 商业航天板块近期新闻
- 美联储加息对 A 股影响

**主要返回：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `title` | String | 信息标题，高度概括核心内容 |
| `secuList` | Array | 关联证券列表，含代码、名称、类型等 |
| `secuList[].secuCode` | String | 证券代码 |
| `secuList[].secuName` | String | 证券名称 |
| `secuList[].secuType` | String | 证券类型，如股票、债券 |
| `trunk` | String/Object | 信息正文或结构化结果主体 |

## 3. 智能选股

适用于根据自然语言条件筛选满足要求的股票，并返回表格化结果。

- **接口**：`POST /api/open/huawei/skills/stock-screen`
- **请求体**：`{"keyword":"今日涨幅2%的股票","pageNo":1,"pageSize":20}`
- **核心入参**：`keyword`
- **可选入参**：`pageNo`、`pageSize`

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/stock-screen' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"keyword":"今日涨幅2%的股票","pageNo":1,"pageSize":20}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `keyword` | Body | 是 | 选股条件关键词，支持自然语言描述 |
| `pageNo` | Body | 否 | 页码，从 1 开始，默认 1 |
| `pageSize` | Body | 否 | 每页数量，默认 20 |

**适合的问题：**

- 今日涨幅 2% 的股票
- ROE 大于 15% 的股票
- 新能源板块中近一年净利润增长的股票

**主要返回：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `status` / `code` | String/Int | 接口全局状态，0 表示成功 |
| `message` | String | 全局提示信息 |
| `data.result.total` | Int | 符合条件的股票总数 |
| `data.result.columns` | Array | 表头列定义 |
| `data.result.dataList` | Array | 股票结果列表 |
| `data.responseConditionList` | Array | 条件解析结果 |
| `data.totalCondition` | Object | 组合筛选条件统计 |

## 4. 自选股管理

适用于查询当前账号自选股，以及通过自然语言添加或删除自选股。

### 4.1 查询自选股

- **接口**：`POST /api/open/huawei/skills/self-select/get`
- **请求体**：无

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/self-select/get' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |

**返回字段说明：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `status` / `code` | String/Int | 接口全局状态，0 表示成功 |
| `message` | String | 接口提示信息 |
| `data.title` | String | 查询标题，例如“我的自选” |
| `data.allResults.result.columns` | Array | 表格列定义 |
| `data.allResults.result.dataList` | Array | 自选股列表明细 |

### 4.2 管理自选股

- **接口**：`POST /api/open/huawei/skills/self-select/manage`
- **请求体**：`{"query":"把东方财富加入自选"}`
- **核心入参**：`query`，用自然语言描述增删动作

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/self-select/manage' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"query":"把东方财富加入自选"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `query` | Body | 是 | 自然语言操作描述，例如添加或删除自选股 |

**适合的问题：**

- 查询我的自选股列表
- 把贵州茅台添加到我的自选股列表
- 把贵州茅台从我的自选股列表删除

**主要返回：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `status` / `code` | String/Int | 接口全局状态，0 表示成功 |
| `message` | String | 接口提示信息 |
| `data.title` | String | 查询标题 |
| `data.allResults.result.columns` | Array | 表格列定义 |
| `data.allResults.result.dataList` | Array | 自选股明细 |

## 5. 模拟组合管理

适用于模拟账户持仓、交易和资金管理。使用前需先在妙想Skills页面创建并绑定模拟组合账户。

### 5.1 接口总览

| 功能 | 代理接口 | 核心入参 |
|----|----|----|
| 持仓查询 | `POST /api/open/huawei/skills/mock-trading/positions` | `moneyUnit` |
| 买入卖出 | `POST /api/open/huawei/skills/mock-trading/trade` | `type` `stockCode` `quantity` |
| 撤单 | `POST /api/open/huawei/skills/mock-trading/cancel` | `type` `orderId` `stockCode` |
| 委托查询 | `POST /api/open/huawei/skills/mock-trading/orders` | `fltOrderDrt` `fltOrderStatus` |
| 资金查询 | `POST /api/open/huawei/skills/mock-trading/balance` | `moneyUnit` |

### 5.2 股票代码格式

- 买入、卖出、撤单接口的 `stockCode` 仅支持 A 股 6 位数字，例如 `600519`、`000001`。

### 5.3 持仓查询

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/mock-trading/positions' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"moneyUnit":1}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `moneyUnit` | Body | 否 | 金额单位，`1` 表示以元为单位返回 |

**返回字段说明：**

| 字段 | 类型 | 说明 |
|----|----|----|
| `totalAssets` | Int64 | 总资产，单位元 |
| `availBalance` | Int64 | 可用余额，单位元 |
| `totalPosValue` | Int64 | 总持仓市值，单位元 |
| `posCount` | Int32 | 持仓股票数量 |
| `totalProfit` | Int64 | 总盈亏，单位元 |
| `currencyUnit` | Int32 | 币种最小面值，1=元 |

### 5.4 买入卖出

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/mock-trading/trade' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"type":"buy","stockCode":"600519","price":"180.00","quantity":"100","useMarketPrice":"false"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `type` | Body | 是 | 操作类型：`buy` 或 `sell` |
| `stockCode` | Body | 是 | 股票代码，仅支持 A 股 6 位数字 |
| `price` | Body | 否 | 委托价格，限价单时必填 |
| `quantity` | Body | 是 | 委托数量，通常为 100 股整数倍 |
| `useMarketPrice` | Body | 否 | 是否使用市价，`true` 时忽略 `price` |

- `type` 取值：`buy` 或 `sell`
- `quantity` 通常需满足 100 股整数倍规则
- `useMarketPrice=false` 时需传 `price`

### 5.5 撤单

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/mock-trading/cancel' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"type":"order","orderId":"ORD987654","stockCode":"600519"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `type` | Body | 是 | 操作类型：`order` 单笔撤单，`all` 全部撤单 |
| `orderId` | Body | 否 | 单笔撤单时必填 |
| `stockCode` | Body | 否 | 单笔撤单时必填 |

**返回字段说明：**

| 字段 | 类型 | 说明 |
|----|----|----|
| `rc` | Int32 | 返回码，0=成功 |
| `rmsg` | String | 返回信息 |
| `cancelCount` | Int32 | 成功撤单数量 |
| `failCount` | Int32 | 撤单失败数量 |
| `failList` | Array | 失败详情列表，仅失败时返回 |

- `type` 取值：`order` 或 `all`
- 单笔撤单时传 `orderId` 与 `stockCode`

### 5.6 委托查询

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/mock-trading/orders' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"fltOrderDrt":"0","fltOrderStatus":"0"}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `fltOrderDrt` | Body | 否 | 委托方向筛选，0=全部，1=买入，2=卖出 |
| `fltOrderStatus` | Body | 否 | 委托状态筛选，0=全部，2=已报，4=已成等 |

- `fltOrderDrt`：0=全部，1=买入，2=卖出
- `fltOrderStatus`：0=全部，2=已报，4=已成 等

**返回字段说明：**

| 字段 | 类型 | 说明 |
|----|----|----|
| `status` | Int/String | 接口状态 |
| `message` | String | 接口提示信息 |
| `data` | Array/Object | 委托列表结果，包含不同状态订单 |
| `data[].status` | Int | 委托状态值，见下方状态映射 |

### 5.7 资金查询

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/mock-trading/balance' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"moneyUnit":1}'
```

**请求字段说明：**

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自.xiaoyienv文件 `117437361_login_token` |
| `moneyUnit` | Body | 否 | 金额单位，`1` 表示以元为单位返回 |

**主要返回：**

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `totalAssets` | Int64 | 总资产 |
| `availBalance` | Int64 | 可用余额 |
| `frozenMoney` | Int64 | 冻结金额 |
| `totalPosValue` | Int64 | 总持仓市值 |
| `totalPosPct` | Double | 总持仓仓位百分比 |
| `currencyUnit` | Int32 | 币种最小面值，1=元 |

## 6. 综合诊股

适用于单只沪深京 A 股的泛化诊断问题，例如“这只股票怎么样”“还能不能继续拿”“当前风险和机会怎么看”。

### 6.1 触发建议

- 用户询问单只 A 股的整体判断。
- 用户询问持仓决策、风险机会或短中期看法。
- 上下文已经明确股票标的，后续继续追问“它还能买吗”“风险大吗”。

不建议用于以下场景：

- 明确要求 MACD、RSI、ROE、PE 等单指标查询。
- 多只股票横向对比。
- 港股、美股或非 A 股标的分析。

### 6.2 接口调用

- **接口**：`POST /api/open/huawei/skills/stock-analysis`
- **请求体**：`{"question":"东方财富这只股票怎么样"}`
- **核心入参**：`question`

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/stock-analysis' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"question":"东方财富这只股票怎么样"}'
```

### 6.3 入参说明

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自 `.xiaoyienv` 文件 `117437361_login_token` |
| `question` | Body | 是 | 用户原始自然语言问句，需保留股票名称与诊断意图 |

### 6.4 适合的问题

- 东方财富这只股票怎么样
- 平安银行亏了还要不要继续拿
- 中国平安现在的风险和机会怎么看
- 全面分析一下海康威视

### 6.5 主要返回

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `code` / `status` | Number/String | 接口全局状态码，字段名以实际上游返回为准 |
| `message` / `msg` | String | 接口提示信息 |
| `data` | Object | 业务数据主体 |
| `data.displayData` | String | 建议优先展示的 Markdown 诊断正文 |
| `displayData` | String | 若上游平铺返回正文，可直接展示 |

- 结果展示时优先读取 `data.displayData`，避免二次改写。
- 若只返回状态码和错误信息，不要杜撰诊断结论。

## 7. 综合诊基

适用于单只基金的泛化诊断问题，例如“这只基金怎么样”“还能不能继续持有”“收益和风险怎么看”。

### 7.1 触发建议

- 用户询问单只基金的整体判断。
- 用户询问持有决策、风险收益特征或是否适合继续定投。
- 上下文已经明确基金标的，后续继续追问“它还值得买吗”“要不要减仓”。

不建议用于以下场景：

- Python 回测、量化建模、组合优化。
- 导出净值明细、程序化数据处理。
- 多只基金横向对比。

### 7.2 接口调用

- **接口**：`POST /api/open/huawei/skills/fund-analysis`
- **请求体**：`{"question":"华夏成长混合基金怎么样"}`
- **核心入参**：`question`

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/fund-analysis' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"question":"华夏成长混合基金怎么样"}'
```

### 7.3 入参说明

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自 `.xiaoyienv` 文件 `117437361_login_token` |
| `question` | Body | 是 | 用户原始自然语言问句，需保留基金名称与诊断意图 |

### 7.4 适合的问题

- 华夏成长混合基金怎么样
- 这只基金还适合长期持有吗
- 中证白酒最近风险大不大
- 帮我全面分析一下易方达蓝筹精选

### 7.5 主要返回

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `code` / `status` | Number/String | 接口全局状态码，字段名以实际上游返回为准 |
| `message` / `msg` | String | 接口提示信息 |
| `data` | Object | 业务数据主体 |
| `data.displayData` | String | 建议优先展示的 Markdown 诊断正文 |
| `displayData` | String | 若上游平铺返回正文，可直接展示 |

- 结果展示时优先读取 `data.displayData`，避免二次改写。
- 若只返回状态码和错误信息，不要杜撰诊断结论。

## 8. 股市热点发现

适用于市场层面的热点发现问题，例如“今日热点是什么”“今天最热的股票有哪些”“最近流行哪些投资赛道”。

### 8.1 触发建议

- 用户询问市场热点、热股、热门题材、活跃方向。
- 用户想快速了解盘中或近期市场关注焦点。

不建议用于以下场景：

- 单只股票深度分析，应走综合诊股。
- 单只基金深度分析，应走综合诊基。
- 明确的单条新闻检索，应走资讯搜索。
- 指标计算、量化建模或回测。

### 8.2 接口调用

- **接口**：`POST /api/open/huawei/skills/hotspot-discovery`
- **请求体**：`{"question":"今日热点是什么"}`
- **核心入参**：`question`

```javascript
curl -X POST --location 'https://mkapi2.dfcfs.com/fsgw/api/open/huawei/skills/hotspot-discovery' \
--header 'Content-Type: application/json' \
--header 'login-token: ${117437361_login_token}' \
--data '{"question":"今日热点是什么"}'
```

### 8.3 入参说明

| 字段 | 位置 | 必填 | 说明 |
|----|----|----|----|
| `login-token` | Header | 是 | 登录凭证，取自 `.xiaoyienv` 文件 `117437361_login_token` |
| `question` | Body | 是 | 用户原始自然语言问句，需保留热点发现意图 |

### 8.4 适合的问题

- 今日热点是什么
- 今天最热的股票有哪些
- 最近流行哪些投资赛道
- 近期市场在关注什么方向

### 8.5 主要返回

| 字段路径 | 类型 | 说明 |
|----|----|----|
| `code` / `status` | Number/String | 接口全局状态码，字段名以实际上游返回为准 |
| `message` / `msg` | String | 接口提示信息 |
| `data` | Object | 业务数据主体 |
| `data.displayData` | String | 建议优先展示的 Markdown 热点正文 |
| `displayData` | String | 若上游平铺返回正文，可直接展示 |

- 结果展示时优先读取 `data.displayData`，避免二次改写。
- 若只返回状态码和错误信息，不要杜撰热点结论。

## 通用异常场景

| 异常类型 | 处理建议 |
|----|----|
| 今日调用次数已达上限 | 提示用户明日再试，或前往妙想Skills页面升级权益 |
| 查询过于频繁 | 提示稍后再试 |
| 登录状态异常 | 检查凭证是否存在且未过期，必要时刷新一次；§1~§5 仍失败时读取 `MX_APIKEY` 改用 `apikey` 头调用，若 `MX_APIKEY` 不存在则引导用户前往妙想Skills页面创建 API Key 并配置为环境变量 `MX_APIKEY` 后重试 |
| 数据结果为空 | 引导用户细化查询条件或确认账号状态 |
| 未绑定模拟组合账户 | 提示先创建并绑定模拟账户 |
