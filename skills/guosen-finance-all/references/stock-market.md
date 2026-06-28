# 股市行情查询 — API 参考及调用示例

本模块提供查询股市行情的能力，包括实时行情、历史行情、资金流向、涨跌幅排名等功能。覆盖沪深 A 股、北交所、港股、美股。

## 脚本

`scripts/stock_market_get_data.py`

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `117859343_login_token` | 从 `.xiaoyienv` 取出 `117859343_login_token`，国信接口鉴权 key（必填） | 空 |

## 调用示例

### 命令行调用

```bash
# 查询单个股票实时行情
python3 scripts/stock_market_get_data.py single_hq --code 600519 --set_code 1

# 查询多只股票实时行情
python3 scripts/stock_market_get_data.py comb_hq --codes 600519,000001 --set_codes 1,0

# 查询资金流向
python3 scripts/stock_market_get_data.py fund_flow --code 600519 --set_code 1 --period 10

# 查询涨幅排名
python3 scripts/stock_market_get_data.py multi_hq --set_domain 6 --want_num 10

# 查询个股关联板块
python3 scripts/stock_market_get_data.py related_comb --code 600519 --set_code 1

# 查询历史行情
python3 scripts/stock_market_get_data.py past_hq --code 600519 --set_code 1 --want_nums 20
```

### 代码调用

```python
from scripts.stock_market_get_data import (
    query_single_hq,
    query_comb_hq,
    query_fund_flow,
    query_multi_hq,
    query_related_comb_hq,
    query_past_hq
)

# 查询上证指数
result = query_single_hq("600519", set_code=1)

# 查询多只股票
result = query_comb_hq(["600519", "000001"], [1, 0])

# 查询资金流向
result = query_fund_flow("600519", set_code=1, period=10)

# 查询沪深A股涨幅前10
result = query_multi_hq(set_domain=6, want_num=10)

# 查询个股关联板块
result = query_related_comb_hq("600519", set_code=1)

# 查询历史行情
result = query_past_hq("600519", set_code=1, want_nums=20)
```

## 功能范围

### 1. 查询单个证券实时行情

**接口**: `GET /gsnews/market/agentbot/queryHQInfo/1.0`

查询单个证券，可返回关联指数信息。

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码，如 `000001`, `600519` |
| setCode | 否 | integer | 证券市场代码，默认 0 |
| target | 否 | integer | 站点信息 0-沪深京(默认)，3-港股美股 |

### 2. 查询多个证券实时行情

**接口**: `GET /gsnews/market/agentbot/queryCombHQ/1.0`

查询多个证券实时行情，不返回关联指数信息。

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码，可多个逗号分隔 |
| setCode | 是 | string | 证券市场代码，多个用逗号分隔 |
| target | 否 | integer | 站点，0-沪深京(默认)，3-港股美股 |

### 3. 查询资金流向

**接口**: `GET /gsnews/market/agentbot/queryFundFlow/1.0`

查询 ETF、个股的资金流向。仅支持沪深市场。

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| period | 是 | string | 周期，单位为日，最多60日 |
| code | 否 | string | 证券代码 |
| setCode | 是 | string | 证券市场代码，0-深圳，1-上海 |

### 4. 查询涨幅排名

**接口**: `GET /gsnews/market/agentbot/queryMultiHQ/1.0`

大盘个股涨幅前N、大盘ETF涨幅前N、行业板块个股涨幅前N。

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| setDomain | 是 | integer | 查询类型 |
| wantNum | 是 | integer | 返回数量，最多80 |
| sortType | 否 | integer | 1-涨幅(默认)，2-跌幅 |
| target | 否 | integer | 0-沪深(默认)，3-港股美股 |

**setDomain 查询类型**:
| setDomain | 说明 |
|-----------|------|
| 0 | 上证A股 |
| 2 | 深证A股 |
| 14515 | 北交所 |
| 6 | 沪深A股 |
| 14 | 创业板 |
| 11005 | 沪深ETF基金 |

### 5. 查询个股关联板块

