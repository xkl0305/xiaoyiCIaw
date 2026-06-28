# 广发证券ETF超级资金异动skill（gf_etf_super_fund）

通过**结构化参数**调用广发证券 ETF 资金异动工具，接口返回 JSON 格式内容。

## name

gf_etf_super_fund（广发证券ETF超级资金异动skill）

## 数据限制说明

建议一次仅查询一种异动类型，便于模型聚焦分析。若需对比多种类型，可拆分多次请求。

## 工具说明

**service_name**: `etf-super-fund`  
**tool_name**: `gfmiddle_eits_super_fund_etf_superfund_get`

查询发生超级资金异动的 ETF 列表。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 异动类型：`大幅流入`、`大幅流出`、`持续流入`、`持续流出` |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| etfcode / etfname | ETF 代码 / 简称 |
| mktCd | 市场，`SH` / `SZ` |
| tradeDate | 交易日期 |
| fndNet | 当日资金净流入（万元） |
| fndNetPercent | 资金强度（%） |
| estimatedFundingCost | 资金估算成本 |
| capitalProfitMargin | 资金盈利水平 |
| details[].tradeDate / fndNetIn | 历史明细：日期 / 当日资金净流入 |

### 调用示例

```json
{
  "service_name": "etf-super-fund",
  "tool_name": "gfmiddle_eits_super_fund_etf_superfund_get",
  "args": {
    "type": "大幅流入"
  }
}
```

## 数据为空时

请检查：

1. 异动类型是否为接口支持的固定值。
2. 当前交易日是否存在对应类型的异动 ETF。
