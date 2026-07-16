---
name: ciccwm-skills
description: 中金财富综合技能包，集成了市场行情分析、股票财务分析、热门资讯查询、ETF热门榜单、龙虎榜异动分析、基金产品信息六大功能。支持沪深A股、北交所、港股、美股的证券详情、资金流向、涨跌幅排行、历史行情、个股关联板块；支持A股财务主要指标、利润表、现金流量表、资产负债表；支持今日热榜和专题资讯；支持ETF涨跌榜/资金榜/特色榜（连涨/换手/溢价/自选）/热搜榜；支持龙虎榜总榜/机构榜/游资榜、活跃营业部画像、个股上榜详情拆解；支持公募基金搜索、基金档案、费率明细、持仓概况、历史表现、分红公告和多基金横向对比。Invoke when user asks for CICCWM/中金财富 stock details, market data, rankings, fund flow, related sectors/blocks, historical market data, financial statements, financial indicators, income statement, cash flow, balance sheet, hot news, trending information, topic news, ETF rankings, ETF hot list, ETF price/fund/turnover/premium ranking, 龙虎榜/异动个股/机构榜/游资榜/活跃营业部/上榜席位, or fund profile, fund fees, fund holdings, fund manager, dividend, announcement, NAV, public fund comparison.
env:
  - 117860603_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取账号凭证；若为空，或当前时间大于 ${117860603_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=117860603，skillName=cicc-skills）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 117860603_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 中金财富综合技能包

本 skill 集成了六个子功能模块，通过统一的凭证体系调用中金财富接口。不要手写 HTTP 请求；优先使用脚本命令行或 Python 函数调用。

将 `{baseDir}` 替换为本 skill 目录，即 `ciccwm-skills`。

## 意图路由

根据用户意图选择对应的脚本和参数：

| 用户意图关键词                              | 脚本                              |
| ------------------------------------ | ------------------------------- |
| 行情、股价、涨跌、K线、资金流向、板块、排行               | `scripts/market_query.py`       |
| 财报、财务、利润表、现金流、资产负债、ROE、毛利率           | `scripts/finance_query.py`      |
| 资讯、新闻、热榜、热点、专题                       | `scripts/get_data.py`           |
| ETF涨跌榜、ETF资金榜、ETF换手/溢价/连涨/自选榜、ETF热搜榜 | `scripts/etf_ranking_query.py`  |
| 龙虎榜、异动个股、机构榜、游资榜、活跃营业部、上榜席位          | `scripts/tiger_list_query.py`   |
| 基金搜索、基金档案、基金费率、基金持仓、基金表现、基金分红、基金对比   | `scripts/fund_product_query.py` |

无法明确意图时，优先按以下规则判断：

- 提到具体证券代码 + "行情/价格/涨跌" → 市场行情
- 提到具体证券代码 + "财务/财报/利润/现金流" → 股票财务
- 提到"新闻/资讯/热点/热榜"且无具体证券代码 → 热门资讯
- 提到"ETF + 榜单/排行/资金/换手/溢价/热搜" → ETF 热门榜单
- 提到"龙虎榜/机构席位/游资/营业部/上榜" → 龙虎榜异动分析
- 提到"基金/公募/基金经理/费率/持仓/净值/分红" → 基金产品信息
- 同时涉及行情和财务 → 两个模块都调用，合并结果
- 意图不明确 → 要求用户补充是查行情、财务、资讯、ETF榜单、龙虎榜还是基金

## 凭证管理

所有子模块共享同一套华为账号绑定凭据：

- 统一从 `/home/sandbox/.openclaw/.xiaoyienv` 读取 `117860603_login_token` 和 `117860603_login_token_expire_time`。
- 若 `117860603_login_token` 为空，或已过期（当前时间大于 `117860603_login_token_expire_time`），先调用一次 `huawei_id_tool(117860603, ciccwm-skills)` 刷新凭证 。
- 刷新成功后重新读取 `.xiaoyienv` 文件，再继续调用对应脚本。
- 脚本只从 `117860603_login_token` 读取鉴权值，不使用本地 config 文件存储凭证。

安全要求:

- 只从 `.xiaoyienv` 读取账号凭证，不要在代码、提示词、日志或输出中明文暴露凭证。
- 若缺少凭证、凭证过期或接口返回 `ret = 5002`，先刷新 `117860603_login_token`；必要时调用 `huawei_id_tool` 获取新凭证，再重新读取 `.xiaoyienv` 并继续。
- 不要把 `117860603_login_token` 写入示例命令、URL、查询参数或输出文件。

---

## 模块一：市场行情分析

通过 `scripts/market_query.py` 调用通达信行情接口，返回 JSON 行情数据。

### 输入控制

用户请求必须包含明确查询对象或明确市场范围:

| 场景               | 必需信息                 |
| ---------------- | -------------------- |
| 证券详情 `info`      | 证券代码、市场代码            |
| 资金流向 `fund`      | 证券代码、市场代码；仅优先用于沪深市场  |
| 涨跌幅排行 `ranking`  | 市场/板块代码，可指定返回条数和排序   |
| 历史行情 `history`   | 证券代码、市场代码；可指定返回交易日数量 |
| 个股关联板块 `related` | 证券代码、市场代码            |

不要接受纯泛指对象。若用户只给名称未给代码，可以先基于常识映射高置信代码；不确定时要求用户补充代码和市场。

单次调用限制:

| 查询类型      | 单次上限  | 说明                         |
| --------- | ----- | -------------------------- |
| `info`    | 1 只证券 | 脚本只支持单代码                   |
| `fund`    | 1 只证券 | 脚本当前请求固定 `Onlytoday=1`     |
| `ranking` | 80 条  | `--limit` 超过 80 时脚本会截断为 80 |
| `history` | 1 只证券 | 默认近5个交易日，可用 `--days` 指定数量  |
| `related` | 1 只证券 | 查询个股关联板块                   |

### 市场代码 `--market`

| 市场   | 代码   | 适用              |
| ---- | ---- | --------------- |
| 深圳   | `0`  | 深市 A 股、深市 ETF 等 |
| 上海   | `1`  | 沪市 A 股、沪市 ETF 等 |
| 北交所  | `2`  | 北京证券交易所         |
| 港股   | `31` | 香港市场            |
| 美股指数 | `12` | 美股指数（道琼斯、纳斯达克等） |
| 美股   | `74` | 美股个股            |

常用规则:

- `60/68` 开头 A 股通常用上海 `1`。
- `00/30` 开头 A 股通常用深圳 `0`。
- 北交所通常用 `2`。
- 港股按脚本常量用 `31`。
- 美股个股用 `74`，美股指数用 `12`。

大陆市场（0/1/2）请求 `Head.Target` 为 `0`，境外市场（31/12/74）为 `1`，脚本内部自动判断。

### 市场/板块排行代码 `ranking --market`

| 排行范围    | 代码      |
| ------- | ------- |
| 上证A股    | `0`     |
| 深证A股    | `2`     |
| 北交所     | `12`    |
| 沪深A股    | `6`     |
| 创业板     | `14`    |
| 沪深ETF基金 | `11005` |
| 港股通     | `12006` |

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

通过 `scripts/finance_query.py` 查询股票财务主要指标、利润表、现金流量表、资产负债表。

### 输入控制

用户请求必须包含明确证券代码或高置信证券名称；如果只给名称且代码不确定，要求用户补充证券代码。

| 场景                  | 必需信息 |
| ------------------- | ---- |
| 财务主要指标 `indicators` | 证券代码 |
| 利润表 `income`        | 证券代码 |
| 现金流量表 `cashflow`    | 证券代码 |
| 资产负债表 `balance`     | 证券代码 |

单次调用限制:

| 查询类型         | 单次上限  | 说明                       |
| ------------ | ----- | ------------------------ |
| `indicators` | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `income`     | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `cashflow`   | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |
| `balance`    | 1 只证券 | 默认最近 5 期，可用 `--limit` 控制 |

多只证券对比时逐只调用脚本，再合并关键指标。不要一次拼接多个代码。

### action 代码

| 命令           | action  | 说明     |
| ------------ | ------- | ------ |
| `indicators` | `48571` | 财务主要指标 |
| `income`     | `48572` | 利润表    |
| `cashflow`   | `48573` | 现金流量表  |
| `balance`    | `48574` | 资产负债表  |

### 报表期 `--qtime`

| qtime | 别名       | 说明  |
| ----- | -------- | --- |
| `12`  | `annual` | 年报  |
| `06`  | `mid`    | 中报  |
| `03`  | `q1`     | 一季度 |
| `09`  | `q3`     | 三季度 |

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

| 字段        | 常见含义        |
| --------- | ----------- |
| `rq`      | 报告期         |
| `yysr`    | 营业收入        |
| `yylr`    | 营业利润        |
| `lrze`    | 利润总额        |
| `jlr`     | 净利润         |
| `mgsjlr`  | 归母净利润       |
| `yycb`    | 营业成本        |
| `glfy`    | 管理费用        |
| `xxfy`    | 销售费用        |
| `cwfy`    | 财务费用        |
| `jyxjlr`  | 经营活动现金流入    |
| `jyxjlc`  | 经营活动现金流出    |
| `jyxjje`  | 经营活动现金流量净额  |
| `tzxjje`  | 投资活动现金流量净额  |
| `czxjje`  | 筹资活动现金流量净额  |
| `zczj`    | 资产总计        |
| `fzhj`    | 负债合计        |
| `gdqyhj`  | 股东权益合计      |
| `gsmssqy` | 归属于母公司所有者权益 |
| `mgsy`    | 每股收益        |
| `jzzsyl`  | 净资产收益率      |
| `xsmll`   | 销售毛利率       |
| `xsjll`   | 销售净利率       |
| `tb` 后缀   | 同比或对比指标     |

---

## 模块三：热门资讯查询

通过 `scripts/get_data.py` 查询今日热榜和专题资讯。

### 输入控制

用户请求必须能明确落到"今日热榜"或"专题资讯"。如果用户要求指定专题资讯但未提供专题 id，可先查询今日热榜第一页；无法确定时要求用户补充 `spec_subject_id`。

| 场景              | 必需信息                  |
| --------------- | --------------------- |
| 今日热榜 `hot_rank` | 无；可指定页码、每页数量、类型       |
| 专题资讯 `topic`    | 可选专题 id；可指定页码、每页数量、类型 |

单次调用限制:

| 查询类型       | 单次上限 | 说明              |
| ---------- | ---- | --------------- |
| `hot_rank` | 1 页  | 默认第 1 页、每页 10 条 |
| `topic`    | 1 页  | 默认第 1 页、每页 20 条 |

### 参数声明

| 参数                  | 说明                                      |
| ------------------- | --------------------------------------- |
| `--page_num`        | 页码，默认 `1`                               |
| `--page_size`       | 每页数量，`hot_rank` 默认 `10`，`topic` 默认 `20` |
| `--type`            | 资讯类型，默认 `1`                             |
| `--spec_subject_id` | 专题 id，仅 `topic` 使用                      |

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

## 模块四：ETF 热门榜单

通过 `scripts/etf_ranking_query.py` 查询 ETF 各类排行榜：涨跌榜、资金榜、特色榜（连涨/换手/溢价/自选）以及热搜榜（并可用批量行情接口补充字段）。

### 输入控制

用户请求需要明确「看哪类榜单」，否则要求补充。ETF 榜单无需证券代码，按市场范围（沪深 ETF）排序返回。

| 场景               | 命令                    | 必需信息     | 说明                   |
| ---------------- | --------------------- | -------- | -------------------- |
| 涨跌榜 `price`      | `price --type <榜单>`   | 榜单类型，可省略 | 默认 `today` 今日涨跌幅     |
| 资金榜 `fund`       | `fund --type <榜单>`    | 榜单类型，可省略 | 默认 `main` 主力净额       |
| 特色榜 `special`    | `special --type <榜单>` | 榜单类型，可省略 | 默认 `consecutive` 连涨榜 |
| 热搜榜 `hot_search` | `hot_search`          | 无        | 可选页码、条数              |

单次调用限制:

| 查询类型                         | 单次上限 | 说明                           |
| ---------------------------- | ---- | ---------------------------- |
| `price` / `fund` / `special` | 80 条 | `--limit` 超过 80 截断为 80；默认 30 |
| `hot_search`                 | 60 条 | 默认 30；最多 60 条（自动翻页）          |

### 榜单参数对照

看涨跌 `price --type`:

| 榜单类型    | 说明        |
| ------- | --------- |
| `today` | 今日涨跌幅（默认） |
| `5d`    | 5 日涨跌幅    |
| `20d`   | 20 日涨跌幅   |
| `60d`   | 60 日涨跌幅   |
| `year`  | 今年以来      |

看资金 `fund --type`: `main` 主力净额（默认）/ `subscribe` 申购净流入 / `finance` 融资净流入。

看特色 `special --type`: `consecutive` 连涨榜（默认）/ `turnover` 换手榜 / `premium` 溢价榜（升序）/ `custom` 自选榜。

热搜榜 `hot_search`: 返回热搜 ETF 列表，默认再用批量行情接口补充最新价、涨跌幅、成交额、溢价率、规模、跟踪指数等行情字段（`--no_enrich` 关闭）。

特殊说明:

- 主力净额榜（`main`）与换手榜（`turnover`）在 **08:50~09:25** 时段内，脚本会自动将排序字段替换为总市值。
- 溢价榜默认升序，其余榜单默认降序；可用 `--sort_type` 覆盖（`1`=降序，`2`=升序）。

### 命令行调用

```bash
# ETF 今日涨跌幅榜前 30
python3 {baseDir}/scripts/etf_ranking_query.py price --type today

# ETF 5 日涨幅榜前 20
python3 {baseDir}/scripts/etf_ranking_query.py price --type 5d --limit 20

# ETF 主力净额榜（默认）
python3 {baseDir}/scripts/etf_ranking_query.py fund --type main

# ETF 换手榜前 20
python3 {baseDir}/scripts/etf_ranking_query.py special --type turnover --limit 20

# ETF 溢价榜（升序，溢价率最低靠前）
python3 {baseDir}/scripts/etf_ranking_query.py special --type premium

# ETF 热搜榜前 30（含行情补充）
python3 {baseDir}/scripts/etf_ranking_query.py hot_search --limit 30

# 返回接口原始结构
python3 {baseDir}/scripts/etf_ranking_query.py price --type 5d --raw
```

### 输出控制

- `price` / `fund` / `special` 默认已将接口的 `ListHead.ItemHead + ListItem` 转为 `items` 对象数组；需要原始结构时使用 `--raw`。
- 字段名保持接口原始列含义，禁止自行扩展不存在的字段。
- 金额类字段单位通常为元；比例类字段（`rise_down_ratio`/`turnover_rate`/`premium_rate` 等）为百分比数值。
- 面向用户回答时优先以表格提取证券名称、代码、市场、最新价、涨跌幅、对应榜单排序字段（如 5 日涨跌、主力净额、换手率、溢价率、连涨天数等）。
- 涉及实时行情时说明时效: 交易时段通常为最新行情，非交易时段可能为最近交易日或延迟数据。

---

## 模块五：龙虎榜异动分析

通过 `scripts/tiger_list_query.py` 调用龙虎榜接口，提供沪深龙虎榜异动个股查询与席位分析能力。

### 输入控制

用户请求应明确属于以下场景之一:

| 场景                     | 必需信息                   |
| ---------------------- | ---------------------- |
| 龙虎榜榜单 `stock_list`     | 可选日期；可指定榜单类型           |
| 活跃营业部列表 `active_orgs`  | 可选日期                   |
| 龙虎榜个股详情 `stock_detail` | `stock_code`（龙虎榜侧股票代码） |
| 活跃营业部详情 `org_detail`   | `yyb`（营业部名称）           |

日期格式为 `yyyy-MM-dd`，不传时默认查询最新日期数据。

`stock_detail` 使用注意（必须遵循）:

- `--stock_code` 不是标准 6 位证券代码，而是龙虎榜接口里的特殊代码（灯塔代码）。
- 该值来自 `stock_list` 返回字段 `dt_sec_code`。
- 建议流程为：先查询最新/指定日期龙虎榜列表，拿到目标个股的 `dt_sec_code`，再调用 `stock_detail` 做深入拆解。
- 不要把 `secu_code`（标准股票代码）直接传给 `--stock_code`，否则可能查不到详情。

单次调用限制:

| 查询类型           | 单次上限   | 说明                                 |
| -------------- | ------ | ---------------------------------- |
| `stock_list`   | 1 个日期  | 默认返回总榜+机构榜+游资榜，可用 `--list_type` 筛选 |
| `active_orgs`  | 1 个日期  | 返回活跃营业部及净买入概况                      |
| `stock_detail` | 1 只股票  | 返回该股票上榜明细及买卖席位                     |
| `org_detail`   | 1 个营业部 | 返回该席位画像与关联上榜个股                     |

### 参数声明

通用参数: `--req_date`（查询日期 `yyyy-MM-dd`，不传默认最新）、`--raw`（返回接口原始结构）。

`stock_list` 参数:

- `--req_type`：`1` 首页，`2` 列表页，默认 `1`
- `--list_type`：`all` 全部、`overall` 总榜、`jgqc` 机构榜、`yzby` 游资榜

`stock_detail` 参数: `--stock_code`（龙虎榜侧股票代码 / 灯塔代码，来源于 `stock_list` 返回的 `dt_sec_code`）。

`org_detail` 参数: `--yyb`（营业部名称，如“中信证券上海分公司”）。

### 命令行调用

```bash
# 第一步：查询最新龙虎榜（总榜+机构榜+游资榜），从返回结果中拿 dt_sec_code
python3 {baseDir}/scripts/tiger_list_query.py stock_list --req_type 1 --list_type all

# 查询指定日期机构榜
python3 {baseDir}/scripts/tiger_list_query.py stock_list --req_date 2026-06-12 --req_type 2 --list_type jgqc

# 查询活跃营业部列表
python3 {baseDir}/scripts/tiger_list_query.py active_orgs --req_date 2026-06-12 --req_type 2

# 第二步：将上一步返回的 dt_sec_code 作为 --stock_code 查询个股详情（含买卖前五席位）
python3 {baseDir}/scripts/tiger_list_query.py stock_detail --stock_code 0001301007 --req_date 2026-06-12

# 查询活跃营业部详情画像
python3 {baseDir}/scripts/tiger_list_query.py org_detail --yyb "中信证券上海分公司" --req_date 2026-06-12
```

### 输出控制

- 优先提取股票代码、股票名称、净买入、涨跌幅、上榜原因、营业部名称、买卖金额、成功率、偏好板块等可识别字段。
- `stock_detail` 重点关注 `sale_secu_detail_list` 内 `reason_map`，用于拆解买方前五和卖方前五席位金额。
- `org_detail` 重点关注 `s_org_class`、`s_org_fac`、`s_manipulat`、`plant`、`f_three_day_success`。
- 所有接口返回的 `f_income`（净买入）字段数值单位均为“万”，使用时请据此换算。
- 字段含义以接口返回为准，不要臆造不存在的字段；结构不符时使用 `--raw` 排查。

---

## 模块六：基金产品信息

通过 `scripts/fund_product_query.py` 调用中金财富基金产品接口，查询公募基金搜索、基金档案、费率明细、持仓概况、历史表现、分红公告等信息。当前版本聚焦公募基金信息查询。

### 输入控制

若用户只提供模糊名称，先调用 `search` 获取候选基金，再用候选结果中的 `product_id` 查询详情，避免因为名称不精确而直接查不到。

| 场景   | 命令            | 说明                          |
| ---- | ------------- | --------------------------- |
| 基金搜索 | `search`      | 按基金名称、简称、代码等关键词搜索公募基金候选     |
| 基金档案 | `profile`     | 查询基金类型、规模、经理、业绩基准、风险等级、成立日等 |
| 费率明细 | `fees`        | 查询申购费、赎回费、管理费、托管费、销售服务费等    |
| 持仓概况 | `holding`     | 查询重仓股/券、行业配置、股票仓位等持仓结构      |
| 历史表现 | `performance` | 查询阶段涨跌幅、区间净值等历史表现数据         |
| 分红公告 | `events`      | 查询分红记录与基金公告                 |
| 横向对比 | `compare`     | 对比多只基金的规模、费率、经理、风险等级、历史表现摘要 |

单次调用建议:

- `search --size` 默认 10，最大建议 20。
- `compare` 建议 2 到 5 只基金，超过 5 只时分批查询。
- 搜索返回多个候选时默认不自动选择；需要自动取第一条时显式使用 `--select-first`。
- 用户给出明确 `product_id` 时可跳过搜索直接查详情；输入 6 位且以 `0` 开头的数字时优先按基金代码搜索。
- 持仓查询默认不传 `date`，由接口返回最新季度数据；只有用户明确指定日期时才传 `--date`。

### 命令行调用

```bash
# 模糊搜索基金
python3 {baseDir}/scripts/fund_product_query.py search --keyword 沪深300

# 查询基金档案；若搜索结果唯一则自动进入详情，否则返回候选列表
python3 {baseDir}/scripts/fund_product_query.py profile --keyword 沪深300

# 明确选择搜索第一条候选后查询基金档案
python3 {baseDir}/scripts/fund_product_query.py profile --keyword 沪深300 --select-first

# 已知 product_id 时直接查询基金档案
python3 {baseDir}/scripts/fund_product_query.py profile --product_id 123456

# 查询费率明细
python3 {baseDir}/scripts/fund_product_query.py fees --keyword 沪深300 --select-first

# 查询持仓概况
python3 {baseDir}/scripts/fund_product_query.py holding --keyword 沪深300 --select-first

# 查询阶段表现
python3 {baseDir}/scripts/fund_product_query.py performance --keyword 沪深300 --select-first

# 查询分红与公告
python3 {baseDir}/scripts/fund_product_query.py events --keyword 沪深300 --select-first

# 对比多只基金
python3 {baseDir}/scripts/fund_product_query.py compare --items 沪深300 中证500 --select-first --include_fees --include_performance
```

### 输出控制

- 脚本输出为 UTF-8 JSON，使用 `--raw` 可返回接口原始数据，便于字段核对。
- 保留接口返回的真实字段，不要臆造缺失字段。
- 搜索命中多只基金时，先展示候选基金简称、基金代码、基金全称；`product_id` 只作为内部产品 ID 辅助识别。
- `risk_level_label`、`product_sell_status_label` 等是面向用户的中文标签；原始码值保留用于核对。
- 涉及历史表现时说明“历史表现不代表未来收益”。
- 任何回答都需要保留风险声明: `本服务提供的数据仅供参考，不构成投资建议，市场有风险，投资需谨慎。`

---

## 常见任务映射

| 用户意图                | 使用命令                                                                             |
| ------------------- | -------------------------------------------------------------------------------- |
| "查贵州茅台详情/行情"        | `market_query.py info --code 600519 --market 1`                                  |
| "查宁德时代资金流向"         | `market_query.py fund --code 300750 --market 0`                                  |
| "今天沪深A股涨幅榜前20"      | `market_query.py ranking --market 6 --limit 20 --sort_type 1`                    |
| "查腾讯控股近5日走势"        | `market_query.py history --code 00700 --market 31`                               |
| "查贵州茅台主要财务指标"       | `finance_query.py indicators --code 600519`                                      |
| "查贵州茅台近三年利润表"       | `finance_query.py income --code 600519 --limit 3`                                |
| "查宁德时代现金流"          | `finance_query.py cashflow --code 300750`                                        |
| "查今天热门新闻"           | `get_data.py hot_rank --page_num 1 --page_size 10`                               |
| "查询专题123的资讯"        | `get_data.py topic --spec_subject_id 123 --page_num 1 --page_size 20`            |
| “ETF 今天涨幅榜前 20”     | `etf_ranking_query.py price --type today --limit 20`                             |
| “ETF 近 5 日涨幅榜”      | `etf_ranking_query.py price --type 5d`                                           |
| “ETF 主力资金净流入榜”      | `etf_ranking_query.py fund --type main`                                          |
| “ETF 换手率榜前 20”      | `etf_ranking_query.py special --type turnover --limit 20`                        |
| “ETF 折价/低溢价榜”       | `etf_ranking_query.py special --type premium`                                    |
| “ETF 热搜榜”           | `etf_ranking_query.py hot_search --limit 30`                                     |
| “盘后看下今天龙虎榜”         | `tiger_list_query.py stock_list --req_type 1 --list_type all`                    |
| “查今天机构席位集中买入的股票”    | `tiger_list_query.py stock_list --req_date 2026-06-12 --list_type jgqc`          |
| “分析某只上榜股买卖前五席位”     | `tiger_list_query.py stock_detail --stock_code 0001301007 --req_date 2026-06-12` |
| “看某营业部风格和近期胜率”      | `tiger_list_query.py org_detail --yyb "中信证券上海分公司" --req_date 2026-06-12`         |
| “搜一下沪深300基金”        | `fund_product_query.py search --keyword 沪深300`                                   |
| “查这只基金的费率”          | `fund_product_query.py fees --keyword 沪深300 --select-first`                      |
| “看基金重仓股和行业配置”       | `fund_product_query.py holding --keyword 沪深300 --select-first`                   |
| “对比沪深300和中证500两只基金” | `fund_product_query.py compare --items 沪深300 中证500 --select-first`               |

## 失败处理

- `.xiaoyienv` 不存在、缺少 `117860603_login_token`、登录过期或接口返回 `ret = 5002`: 先刷新凭证；必要时调用 `huawei_id_tool(117860603, ciccwm-skills)`获取新凭证，刷新后重新读取 `.xiaoyienv` 并重试一次。
- JSON 解析失败或网络失败: 简要说明接口调用失败，并保留脚本返回的错误信息。
- 用户要求超过脚本能力（如分时行情、批量行情）: 说明脚本当前不支持，多只证券可逐只调用并合并结果。
- 接口返回错误状态或空数据: 说明接口未返回可用数据，不要改用联网搜索替代。
