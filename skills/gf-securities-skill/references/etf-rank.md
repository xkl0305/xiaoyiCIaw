# 广发证券ETF榜单skill（gf_etf_rank）

通过**结构化参数**调用广发证券 ETF 榜单工具，接口返回 JSON 格式内容。

## name

gf_etf_rank（广发证券ETF榜单skill）

## 数据限制说明

建议结合 `size` 和 `page` 控制返回条数，避免一次性拉取过多榜单数据。

## 工具说明

**service_name**: `etf_rank`  
**tool_name**: `finance-api_product_etf_rank_get`

获取各类 ETF 榜单数据。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | integer | 是 | 榜单类型：`1`=涨幅，`2`=跌幅，`3`=换手，`4`=主力资金，`12`=净申购，`13`=溢价率 |
| page | integer | 否 | 页数，从 `0` 开始 |
| size | integer | 否 | 每页条数，默认 `10` |
| sameIndexFilter | integer | 否 | 同指数 ETF 只展示 1 只：`1`=开启，`0`=关闭 |
| continueRiseLimit | integer | 否 | 连涨/连跌天数过滤 |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| code / name / ext_name | ETF 代码 / 简称 / 场内全名 |
| exchange | 市场，`101`=上海，`105`=深圳 |
| roc / fiveRoc | 当日涨跌幅 / 5日涨跌幅 |
| volume / cashFlow | 成交额 / 主力资金净流入 |
| turnover_rate | 换手率 |
| fundSize | 基金规模 |
| trackIndexName | 跟踪指数名称 |
| continueRiseDay | 连涨天数 |
| premium | 溢价率 |

### 调用示例

```json
{
  "service_name": "etf_rank",
  "tool_name": "finance-api_product_etf_rank_get",
  "args": {
    "type": 1,
    "size": 20
  }
}
```

## 数据为空时

请检查：

1. 榜单类型是否在支持范围内。
2. 分页参数是否合理。
3. 查询时点是否存在对应榜单数据。
