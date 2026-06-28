# 广发证券基金定投计算器skill（gf_fund_invest）

通过**结构化参数**调用广发证券基金定投计算工具，接口返回 JSON 格式内容。

## name

gf_fund_invest（广发证券基金定投计算器skill）

## 数据限制说明

定投明细可能非常长，尤其是按日定投或长区间回测。建议缩短回测区间，或优先关注汇总结果字段。

## 工具说明

**service_name**: `fund_invest`  
**tool_name**: `finance_api_product_invest_compute_post`

模拟指定基金在历史区间内的定投收益。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tradeCode | string | 是 | 基金代码，如 `001643` |
| balance | number | 是 | 每期定投金额（元） |
| startDate | string | 是 | 开始日期，格式 `YYYYMMDD` |
| endDate | string | 是 | 结束日期，格式 `YYYYMMDD` |
| rate | string | 是 | 扣款频率：`0`=每月，`1`=每周，`2`=每天，`3`=每双周 |
| enFundDate | string | 否 | 扣款日 |
| strategyList | array | 是 | 策略列表 |

### strategyList 常用字段

| 字段 | 说明 |
|------|------|
| prodAIRationType | `0`=普通定投，`1`=指数均线，`2`=目标止盈，`3`=移动止盈，`4`=均线+目标止盈，`5`=均线+移动止盈 |
| prodIndexType | 参考指数 |
| prodAverageType | 均线类型 |
| expectIncomeRatio | 止盈目标收益率 |
| backRate | 移动止盈回撤比例 |
| lockPeriod | 止盈锁定期（月） |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| fee | 定投费率 |
| fundEarning | 基金区间净值涨幅 |
| strategyInvestResultList[].investInfoList | 每日或每期定投记录 |
| investInfoList[].date | 日期 |
| investInfoList[].nav | 当日净值 |
| investInfoList[].investMoney / totalInvestMoney | 本次投入 / 累计投入 |
| investInfoList[].earning / earningRate | 累计收益 / 累计收益率 |
| investInfoList[].historyMaxEarningRate | 历史最大收益率 |
| investInfoList[].backRate | 当前最大回撤 |

### 调用示例

```json
{
  "service_name": "fund_invest",
  "tool_name": "finance_api_product_invest_compute_post",
  "args": {
    "tradeCode": "001643",
    "balance": 1000,
    "rate": "0",
    "startDate": "20200101",
    "endDate": "20250101",
    "enFundDate": "1",
    "strategyList": [{
      "prodAIRationType": "4",
      "prodIndexType": "0",
      "prodAverageType": "0",
      "expectIncomeRatio": "0.2"
    }]
  }
}
```

## 数据为空时

请检查：

1. 基金代码是否正确。
2. 回测时间区间是否有效。
3. 策略参数是否满足对应策略的必填要求。
