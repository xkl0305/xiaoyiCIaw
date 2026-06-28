---
name: gf-securities-skill
description: "智能体调用广发证券GF Skills API专业服务获取权威、实时的 A 股、基金、ETF相关数据。涵盖股票 F10 基础信息、沪深龙虎榜异动榜单、上市公司财务对比、ETF热点榜单、ETF 多维筛选、ETF超级资金异动、公募基金产品信息、基金定投计算器。针对投资者专业金融数据获取难、操作复杂、价格昂贵、效率低等核心痛点，广发证券把硬核金融能力封装成易淘金Skills技能插件包，让 AI 秒变你的专属智能投资助理！"
---

# 广发证券金融数据

## 核心流程

1. 需要实时、近期或权威广发证券数据时，调用广发证券 GF Skills API，不要依赖模型记忆。
2. 优先读取环境变量 `GF_SKILLS_APIKEY`。如果缺失，按“首次无 apikey 引导”请用户提供。
3. 从“工具索引”选择匹配用户问题的 `service_name`、`tool_name` 和 reference。
4. 需要具体参数、返回字段、调用示例或空值排查时，只读取对应 reference。
5. 输出结论时说明关键输入、数据日期或区间；只基于接口数据做事实整理、比较和风险提示，不给确定性收益承诺。

## 首次无 apikey 引导

如果用户首次安装或当前环境没有 `GF_SKILLS_APIKEY`，按两步引导：

1. 请用户打开 `http://hd.gf.com.cn/skills-market` 注册并获取 API key。
2. 请用户把 API key 复制到当前聊天窗口；收到后将该 key 作为 `Authorization: Bearer <apikey>` 使用。

## 通用使用方式

所有广发证券数据工具都通过同一个 MCP API 地址调用：

```bash
curl -sS -X POST 'https://mcp-api.gf.com.cn/gf-skills/skills/mcp/call' \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer ${GF_SKILLS_APIKEY}" \
  --data '{
    "service_name": "<service_name>",
    "tool_name": "<tool_name>",
    "args": {}
  }'
```

通用步骤：

1. 如本地已有环境变量 `GF_SKILLS_APIKEY`，直接复用。
2. 如没有 apikey，按“首次无 apikey 引导”让用户获取并复制到聊天窗口。
3. 使用 POST 请求调用接口。
4. 按所选工具传入 `args`。

## 通用工具说明

请求体固定包含：

| 字段 | 说明 |
| --- | --- |
| `service_name` | 广发证券服务名 |
| `tool_name` | 广发证券工具名 |
| `args` | 该工具的结构化参数 |

参数规范：

- 股票市场：按工具分别使用 `SH/SZ`、`sh/sz`、`101/105` 或带前缀代码。上海为 `SH`、`sh`、`101`；深圳为 `SZ`、`sz`、`105`。
- 股票代码：F10 用纯数字代码，如 `000776`；估值用带市场前缀的大写代码，如 `SZ000776`、`SH600000`。
- 财务指标对比：使用带市场前缀的大写股票代码，`report_type` 取 `1`、`6`、`9`、`12`，`year` 使用完整年份字符串，如 `2025`。
- 日期：龙虎榜使用整数 `YYYYMMDD`；基金工具使用字符串 `YYYYMMDD`。
- 区间筛选：ETF 筛选常用 `5~`、`0~20` 这类区间格式；条件过多时容易无结果。

## 工具索引

