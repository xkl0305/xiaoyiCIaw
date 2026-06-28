# 广发证券股票市值与估值skill（gf_stock_valuation）

通过**结构化参数**调用广发证券估值与财务对比工具，接口返回 JSON 格式内容。

## name

gf_stock_valuation（广发证券股票市值与估值skill）

## 数据限制说明

建议单次查询少量股票进行对比，避免返回过多标的导致结果冗长，影响模型总结。

## 工具说明

### 工具 1：市值与估值对比

**service_name**: `quant`  
**tool_name**: `common_basic_post`

对比多只股票的总市值及估值水平。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_codes | array\<string\> | 是 | 股票代码列表，格式为交易所前缀+代码，如 `["SZ000776", "SH600000"]` |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| stock_code / stock_name | 股票代码 / 名称 |
| basic.list_date | 上市日期 |
| basic.total_marketcap | 总市值（亿元） |
| valuation.pettm | 市盈率 TTM |
| valuation.pettm_avg | PE 行业均值 |
| valuation.pettm_percent | PE 历史百分位 |
| valuation.pb | 市净率 |
| valuation.pb_avg | PB 行业均值 |
| valuation.pb_percent | PB 历史百分位 |

### 调用示例

```json
{
  "service_name": "quant",
  "tool_name": "common_basic_post",
  "args": {
    "stock_codes": ["SZ000776", "SZ000001"]
  }
}
```

### 工具 2：财务指标对比

**service_name**: `quant`  
**tool_name**: `compare_indicator_post`

对比两只股票在盈利能力、资本结构、现金流、成长性等维度的核心财务指标。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| report_type | integer | 是 | 报告期类型：`1`=一季报，`6`=中报，`9`=三季报，`12`=年报 |
| stock_codes | array\<string\> | 是 | 股票代码列表，格式为交易所前缀+代码，如 `["SZ000783", "SZ000776"]` |
| year | string | 是 | 报告年份，如 `2025` |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| year / report_type | 查询年份 / 报告期 |
| data[].stock_code / data[].stock_name | 股票代码 / 名称 |
| data[].end_date | 财报截止日期 |
| data[].roe | ROE |
| data[].net_profit2totalincome | 营业净利率 |
| data[].cashflow_oper2income | 收现比 |
| data[].net_cashflow_oper2net_profit | 净现比 |
| data[].equity2asset | 股东权益/总资产比 |
| data[].liablity2asset | 资产负债率 |
| data[].liab2equity | 产权比率 |
| data[].operate_income_yoy | 营业收入同比增长 |
| data[].net_profit_yoy | 净利润同比增长 |
| data[].total_asset_yoy | 总资产增长率 |

### 调用示例

```json
{
  "service_name": "quant",
  "tool_name": "compare_indicator_post",
  "args": {
    "report_type": 9,
    "stock_codes": ["SZ000783", "SZ000776"],
    "year": "2025"
  }
}
```

## 数据为空时

请检查：

1. 股票代码是否带有正确的市场前缀。
2. 股票代码是否使用大写格式。
3. 查询股票是否仍处于可查询状态。
4. 使用 `compare_indicator_post` 时，`report_type` 是否为 `1`、`6`、`9`、`12` 之一，且 `year` 填写完整有效。
