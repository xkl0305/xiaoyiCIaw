# 广发证券龙虎榜个股列表skill（gf_lhb_list）

通过**结构化参数**调用广发证券龙虎榜工具，接口返回 JSON 格式内容。

## name

gf_lhb_list（广发证券龙虎榜个股列表skill）

## 数据限制说明

请优先查询单个交易日的数据。若连续跨多个日期批量查询，建议拆分请求，避免返回内容过长。

## 工具说明

**service_name**: `lhb`  
**tool_name**: `lhb_aborttrade_market_date_get`

获取指定日期、指定市场上榜的异常交易个股列表。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | integer | 是 | 日期，格式 `YYYYMMDD`，如 `20260313` |
| market | string | 是 | 交易市场：`sh`=上海，`sz`=深圳 |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| trdCode | 交易代码 |
| secuSht | 证券简称 |
| clsPrc | 收盘价 |
| dayChgRat | 日涨跌幅（%） |
| tnvVol / tnvVal | 成交量 / 成交额（元） |
| items[].rsnSht | 上榜原因 |
| items[].rsnCode | 上榜原因代码 |
| items[].beginDate / endDate | 统计区间 |

### 调用示例

```json
{
  "service_name": "lhb",
  "tool_name": "lhb_aborttrade_market_date_get",
  "args": {
    "date": 20260313,
    "market": "sh"
  }
}
```

## 数据为空时

请检查：

1. 日期是否为交易日。
2. 市场参数是否为 `sh` 或 `sz`。
3. 当日对应市场是否存在龙虎榜上榜个股。
