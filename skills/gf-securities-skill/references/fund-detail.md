# 广发证券基金详情skill（gf_fund_detail）

通过**结构化参数**调用广发证券基金详情工具，接口返回 JSON 格式内容。

## name

gf_fund_detail（广发证券基金详情skill）

## 数据限制说明

该工具适合单只基金详情查询。如需批量比对基金，建议分批请求并提炼核心字段。

## 工具说明

**service_name**: `jijin_info`  
**tool_name**: `finance-api_product_fund_detail_get`

查询基金完整信息，包括基本信息、净值、收益率、风险等级、申购赎回规则和基金经理等。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tradeCode | string | 是 | 基金交易代码，如 `519002` |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| tradeCode / chiName / secuAbbr | 基金代码 / 全名 / 简称 |
| fundType | 基金类型 |
| riskLevel | 风险等级 |
| shareNav | 最新份额净值 |
| return1w / return1m / return3m / return6m / return1y / return3y / returnTn | 各阶段收益率 |
| assetScale | 基金资产规模 |
| fundManageCorp | 基金管理公司 |
| contractEffDate | 基金成立日期 |
| prodStatus | 基金状态 |
| isAllowBuy / isAllowRedeem | 是否可购买 / 赎回 |
| min_share / min_share2 | 最低认购 / 申购金额 |
| extraInfo.investTarget | 投资目标 |
| extraInfo.riskReturnFeature | 风险收益特征 |
| report | 基金综合评价 |

### 调用示例

```json
{
  "service_name": "jijin_info",
  "tool_name": "finance-api_product_fund_detail_get",
  "args": {
    "tradeCode": "519002"
  }
}
```

## 数据为空时

请检查：

1. 基金代码是否正确。
2. 该基金是否仍处于可查询状态。