| 场景 | 描述 | 适用场景 | service_name | tool_name | 核心参数 | 读取 reference |
| --- | --- | --- | --- | --- | --- | --- |
| 股票 F10 基础信息 | 本 Skill 基于**广发证券权威数据接口**构建，支持查询个股 F10 基础信息，包括公司全称、板块、上市日期、主营业务和所属行业等。 | 适用于快速了解上市公司基本面画像、核对个股静态资料、补充投研背景信息的场景。采用此skill可为大模型提供权威、实时的股票 F10 基础信息。 | `wechat_f10` | `f10_basic_post` | `code`, `market` | [stock-f10.md](references/stock-f10.md) |
| 股票市值、估值与财务指标对比 | 本 Skill 基于**广发证券权威数据接口**构建，支持对比多只股票的总市值、PE、PB、行业均值及历史百分位等估值信息，也支持对比盈利能力、资本结构、现金流等核心财务指标。 | 适用于横向比较股票估值水平、识别高估或低估标的、辅助行业估值分析，以及比较两只股票在盈利、资本、现金流等维度差异的场景。采用此skill可为大模型提供权威、实时的个股市值、估值与财务对比数据。 | `quant` | `common_basic_post`, `compare_indicator_post` | `stock_codes`, `report_type`, `year` | [stock-valuation.md](references/stock-valuation.md) |
| 龙虎榜个股列表 | 本 Skill 基于**广发证券权威数据接口**构建，支持查询指定交易日、指定市场的龙虎榜异常交易个股列表，返回上榜原因、成交额、涨跌幅等关键信息。 | 适用于需要快速定位当日异动个股、分析龙虎榜上榜原因、复盘市场情绪的场景。采用此skill可避免模型依赖过时知识回答短期市场异动问题，为大模型提供权威、实时的广发证券龙虎榜数据。 | `lhb` | `lhb_aborttrade_market_date_get` | `date`, `market` | [lhb-list.md](references/lhb-list.md) |
| 基金详情 | 本 Skill 基于**广发证券权威数据接口**构建，支持查询基金完整详情，包括净值、收益率、风险等级、申购赎回规则、基金经理、基金公司及综合评价等信息。 | 适用于快速核查基金概况、补充基金投研资料、比较基金基本属性的场景。采用此skill可为大模型提供权威、实时的基金详情数据。 | `jijin_info` | `finance-api_product_fund_detail_get` | `tradeCode` | [fund-detail.md](references/fund-detail.md) |
| 基金定投回测 | 本 Skill 基于**广发证券权威数据接口**构建，支持模拟指定基金在历史区间内的定投收益，覆盖普通定投、指数均线、目标止盈、移动止盈等多种策略。 | 适用于回测基金定投方案、评估不同策略收益表现、比较定投参数设置效果的场景。采用此skill可为大模型提供权威、实时的基金定投回测数据。 | `fund_invest` | `finance_api_product_invest_compute_post` | `tradeCode`, `balance`, `rate`, `startDate`, `endDate`, `strategyList` | [fund-invest.md](references/fund-invest.md) |
| ETF 多维筛选 | 本 Skill 基于**广发证券权威数据接口**构建，支持按收益率、回撤、夏普、估值温度、规模、赛道、交易属性等多维条件筛选 ETF。 | 适用于寻找特定主题 ETF、做收益与风险条件过滤、构建 ETF 候选池的场景。采用此skill可为大模型提供权威、实时的 ETF 筛选数据。 | `etf_search` | `finance_api_inclusive_etf_list_get` | 筛选条件、`sort`, `start`, `limit` | [etf-search.md](references/etf-search.md) |
| ETF 榜单 | 本 Skill 基于**广发证券权威数据接口**构建，支持获取 ETF 涨幅、跌幅、换手、主力资金、净申购、溢价率等多类榜单数据。 | 适用于筛选市场热点 ETF、观察资金偏好、快速获取榜单排名的场景。采用此skill可为大模型提供权威、实时的 ETF 榜单数据。 | `etf_rank` | `finance-api_product_etf_rank_get` | `type`, `page`, `size` | [etf-rank.md](references/etf-rank.md) |
| ETF 超级资金异动 | 本 Skill 基于**广发证券权威数据接口**构建，支持查询发生大幅流入、大幅流出、持续流入、持续流出等超级资金异动的 ETF 列表及近 14 日资金明细。 | 适用于跟踪 ETF 资金异动、观察市场情绪、识别短期资金聚焦方向的场景。采用此skill可为大模型提供权威、实时的 ETF 超级资金数据。 | `etf-super-fund` | `gfmiddle_eits_super_fund_etf_superfund_get` | `type` | [etf-super-fund.md](references/etf-super-fund.md) |
