---
name: ai-zhangle-skills
description: 华泰证券「AI涨乐」金融服务套件，覆盖 A 股模拟交易、金融分析与资讯、金融指标与行情查询、条件选股、自选股管理 5 大模块。当用户的意图属于"查行情/指标/估值"、"个股或大盘分析诊断"、"按条件选股"、"加自选/查自选"或"A 股模拟盘交易（行情/账户/持仓/下单/撤单/查委托与成交）"中任一类时调用本套件。
env:
  - 117860613_login_token: "从 /home/sandbox/.openclaw/.xiaoyienv 文件中读取账号凭证；若为空，或当前时间大于 ${117860613_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool 工具（工具参数：clientId=117860613，skillName=ai-zhangle-skills）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 117860613_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# ai-zhangle-skills

华泰证券「AI涨乐」面向华为小艺的统一金融服务套件，5 个模块对应 5 个 Python 脚本，统一从同一份华为账号凭证发起调用。

## 凭证管理

所有子模块共享同一套华为账号绑定凭据：

- 统一从 `/home/sandbox/.openclaw/.xiaoyienv` 读取 `117860613_login_token` 和 `117860613_login_token_expire_time`。
- 若 `117860613_login_token` 为空，或当前时间大于 `117860613_login_token_expire_time`，先调用一次 `huawei_id_tool` 刷新凭证，工具参数为 `clientId=117860613`、`skillName=ai-zhangle-skills`。
- 刷新成功后重新读取 `.xiaoyienv` 文件，再继续调用对应脚本。
- 脚本只从 `117860613_login_token` 读取鉴权值，不使用本地 config 文件存储凭证。

安全要求：

- 只从 `.xiaoyienv` 读取账号凭证，不要在代码、提示词、日志或输出中明文暴露凭证。
- 若缺少凭证、登录过期或接口返回鉴权类错误（如 `code = -2` / `1001` / `5002` / HTTP 401/403）：先刷新 `117860613_login_token`；必要时调用 `huawei_id_tool`（`clientId=117860613`、`skillName=ai-zhangle-skills`）获取新凭证，再重新读取 `.xiaoyienv` 并重试一次。
- 不要把 `117860613_login_token` 写入示例命令、URL、查询参数或输出文件。

## 调用前的总体路由

收到请求后，先按下表把用户意图归到一个模块，再执行对应章节：

| 用户意图 | 路由 |
|---|---|
| "看××最新价 / 涨跌幅 / 成交量 / 换手率 / PE / PB / 财务指标"——查具体数值或对比表现 | **模块三 query_indicator** |
| "分析一下××"、"诊断××"、"××为什么涨/跌"、"今天大盘怎么样"、"对比 A 和 B"、"××最近资讯利好利空" | **模块二 financial_analysis** |
| "找/筛××板块的"、"PE<20 且涨幅>5% 的股票"、"业绩超预期的"、"推荐几只好股票"——按条件选标的 | **模块四 select_stock** |
| "把××加自选"、"我自选股有哪些"、"看看××分组" | **模块五 watchlist_management** |
| "买/卖××"、"我有多少钱"、"我持仓"、"撤单"、"挂单"、"成交记录"——A 股**模拟盘**交易/账户操作 | **模块一 a_share_paper_trading** |

边界辨析：

- "贵州茅台怎么样" → **模块二**（个股分析），不要走选股或指标。
- "PE 低于 20 的股票有哪些" → **模块四**（条件选股），不要走指标查询。
- "茅台 PE 现在多少" → **模块三**（指标查询），不要走分析。
- "把茅台加自选并看看走势" → 先 **模块五** 加自选，再 **模块三** 查走势；按用户主意图分两次调用。
- "帮我买入××" → **模块一**（仅模拟盘）；本套件不涉及任何真实资金交易。
- 纯编程问题、天气、体育等非金融问题：不调用本套件任何模块。

## 通用约定

- 所有脚本以 `python3 {baseDir}/<script>.py <tool> [args]` 的形式调用，结果以 JSON 形式打印到 stdout。
- 字段命名：**小驼峰**（`stockCode`、`orderType`、`availableBalance` 等）。
- 多个脚本之间不共享业务数据，但共用同一份登录凭证。

### 响应结构（所有模块统一）

成功：

```json
{ "ok": true, "data": { ... }, "error": null }
```

