---
name: ciccwm-skills
description: 中金财富综合技能包，集成了市场行情分析、股票财务分析、热门资讯查询三大功能。支持沪深A股、北交所、港股、美股的证券详情、资金流向、涨跌幅排行、历史行情、个股关联板块；支持A股财务主要指标、利润表、现金流量表、资产负债表；支持今日热榜和专题资讯。Invoke when user asks for CICCWM/中金财富 stock details, market data, rankings, fund flow, related sectors/blocks, historical market data, financial statements, financial indicators, income statement, cash flow, balance sheet, hot news, trending information, or topic news.
env:
  - 117860603_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取账号凭证；若为空，或当前时间大于 ${117860603_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=117860603，skillName=ciccwm-skills）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 117860603_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 中金财富综合技能包

本 skill 集成了三个子功能模块，通过统一的凭证体系调用中金财富接口。不要手写 HTTP 请求；优先使用脚本命令行或 Python 函数调用。

将 `{baseDir}` 替换为本 skill 目录，即 `ciccwm-skills`。

## 意图路由

根据用户意图选择对应的脚本和参数：

| 用户意图关键词 | 脚本 |
|---------------|------|
| 行情、股价、涨跌、K线、资金流向、板块、排行 | `scripts/market_query.py` |
| 财报、财务、利润表、现金流、资产负债、ROE、毛利率 | `scripts/finance_query.py` |
| 资讯、新闻、热榜、热点、专题 | `scripts/get_data.py` |

无法明确意图时，优先按以下规则判断：
- 提到具体证券代码 + "行情/价格/涨跌" → 市场行情
- 提到具体证券代码 + "财务/财报/利润/现金流" → 股票财务
- 提到"新闻/资讯/热点/热榜"且无具体证券代码 → 热门资讯
- 同时涉及行情和财务 → 两个模块都调用，合并结果
- 意图不明确 → 要求用户补充是查行情、财务还是资讯

## 凭证管理

所有子模块共享同一套华为账号绑定凭据：

- 统一从 `/home/sandbox/.openclaw/.xiaoyienv` 读取 `117860603_login_token` 和 `117860603_login_token_expire_time`。
- 若 `117860603_login_token` 为空，或当前时间大于 `117860603_login_token_expire_time`，先调用一次 `huawei_id_tool` 刷新凭证，工具参数为 `clientId=117860603`、`skillName=ciccwm-skills`。
- 刷新成功后重新读取 `.xiaoyienv` 文件，再继续调用对应脚本。
- 脚本只从 `117860603_login_token` 读取鉴权值，不使用本地 config 文件存储凭证。

安全要求:
- 只从 `.xiaoyienv` 读取账号凭证，不要在代码、提示词、日志或输出中明文暴露凭证。
- 若缺少凭证、登录过期或接口返回 `ret = 5002`，先刷新 `117860603_login_token`；必要时调用 `huawei_id_tool` 获取新凭证，再重新读取 `.xiaoyienv` 并继续。
- 不要把 `117860603_login_token` 写入示例命令、URL、查询参数或输出文件。

---

## 模块一：市场行情分析

通过 `scripts/market_query.py` 调用通达信行情接口，返回 JSON 行情数据。

- 服务地址: `https://skill.ciccwm.com`
- 业务命令: `SkillTdxQuotationQueryCommon`

### 输入控制

用户请求必须包含明确查询对象或明确市场范围:

| 场景 | 必需信息 |
|------|----------|
| 证券详情 `info` | 证券代码、市场代码 |
| 资金流向 `fund` | 证券代码、市场代码；仅优先用于沪深市场 |
| 涨跌幅排行 `ranking` | 市场/板块代码，可指定返回条数和排序 |
| 历史行情 `history` | 证券代码、市场代码；可指定返回交易日数量 |
| 个股关联板块 `related` | 证券代码、市场代码 |

不要接受纯泛指对象。若用户只给名称未给代码，可以先基于常识映射高置信代码；不确定时要求用户补充代码和市场。

单次调用限制:

| 查询类型 | 单次上限 | 说明 |
|----------|----------|------|
| `info` | 1 只证券 | 脚本只支持单代码 |
| `fund` | 1 只证券 | 脚本当前请求固定 `Onlytoday=1` |
| `ranking` | 80 条 | `--limit` 超过 80 时脚本会截断为 80 |
| `history` | 1 只证券 | 默认近5个交易日，可用 `--days` 指定数量 |
| `related` | 1 只证券 | 查询个股关联板块 |

### 市场代码 `--market`

| 市场 | 代码 | 适用 |
|------|------|------|
| 深圳 | `0` | 深市 A 股、深市 ETF 等 |
| 上海 | `1` | 沪市 A 股、沪市 ETF 等 |
| 北交所 | `2` | 北京证券交易所 |
| 港股 | `31` | 香港市场 |
| 美股指数 | `12` | 美股指数（道琼斯、纳斯达克等） |
| 美股 | `74` | 美股个股 |

常用规则:
- `60/68` 开头 A 股通常用上海 `1`。
- `00/30` 开头 A 股通常用深圳 `0`。
- 北交所通常用 `2`。
- 港股按脚本常量用 `31`。
- 美股个股用 `74`，美股指数用 `12`。

大陆市场（0/1/2）请求 `Head.Target` 为 `0`，境外市场（31/12/74）为 `1`，脚本内部自动判断。

### 市场/板块排行代码 `ranking --market`

| 排行范围 | 代码 |
|----------|------|
| 上证A股 | `0` |
| 深证A股 | `2` |
| 北交所 | `12` |
| 沪深A股 | `6` |
| 创业板 | `14` |
| 沪深ETF基金 | `11005` |
| 港股通 | `12006` |

排序参数:
- `--sort_type 1`: 涨幅倒序
- `--sort_type 0`: 跌幅正序

### 命令行调用

```bash
# 证券详情
python3 {baseDir}/scripts/market_query.py info --code 600519 --market 1

# 今日资金流向
python3 {baseDir}/scripts/market_query.py fund --code 600519 --market 1

# 沪深A股涨幅前10
python3 {baseDir}/scripts/market_query.py ranking --market 6 --limit 10 --sort_type 1

# 沪深A股跌幅前10
python3 {baseDir}/scripts/market_query.py ranking --market 6 --limit 10 --sort_type 0

# 近5日历史行情
python3 {baseDir}/scripts/market_query.py history --code 600519 --market 1

# 近20日历史行情
python3 {baseDir}/scripts/market_query.py history --code 600519 --market 1 --days 20

# 个股关联板块
python3 {baseDir}/scripts/market_query.py related --code 600519 --market 1
```

### 输出控制

- 保留原始 JSON 中的关键字段，不要臆造缺失字段。
- `history` 和 `ranking` 默认已将接口的 `ListHead.ItemHead + ListItem[].Item` 位置数组转为 `items` 对象数组。
- 面向用户回答时优先提取证券名称、代码、市场、价格、涨跌幅、成交额、成交量、时间、板块名称等可识别字段。
- 多只证券查询时逐只调用脚本，最终合并为表格；若某只失败，在结果中单独标注失败原因。
- 涉及实时行情时说明时效: 交易时段通常为最新行情，非交易时段可能为最近交易日或延迟数据。

---

## 模块二：股票财务分析

通过 `scripts/finance_query.py` 调用 `EQuoteZhongzhuoF10Common` 接口，查询股票财务主要指标、利润表、现金流量表、资产负债表。

- 服务地址: `https://skill.ciccwm.com/zzt/ext/fcgi/common.fcgi`
- 命令字: `EQuoteZhongzhuoF10Common`

### 输入控制

用户请求必须包含明确证券代码或高置信证券名称；如果只给名称且代码不确定，要求用户补充证券代码。

| 场景 | 必需信息 |
|------|----------|
| 财务主要指标 `indicators` | 证券代码 |
| 利润表 `income` | 证券代码 |
| 现金流量表 `cashflow` | 证券代码 |
| 资产负债表 `balance` | 证券代码 |

单次调用限制:

| 查询类型 | 单次上限 | 说明 |
|----------|----------|------|
| `indicators` | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `income` | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `cashflow` | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `balance` | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |

多只证券对比时逐只调用脚本，再合并关键指标。不要一次拼接多个代码。

### action 代码

| 命令 | action | 说明 |
|------|--------|------|
| `indicators` | `48571` | 财务主要指标 |
| `income` | `48572` | 利润表 |
| `cashflow` | `48573` | 现金流量表 |
| `balance` | `48574` | 资产负债表 |

### 报表期 `--qtime`

| qtime | 别名 | 说明 |
|-------|------|------|
| `12` | `annual` | 年报 |
| `06` | `mid` | 中报 |
| `03` | `q1` | 一季度 |
| `09` | `q3` | 三季度 |

### 页面类型 `--gtype`

- `0`: 年报、中报等非单季度查询。默认使用 `0`。
- `1`: 单季度查询。只有明确查询单季度口径时传 `1`。

### 命令行调用

```bash
# 查询贵州茅台最近 5 期年报主要指标
python3 {baseDir}/scripts/finance_query.py indicators --code 600519

# 查询贵州茅台最近 3 期年报利润表
python3 {baseDir}/scripts/finance_query.py income --code 600519 --limit 3

# 查询宁德时代最近 5 期现金流量表
python3 {baseDir}/scripts/finance_query.py cashflow --code 300750

# 查询宁德时代最近 5 期资产负债表
python3 {baseDir}/scripts/finance_query.py balance --code 300750

# 查询中报数据
python3 {baseDir}/scripts/finance_query.py income --code 600519 --qtime 06

# 查询单季度口径数据
python3 {baseDir}/scripts/finance_query.py income --code 600519 --qtime 03 --gtype 1

# 返回全部历史期数
python3 {baseDir}/scripts/finance_query.py indicators --code 600519 --limit 0
```

### 输出控制

- `items` 按接口返回顺序排列，通常从最新报告期到更早报告期。
- 字段名保持接口原始缩写，禁止自行扩展不存在的字段。
- 空字符串表示接口未返回该字段数据，不要把空字符串解读为 0。
- 做财务分析时优先提取报告期 `rq`、营收、利润、经营现金流、总资产、总负债、股东权益、每股收益、ROE、毛利率、净利率等可识别字段。

### 常见字段

| 字段 | 常见含义 |
|------|----------|
| `rq` | 报告期 |
| `yysr` | 营业收入 |
| `yylr` | 营业利润 |
| `lrze` | 利润总额 |
| `jlr` | 净利润 |
| `mgsjlr` | 归母净利润 |
| `yycb` | 营业成本 |
| `glfy` | 管理费用 |
| `xxfy` | 销售费用 |
| `cwfy` | 财务费用 |
| `jyxjlr` | 经营活动现金流入 |
| `jyxjlc` | 经营活动现金流出 |
| `jyxjje` | 经营活动现金流量净额 |
| `tzxjje` | 投资活动现金流量净额 |
| `czxjje` | 筹资活动现金流量净额 |
| `zczj` | 资产总计 |
| `fzhj` | 负债合计 |
| `gdqyhj` | 股东权益合计 |
| `gsmssqy` | 归属于母公司所有者权益 |
| `mgsy` | 每股收益 |
| `jzzsyl` | 净资产收益率 |
| `xsmll` | 销售毛利率 |
| `xsjll` | 销售净利率 |
| `tb` 后缀 | 同比或对比指标 |

---

## 模块三：热门资讯查询

通过 `scripts/get_data.py` 调用 `SkillEInformationTopicSecendPage` 接口，查询今日热榜和专题资讯。

- 服务地址: `https://skill.ciccwm.com/zzt/ext/fcgi/common.fcgi`
- 命令字: `EInformationTopicSecendPage`

### 输入控制

用户请求必须能明确落到"今日热榜"或"专题资讯"。如果用户要求指定专题资讯但未提供专题 id，可先查询今日热榜第一页；无法确定时要求用户补充 `spec_subject_id`。

| 场景 | 必需信息 |
|------|----------|
| 今日热榜 `hot_rank` | 无；可指定页码、每页数量、类型 |
| 专题资讯 `topic` | 可选专题 id；可指定页码、每页数量、类型 |

单次调用限制:

| 查询类型 | 单次上限 | 说明 |
|----------|----------|------|
| `hot_rank` | 1 页 | 默认第 1 页、每页 10 条 |
| `topic` | 1 页 | 默认第 1 页、每页 20 条 |

### 参数声明

| 参数 | 说明 |
|------|------|
| `--page_num` | 页码，默认 `1` |
| `--page_size` | 每页数量，`hot_rank` 默认 `10`，`topic` 默认 `20` |
| `--type` | 资讯类型，默认 `1` |
| `--spec_subject_id` | 专题 id，仅 `topic` 使用 |

### 命令行调用

```bash
# 查询今日热榜前 10 条
python3 {baseDir}/scripts/get_data.py hot_rank --page_num 1 --page_size 10

# 查询今日热榜第 2 页
python3 {baseDir}/scripts/get_data.py hot_rank --page_num 2 --page_size 10

# 查询指定专题资讯
python3 {baseDir}/scripts/get_data.py topic --spec_subject_id 123 --page_num 1 --page_size 20
```

### 输出控制

- `data` 保留接口返回结构，每条记录已自动注入 `redirect_url` 字段，表示详情链接。
- 不臆造不存在的标题、时间、来源或摘要。
- 如果接口返回空列表或错误状态，明确说明接口未返回可用资讯。
- 面向用户回答时优先提取标题、摘要、来源、发布时间、专题 id、详情链接等可识别字段，优先以表格输出。
- 返回数据仅供资讯参考，不作为投资建议。

---

## 常见任务映射

| 用户意图 | 使用命令 |
|----------|----------|
| "查贵州茅台详情/行情" | `market_query.py info --code 600519 --market 1` |
| "查宁德时代资金流向" | `market_query.py fund --code 300750 --market 0` |
| "今天沪深A股涨幅榜前20" | `market_query.py ranking --market 6 --limit 20 --sort_type 1` |
| "查腾讯控股近5日走势" | `market_query.py history --code 00700 --market 31` |
| "查贵州茅台主要财务指标" | `finance_query.py indicators --code 600519` |
| "查贵州茅台近三年利润表" | `finance_query.py income --code 600519 --limit 3` |
| "查宁德时代现金流" | `finance_query.py cashflow --code 300750` |
| "查今天热门新闻" | `get_data.py hot_rank --page_num 1 --page_size 10` |
| "查询专题123的资讯" | `get_data.py topic --spec_subject_id 123 --page_num 1 --page_size 20` |

## 失败处理

- `.xiaoyienv` 不存在、缺少 `117860603_login_token`、登录过期或接口返回 `ret = 5002`: 先刷新凭证；必要时调用 `huawei_id_tool`（`clientId=117860603`、`skillName=ciccwm_skills`）获取新凭证，刷新后重新读取 `.xiaoyienv` 并重试一次。
- JSON 解析失败或网络失败: 简要说明接口调用失败，并保留脚本返回的错误信息。
- 用户要求超过脚本能力（如分时行情、批量行情）: 说明脚本当前不支持，多只证券可逐只调用并合并结果。
- 接口返回错误状态或空数据: 说明接口未返回可用数据，不要改用联网搜索替代。