**接口**: `GET /gsnews/market/agentbot/queryRelatedCombHQ/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| setCode | 是 | integer | 证券市场代码 |
| target | 否 | integer | 站点信息 0-沪深京(默认)，3-港股美股 |

### 6. 查询近n个交易日日行情

**接口**: `GET /gsnews/market/agentbot/queryPastHQInfo/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| setCode | 是 | string | 证券市场代码 |
| wantNums | 是 | integer | 近n个交易日 |
| target | 否 | integer | 0-沪深京(默认)，3-港股美股 |
| mas | 否 | string | 要计算的MA周期，多个以逗号分隔 |

## 常用市场代码参考

| 市场 | setCode | 说明 |
|------|---------|------|
| 深圳 | 0 | 深证A股 |
| 上海 | 1 | 上证A股 |
| 北交所 | 2 | 北京证券交易所 |
| 港股 | -1 | 香港股票 |
| 美股 | 74 | 美国股票 |

## 核心数据约束

### 必须指定明确的查询对象
- 要求：查询语句中必须包含明确的证券名称、代码、指数名称或板块 / 概念名称
- 禁止：纯泛指表述，如"某只股票"、"某个行业"、"一些热门股"等

| 示例类型 | 示例内容 |
|----------|----------|
| 错误 | 查询某热门股票的行情 |
| 正确 | 查询宁德时代今日行情 |
| 正确 | 查询 300750 近 20 个交易日的历史行情 |
| 正确 | 查询电力板块的涨跌幅排行 |

### 单次查询实体上限

| 数据类型 | 单次最多证券实体数 | 超出处理方式 |
|----------|-------------------|-------------|
| 实时行情 | 10 个 | 自动拆分为多次调用，合并结果 |
| 历史行情 | 1 个 | 自动逐一调用 |
| 资金流向 | 1 个 | 自动逐一调用 |

### 行情数据时效性说明

| 类型 | 说明 |
|------|------|
| 实时行情 | 仅在交易时段（A 股 09:30–15:00，港股 09:30–16:00）返回最新价；非交易时段返回上一交易日收盘价 |
| 历史行情 | 数据截止至最近已收盘的交易日；默认返回最近 20 个交易日 |
| 北向/南向资金 | 每日收盘后更新，当日数据在收盘后约 30 分钟可用 |

## 返回字段说明

各接口统一返回格式如下:

```json
{
    "result": {
        "code": 0,
        "msg": "请求成功"
    },
    "data": { ... }
}
```

## 查询示例

### 实时行情
1. 查询贵州茅台当前的股价和涨跌幅
2. 宁德时代、比亚迪今天的实时行情
3. 查询腾讯控股（港股）现在的最新价和成交量

### 历史 K 线
1. 查询格力电器近 20 个交易日的日 K 数据
2. 查询 300750 从 2025 年 1 月 1 日到 3 月 15 日的历史行情
3. 中芯国际近三个月每日收盘价和涨跌幅

### 资金流向
1. 查询宁德时代今日的主力资金净流入情况
2. 比亚迪大单和超大单资金今天的买入卖出情况
3. 今日北向资金持仓最多的 A 股个股是哪些？
4. 查询南向资金（港股通）今日买入最多的港股

### 板块涨跌幅排行
1. 今日行业涨跌幅排名
2. 电力板块内各成分股的实时涨跌幅
3. 查询宁德时代所属板块的整体行情表现
4. 今天涨幅最大的概念板块是哪些？

### 涨跌停分析
1. 今日 A 股涨停家数和涨停成因分析
2. 查询今日封板时间最长的涨停股
3. 有哪些股票今日出现跌停？

### ETF 与概念联动
1. 当前市场最热门的概念板块有哪些？
2. 持有比亚迪股票的 ETF 有哪些？
3. 半导体行业 ETF（588000）的十大重仓股

## 常见问题

**错误: `login token` is required.**
→ 需配置 `login token`，请联系管理员获取并手动配置

**接口返回错误怎么办？**
→ 检查证券代码是否正确，确认市场代码是否匹配

## 注意事项
- 如果 API 调用失败，直接提醒用户"数据获取失败"，**不要**尝试从联网搜索或其他渠道获取数据
- 返回数据仅供参考，不作为投资建议