失败：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": 1001,
    "message": "面向用户的中文说明",
    "category": "auth | validation | business | network",
    "retriable": false,
    "hint": "下一步该怎么做"
  }
}
```

`error.code` 是数字或字符串，**不要据此判断错误类型**，要看 `error.category` 与 `error.message`：

| category | 含义 | 处理 |
|---|---|---|
| `auth` | 密钥失效或未授权（典型如后端 `code=1001` "API Key 无效或已删除"） | 不重试，按"凭证管理"刷新 `117860613_login_token`，必要时调用 `huawei_id_tool` |
| `validation` | 参数/资金/持仓不合规 | 不重试，按 `hint` 引导用户调整 |
| `business` | 非交易时段、停牌、涨跌停、无数据等业务限制 | 不立即重试，告知业务限制 |
| `network` | 网络/超时/5xx | 临时问题，可稍后再试 |

成功时按用户提问角度组织 `data` 的回复，不要把所有字段一股脑念给用户。

---

## 模块一：A 股模拟交易（a_share_paper_trading.py）

A 股**模拟盘**全套交易能力：行情查询、账户/持仓查询、买卖下单、撤单、委托与成交查询。仅 A 股、仅模拟盘，不涉及真实资金；不适用于港股/美股/期货/外汇、真实资金交易。

### 字段单位与枚举

- 金额：**元**（float，2 位小数）；价格：**元/股**（float，最小变动价位由后端按品种校验）；数量：**股**（int，最小申报数量与递增单位由后端按品种校验）。
- 比例：返回字段中 `xxxPct` 一律为**百分数**（`5.20` 表示 5.20%，不是 0.052）。
- 时间：ISO 8601 含时区。
- 股票代码：6 位数字字符串。
- 枚举：`exchange`=`SH/SZ/BJ`，`direction`=`buy/sell`，`orderType`=`limit/market`，`orderStatus`=`pending/partialFilled/filled/cancelled/rejected`。

### 股票标识规则（必读）

A 股不同市场可能存在相同代码（如 `000001` 在 SH 是上证指数，在 SZ 是平安银行），单凭代码无法唯一确定标的。故：

- **交易类**（`submitOrder`）：必须传 `exchange`。
- **查询过滤类**（`cancelAllPendingOrders` / `listPendingOrders` / `listTradeHistory`）：传了 `stockCode` 就必须同时传 `exchange`，否则两者都不传。
- 用户只给名称（"茅台"、"宁德"）或拼音简称时，**先 `searchStock` 解析为 `(stockCode, exchange)` 再调用后续工具**。不要凭印象编代码。

### 工具

#### searchStock — 按名称/代码/拼音搜索股票

- **何时调用**：用户提到股票时只给了名称或拼音/简称，而后续工具需要 `stockCode`。
- **参数**：`query`（股票名称、代码、拼音首字母）。
- **返回**：`results[]`（每条 `stockCode, stockName, exchange`）、`totalCount`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py searchStock --query <query>`
- **结果策略**：1 条 → 直接采用；多条 → 列出候选向用户确认，不要替用户猜；0 条 → 告知找不到，不要编造代码。

#### getQuote — 实时行情

- **何时调用**：用户问股价；下单前确认参考价；用户提"涨停/跌停"需具体价格。
- **参数**：`stockCode`、`exchange`（必填）。
- **返回**：`stockName, currentPrice, prevClose, limitUp, limitDown, bidPrice1, askPrice1, change, isSuspended`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py getQuote --stock-code <code> --exchange <SH|SZ|BJ>`

#### getAccountBalance — 账户资金总览

- **何时调用**：用户问余额/可用资金/盈亏概况；评估购买力。
- **参数**：无。
- **返回**：`totalAssets, availableBalance, frozenAmount, totalPositionValue, positionRatio, dayProfit, dayProfitPct, totalProfit, totalProfitPct, initialCapital`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py getAccountBalance`
- **复述提示**：问"还有多少钱"重点说 `availableBalance`；问"今天怎么样"重点说 `dayProfit/dayProfitPct`；问"总情况"`totalAssets + dayProfit + positionRatio` 即可，不必把所有字段都念一遍。

#### getPositions — 所有持仓明细

