# 广发证券ETF多维度筛选skill（gf_etf_search）

通过**结构化参数**调用广发证券 ETF 筛选工具，接口返回 JSON 格式内容。

## name

gf_etf_search（广发证券ETF多维度筛选skill）

## 数据限制说明

该工具支持大量可选参数。建议优先传入最关键的 2 到 4 个筛选条件，并使用 `limit` 控制结果规模。

## 工具说明

**service_name**: `etf_search`  
**tool_name**: `finance_api_inclusive_etf_list_get`

按多维条件筛选 ETF。

### 常用输入参数

| 参数 | 说明 |
|------|------|
| search | 模糊搜索代码或名称 |
| type | ETF 类型，如 `股票ETF`、`境外ETF` |
| trakType | ETF 赛道分类，如 `宽基`、`行业` |
| oneTrakName | 一级赛道名称，如 `科技` |
| tradeCode | 交易代码，多个逗号分隔 |
| tradeT0 | 是否 T+0，`1`=是 |
| marginTrade | 是否两融，`1`=是 |
| roc1w / roc1m / roc6m / roc1y | 区间涨跌幅条件 |
| return1m / return6m / return1y / return3y | 收益率条件 |
| maxDrawdown1m / maxDrawdown1y | 最大回撤条件 |
| sharpRatio1y / sharpRatio3y | 夏普比率条件 |
| valuationResult | 估值区，`1`=低位，`2`=中位，`3`=高位 |
| indexTempType | 指数温度，`low` / `ord` / `high` |
| assetScale | 基金规模区间 |
| start / limit | 分页参数 |
| sort | 排序字段，降序加 `-` 前缀 |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| tradeCode / secuAbbr / extName | 代码 / 简称 / 场内名称 |
| exchangeCode | 市场，`101`=SH，`105`=SZ |
| fiInfoName / fiInfoCode | 跟踪指数名称 / 代码 |
| fundSize / assetScale | 基金市值 / 资产规模 |
| pe / pePercent / pb / pbPercent | PE/PB 及百分位 |
| roc / roc1w / roc1m / roc6m / roc1y | 当日及阶段涨跌幅 |
| netMainForce1d / netMainForce5d | 主力净流入 |
| premium | 溢价率 |
| indexTempType | 指数温度 |
| trakName / trakType | 赛道主题 |

### 调用示例

```json
{
  "service_name": "etf_search",
  "tool_name": "finance_api_inclusive_etf_list_get",
  "args": {
    "trakType": "行业",
    "roc1m": "5~",
    "sort": "-roc1m",
    "limit": 20,
    "addRealTimeRoc": 1
  }
}
```

## 数据为空时

请检查：

1. 区间筛选格式是否正确，例如 `5~`、`0~20`。
2. 枚举值是否符合接口约束。
3. 条件是否过于严格导致无结果。
