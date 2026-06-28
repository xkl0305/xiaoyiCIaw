# 广发证券股票F10基础信息skill（gf_stock_f10）

通过**结构化参数**调用广发证券 F10 工具，接口返回 JSON 格式内容。

## name

gf_stock_f10（广发证券股票F10基础信息skill）

## 数据限制说明

该工具适合单只股票查询。如需批量拉取多只个股基础信息，建议分批请求，避免结果过长。

## 工具说明

**service_name**: `wechat_f10`  
**tool_name**: `f10_basic_post`

查询个股基本面信息，包括公司全名、板块、上市日期、主营业务和所属行业。

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 证券代码（纯数字），如 `000776` |
| market | string | 是 | 市场（大写）：`SH`=上海，`SZ`=深圳 |

### 关键返回字段

| 字段 | 说明 |
|------|------|
| compName | 公司全称 |
| boardName | 板块 |
| listDate | 上市日期 |
| businessScope | 主营业务范围 |
| industries | 所属行业 |

### 调用示例

```json
{
  "service_name": "wechat_f10",
  "tool_name": "f10_basic_post",
  "args": {
    "code": "000776",
    "market": "SZ"
  }
}
```

## 数据为空时

请检查：

1. 股票代码是否为纯数字。
2. 市场参数是否为 `SH` 或 `SZ`。
3. 代码与市场是否匹配。
