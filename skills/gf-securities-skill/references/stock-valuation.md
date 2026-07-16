# 广发证券股票市值与估值skill（gf_stock_valuation）

通过**结构化参数**调用广发证券估值工具，接口返回 JSON 格式内容。

## name

gf_stock_valuation（广发证券股票市值与估值skill）

## 数据限制说明

建议单次查询少量股票进行对比，避免返回过多标的导致结果冗长，影响模型总结。

## 工具说明

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

## 数据为空时

请检查：

1. 股票代码是否带有正确的市场前缀。
2. 股票代码是否使用大写格式。
3. 查询股票是否仍处于可查询状态。