- **何时调用**：用户问"我的持仓"、"哪些股票亏/赚"；卖出前确认持有数量。
- **参数**：无。
- **返回**：`positions[]`（每条 `stockCode, stockName, quantity, availableQuantity, costPrice, currentPrice, marketValue, profit, profitPct, dayProfit, positionPct`），`totalCount, totalMarketValue, totalProfit`，按盈亏比例倒序。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py getPositions`
- **关键**：`availableQuantity` 是当前可卖数量（受结算规则约束，可能小于 `quantity`），卖出按此字段判断。
- **复述提示**：问"哪些亏"只列 `profit<0` 的；问"持仓概况"报数量、总市值、整体盈亏，重点持仓提一两个；不要每次把所有持仓全部念一遍。

#### submitOrder — 提交买卖委托

- **何时调用**：用户表达明确买卖意图。下单前必须知道：方向、股票代码（含 `exchange`）、数量、`orderType`；`limit` 单还需 `price`。**用户没说数量时必须先问，不要替用户决定。**
- **参数**：`direction`（`buy/sell`）、`stockCode`、`exchange`、`quantity`、`orderType`（`limit` 默认 / `market`）、`price`（`limit` 必填，`market` 时忽略）。
- **返回**：`orderId, stockName, price, quantity, estimatedAmount, estimatedFee, status, submitTime`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py submitOrder --direction <buy|sell> --stock-code <code> --exchange <SH|SZ|BJ> --quantity <N> [--order-type <limit|market>] [--price <P>]`
- **典型业务错误**（具体以 `error.message` 与 `error.hint` 为准）：可用资金不够 / 可卖数量不够 / 数量不符合品种申报规则 / 价格不符合最小变动价位 / 价格超出涨跌停 / 当前非交易时段 / 股票停牌。

#### cancelOrder — 按单号撤单

- **何时调用**：用户指定撤单且有 `orderId`；用户描述了具体委托但无 id 时，先 `listPendingOrders` 找 id 再调用。
- **参数**：`orderId`。
- **返回**：`orderId, previousStatus, currentStatus, cancelledQuantity, cancelTime`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py cancelOrder --order-id <orderId>`
- 仅 `pending` / `partialFilled` 状态可撤。

#### cancelAllPendingOrders — 一键撤所有未成交

- **何时调用**：用户说"撤所有"、"一键撤单"、"撤掉所有 X 股票/买单/卖单"。
- **参数**：`stockCode` + `exchange`（同进同退）、`direction`，皆可选。
- **返回**：`cancelledCount, failedCount, cancelledOrders[], failedOrders[]`。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py cancelAllPendingOrders [--stock-code <code> --exchange <SH|SZ|BJ>] [--direction <buy|sell>]`
- **关键**：`ok=true` 时也可能 `failedCount > 0`（典型原因：撤单瞬间委托已成交），如实告知，不是错误。
- **复述提示**：报成功撤单数；`failedCount > 0` 时说明失败原因；无失败时不必赘述。

#### listPendingOrders — 当日未成交/部分成交委托

- **何时调用**：用户问"挂单"、"未成交"、"我的委托"；为 `cancelOrder` 找 id。
- **参数**：`stockCode` + `exchange`（同进同退）、`direction`，皆可选。
- **返回**：`orders[]`（每条 `orderId, stockCode, stockName, exchange, direction, orderType, price, quantity, filledQuantity, status, submitTime`），按提交时间倒序。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py listPendingOrders [--stock-code <code> --exchange <SH|SZ|BJ>] [--direction <buy|sell>]`
- **复述提示**：先报总数；委托少（≤3）时逐一简述（股票名+方向+数量+价格+状态）；多则只报总数和概要。`partialFilled` 记得提 `filledQuantity`。

#### listTradeHistory — 历史成交记录

- **何时调用**：用户问"历史成交"、"交易记录"、"什么时候买/卖的 X"。
- **参数**：`startDate`（YYYY-MM-DD，必填）、`endDate`（YYYY-MM-DD，必填，跨度 ≤ 90 天）、`stockCode` + `exchange`（同进同退）、`direction`。
- **返回**：`trades[]`（每条 `orderId, stockCode, stockName, exchange, direction, filledPrice, filledQuantity, filledAmount, fee, filledTime`），`totalCount, totalBuyAmount, totalSellAmount, totalFee`，按成交时间倒序。
- **执行**：`python3 {baseDir}/a_share_paper_trading.py listTradeHistory --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> [--stock-code <code> --exchange <SH|SZ|BJ>] [--direction <buy|sell>]`
- **时间范围默认推断**："最近"→ 7 天；"本月"→ 当月 1 日至今；"今年"→ 最近 90 天，并提示用户可分批查询。

### 调用模式速查

| 用户意图 | 调用路径 |
|---|---|
| "茅台/600519 现价多少" | （名称需先 `searchStock`）→ `getQuote` |
| "我有多少钱 / 今天赚亏" | `getAccountBalance` |
| "我持仓 / 哪些亏了" | `getPositions` |
| "买/卖 N 股 X 价 Y" | （名称需先 `searchStock`）→ `submitOrder` |
| "我能买多少 X" | （需要时 `searchStock`）+ `getAccountBalance` + `getQuote`，自行计算 |
| "撤掉那笔买茅台的" | `listPendingOrders` 找 id → `cancelOrder` |
| "全撤了" | `cancelAllPendingOrders` |
| "我有哪些挂单" | `listPendingOrders` |
| "本月成交了几笔" | `listTradeHistory`（按当月） |

---

## 模块二：金融分析与资讯（financial_analysis.py）

针对个股/ETF/板块的分析诊断，以及覆盖大盘、行业、多标的对比与金融资讯的市场洞察。

### 触发条件

用户问题属于以下任一类时使用本模块（详细分类示例参见 `references/CATEGORIES.md`）：

- **个股分析**：综合分析、投资价值、基本面、财报解读、事件分析、股价走势、机构观点、估值、建仓/出货时机、投资逻辑。
- **大盘分析（A 股 / 港美股）**：走势预测/分析、资金流向、涨跌归因、事件催化、热门板块、估值、复盘。
- **概念/板块/行业/ETF 分析**：综合分析、投资价值、增长前景、生命周期、事件影响、走势分析与预测、资金面、机构观点、估值。
- **多标的对比**：同行业 / 跨行业综合对比、基本面 / 财务 / 走势 / 指标对比。
- **金融资讯查询**：个股或多股的新闻资讯、利好利空分类、指定时间范围内的资讯汇总、板块/行业/市场新闻聚合。
- **宏观事件与选股/荐股**：基于宏观经济、地缘政治、政策变化等事件分析其对金融市场的影响。
- **个股分析诊断**。

### 不应触发

- 纯编程或技术开发问题。
- 金融条件选股（如"帮我找 PE 低于 20 的股票"）→ 走 **模块四**。
- 涉及具体交易操作指令（如"帮我买入××"）→ 走 **模块一**。
- 非金融类的新闻查询（天气、体育等）。

### 工具

#### diagnosisStock — 个股/ETF/板块分析诊断

- **何时调用**：用户**明确**要求"分析诊断"、"诊断报告"，且对象为单一个股/ETF/板块。
- **参数**：`query`（用户原始问题，必填）。
- **执行**：`python3 {baseDir}/financial_analysis.py diagnosisStock --query <query>`

#### marketInsight — 市场洞察（不属于分析诊断的其他金融问题）

- **何时调用**：大盘分析、板块/行业分析、多标的对比、金融资讯、宏观事件解读等。
- **参数**：`query`（用户原始问题，必填）。
- **执行**：`python3 {baseDir}/financial_analysis.py marketInsight --query <query>`

成功时直接展示 `data.answer`（已是结构化 Markdown）。接口耗时较长（最长可达数分钟），保留脚本返回的 `answer` 原文，不要另行补充分析或删减。

### 调用模式速查

| 用户意图 | 类别 | 调用路径 |
|---|---|---|
| "帮我分析一下比亚迪" | 分析诊断 | `diagnosisStock` |
| "帮我诊断招商中证 1000 指数增强 A" | 分析诊断 | `diagnosisStock` |
| "今天大盘为什么跌了" | 市场洞察 | `marketInsight` |
| "对比东方财富和华泰证券" | 市场洞察 | `marketInsight` |
| "整理长江电力最近 48 小时利好利空资讯" | 市场洞察 | `marketInsight` |

---

## 模块三：金融指标与行情查询（query_indicator.py）

金融指标、行情数据、财务估值等"查数值/看指标/对比表现"类问题的统一入口。

### 触发条件

- **实时与历史行情**：股票/债券/基金/指数/市场/板块的最新价、走势、开收盘、最高/最低、涨跌幅、成交量、成交额、换手率、振幅。
- **基础原子指标**：流通市值、研报目标价、技术面支撑位/压力位、止盈止损位等。
- **财务与估值**：净利润、营业收入、PE、PB 等。
- **聚合与关联查询**："股价走势"（多项行情指标关联）、多标的横向对比，或"行情/表现如何/估值高低"等模糊表述。

### 不应触发

- 纯编程或技术开发问题。
- 金融条件选股（如"帮我找 PE 低于 20 的股票"）→ 走 **模块四**。
- 具体交易指令（如"帮我买入××"）→ 走 **模块一**。
- 非金融类查询（天气、体育等）。
- 个股分析诊断 → 走 **模块二**。

### 工具

#### queryIndicator — 查询金融指标/行情/估值

- **参数**：`query`（保留用户原始表述，必填）。
- **执行**：`python3 {baseDir}/query_indicator.py queryIndicator --query <query>`

**铁律（必须严格遵守）**：

- **不要拆分多次调用**："南京中达昨天和前天的最高价"、"领益智造、国轩高科当日收益情况" → 单次传入完整问句，不要为每个标的或每个指标拆分多次调用。
- **不要替换参数**：禁止把"昨天"换成具体日期，禁止缩写股票名称，禁止在 `query` 中插入由你计算的中间值。
- **不要补充解释**：`query` 仅包含用户原话，不要追加任何额外说明。

### 调用示例

| 用户问题 | 调用方式 |
|---|---|
| "看看华泰证券最新价" | `queryIndicator --query "看看华泰证券最新价"` |
| "南京中达昨天和前天的最高价" | `queryIndicator --query "南京中达昨天和前天的最高价"` |
| "隆基股份和通威股份今天的换手率和成交额" | `queryIndicator --query "隆基股份和通威股份今天的换手率和成交额"` |
| "国际实业和泰山石油的换手率" | `queryIndicator --query "国际实业和泰山石油的换手率"` |

---

## 模块四：条件选股（select_stock.py）

按自然语言筛选条件查询符合条件的股票/ETF/基金等金融标的。

### 触发条件

用户意图属于以下任一类时使用本模块：

- **行业/板块筛选**："白酒行业"、"半导体"、"AI 概念"、"新能源"等。
- **财务指标筛选**："市盈率小于 20"、"净利润增长率大于 30%"、"ROE>15%" 等。
- **技术指标筛选**："均线金叉"、"MACD 底背离"、"连板股票" 等。
- **行情数据筛选**："涨幅超过 5%"、"主力净流入超过 1 亿"、"换手率大于 10%" 等。
- **业绩超预期筛选**："业绩超预期"、"一季报财报超预期" 等。
- **组合多条件**：上述条件的任意组合。
- **主观推荐类**："推荐几只股票"、"有什么好的 ETF" 等。

### 不应触发

- 个股分析（如"贵州茅台怎么样"）→ 走 **模块二**。
- 查具体指标数值（如"茅台 PE 多少"）→ 走 **模块三**。

### 工具

#### selectStock — 条件选股

- **参数**：`query`（筛选条件查询语句，必填）。
- **返回**：`data.result`（Markdown 格式的选股结果）。
- **执行**：`python3 {baseDir}/select_stock.py selectStock --query <query>`

### 执行流程（必须严格遵守）

> **关键约束：禁止向用户反问。** 收到请求后立即直接调用脚本，遇到歧义按"查询改写规则"自行推断，不得暂停去问用户。

1. **第一次调用**：将用户**原始问句**直接作为 `--query` 传入，不做任何改写。
2. **若无结果**：按下方"查询改写规则"将原始问句改写为清晰、无歧义的查询语句，再调一次。
3. **若仍无结果**：停止重试，告知用户"未检索到符合条件的标的"。
4. **结果展示**：标的数量不超过 **10 个**；**严禁修改返回的 Markdown 格式**。

### 查询改写规则（仅在第一次无结果时使用）

1. **逻辑关系消歧（OR vs AND）**：同一维度多个值（多个行业）通常为 **OR**；跨维度多个条件（行业 + 市盈率 + 涨幅）通常为 **AND**；改写时必须用"或"/"且"明确标注。
2. **时间条件丢失或泛化**：完整保留所有时间限定；"上周五"、"本周一"等相对时间按当前日期推算成具体日期写入。
3. **隐含排序与排名条件**：从上下文推断排序字段、方向及取前 N 条数量限制并写明。
4. **复合条件拆解不完整**：拆为独立子条件，每个覆盖一个维度，用"且"/"或"连接。
5. **指代消解**：把代词替换为明确指代实体或条件集合，使查询自包含。
6. **否定与排除**：用"排除"、"不包含"等显式否定词标注。
7. **数值单位与区间歧义**：按金融常识补全单位（市值"亿元"、股价"元"），区间默认闭区间。
8. **连续性与累计性**："连续"的时间单位为交易日、补全截止日期，并区分"连续每天都满足"与"累计/合计满足"。

---

## 模块五：自选股管理（watchlist_management.py）

支持**添加股票到自选**、**查询自选股列表**两类操作。

### 触发条件

#### 添加类关键词

- "将×加入自选"、"把×加到自选股"、"添加×到自选"、"关注×股票"、"自选股添加×"、"收藏×股票"。

#### 查看类关键词

- "查看我的自选股"、"我的自选股有哪些"、"自选股列表"、"看一下我收藏的股票"、"看看自选里的股票"。

### 不应触发

- 从自选股删除、调整分组（本模块当前不支持）。
- 股票分析、买卖交易、行情查询等非自选操作 → 走对应模块。

### 工具

#### addWatchlist — 添加自选

- **参数**：`query`（用户加自选的请求文本，必填）；`group`（分组名，可选，默认 `"默认组"`）。
- **返回**：`data.result`（操作结果文本）、`data.stocks`（添加的股票信息）。
- **执行**：`python3 {baseDir}/watchlist_management.py addWatchlist --query <query> [--group <group>]`

#### getWatchlist — 查询自选

- **参数**：`query`（用户查自选的请求文本，必填）。
- **返回**：`data.result`（查询结果文本）、`data.answer`（自选股列表详情，前 20 条）。
- **执行**：`python3 {baseDir}/watchlist_management.py getWatchlist --query <query>`

### 执行流程

1. **意图判断与拆分**：识别请求是「添加自选」还是「查看自选」；同时包含两类时拆分后分别执行。
2. **添加流程**：按用户提到的分组拆分请求；未提分组则用 `"默认组"`。
   - "紫金矿业最近行情怎么样？帮我加个自选" → `query="将紫金矿业加入自选"`、`group="默认组"`。
   - "将华泰证券、贵州茅台分别加入证券和白酒分组" → 拆 2 个请求：① `query="将华泰证券加入证券自选分组"`、`group="证券"`；② `query="将贵州茅台加入白酒自选分组"`、`group="白酒"`。
3. **查看流程**：直接调用 `getWatchlist`。
4. **结果展示**：直接转发脚本返回内容，不擅自总结或删减；查询结果若被截断（>20 条），需明确告知用户超出部分被截断。

### 调用模式速查

| 用户意图 | 调用路径 |
|---|---|
| "将华泰证券加入自选" | `addWatchlist`（默认组） |
| "把茅台加到白酒分组" | `addWatchlist`（`group=白酒`） |
| "将华泰证券、贵州茅台分别加入证券和白酒分组" | 拆为 2 次 `addWatchlist`（证券组、白酒组） |
| "我的自选股有哪些" | `getWatchlist` |
| "查看新能源分组" | `getWatchlist` |
| "把比亚迪加到新能源分组，再看看这个分组有啥" | 先 `addWatchlist`（新能源组），再 `getWatchlist`（"查看新能源分组"） |

---

## 失败处理

- `.xiaoyienv` 不存在、缺少 `117860613_login_token`、登录过期或接口返回鉴权类错误（`code=1001` "API Key 无效或已删除"、`code=-2`、`code=5002`、HTTP 401/403 等）：先刷新凭证；必要时调用 `huawei_id_tool`（`clientId=117860613`、`skillName=ai-zhangle-skills`）获取新凭证，刷新后重新读取 `.xiaoyienv` 并重试一次。
- JSON 解析失败、网络失败、超时：简要说明接口调用失败，并保留脚本返回的 `error` 信息，不要改用联网搜索替代。
- 用户要求超出脚本能力（如真实资金交易、本套件未列出的工具）：直接说明当前不支持，不要绕路实现。
- 接口返回错误状态或空数据：说明接口未返回可用数据，不要臆造数据。
