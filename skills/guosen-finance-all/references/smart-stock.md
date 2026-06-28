# 智能选股 — API 参考及调用示例

本模块提供国信证券智能选股接口的调用能力，用于根据财务指标、技术指标、市值等条件筛选符合条件的股票。

## 脚本

`scripts/stock_picking.py`

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `117859343_login_token`  | 从 `.xiaoyienv` 取出 `117859343_login_token`，国信智能选股 `login token`（必填） | 空 |

## 使用场景

当需要回答以下类型的问题时，使用此模块：
- 根据财务指标筛选股票（如市盈率、市净率、净利润等）
- 根据技术指标选股（如均线、MACD、KDJ等）
- 查找满足特定条件的股票组合
- 行业板块筛选
- 涨停板、跌停板股票查询
- 资金流向筛选

## 接口信息

### 基本信息

- **接口地址**: `/mcp/smart_stock_picking`
- **请求方法**: GET
- **完整URL**: `https://dgzt.guosen.com.cn/skills/agent/mcp/smart_stock_picking?searchstring={条件}&searchtype={类型}&apiKey=${117859343_login_token}&softName=xiaoyi_skills`
- **认证方式**: 通过请求参数apiKey进行身份验证

### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| searchstring | String | 是 | 选股条件，例如："市盈率小于20的银行股" |
| searchtype | String | 是 | 搜索类型，详见下表 |
| apiKey | String | 是 | API密钥，用于身份验证 |
| softName | String | 是 | 固定字符串 |

### searchtype 搜索类型

| 类型值 | 说明 |
|--------|------|
| stock | 股票 |
| fund | 基金 |
| HK_stock | 港股 |
| US_stock | 美股 |
| NEEQ | 新三板 |
| index | 指数 |

### 响应格式

成功响应：
```json
{
  "result": [{"code": 0, "msg": "请求成功"}],
  "data": {"tables": [/* 返回的数据表格 */]}
}
```

失败响应：
```json
{
  "result": [{"code": -1, "msg": "查询失败:no data."}],
  "data": null
}
```

## 调用示例

### 脚本运行方式

**前提条件**: 安装 Python 3.10 或更高版本，安装 urllib3 和 uuid-backport 库。

**运行命令**:
```bash
python scripts/stock_picking.py --searchstring "市盈率小于20的银行股" --searchtype stock --apiKey ${117859343_login_token}
```

**参数说明**:
| 参数 | 说明 | 示例 |
|------|------|------|
| --searchstring | 选股条件，中文描述即可 | "市盈率小于20的银行股" |
| --searchtype | 搜索类型 | stock, fund, HK_stock, US_stock, NEEQ, index |
| --apiKey | API密钥，用于身份验证 | ${117859343_login_token} |

### HTTP请求示例

```http
# 查询股票
GET /mcp/smart_stock_picking?searchstring=市盈率小于20的银行股&searchtype=stock&softName=xiaoyi_skills&apiKey=${117859343_login_token}

# 查询基金
GET /mcp/smart_stock_picking?searchstring=近一年收益超过20%的基金&searchtype=fund&softName=xiaoyi_skills&apiKey=${117859343_login_token}

# 查询港股
GET /mcp/smart_stock_picking?searchstring=当前macd为金叉的价格最高的前十只股票&searchtype=HK_stock&softName=xiaoyi_skills&apiKey=${117859343_login_token}

# 查询美股
GET /mcp/smart_stock_picking?searchstring=苹果相关股票&searchtype=US_stock&softName=xiaoyi_skills&apiKey=${117859343_login_token}

# 查询指数
GET /mcp/smart_stock_picking?searchstring=上证指数&searchtype=index&softName=xiaoyi_skills&apiKey=${117859343_login_token}

# 查新三板
GET /mcp/smart_stock_picking?searchstring=最近放量上涨的10家公司&searchtype=NEEQ&softName=xiaoyi_skills&apiKey=${117859343_login_token}
```

## 查询条件示例

| 查询类型 | 示例searchstring | 说明 |
|----------|------------------|------|
| 市盈率筛选 | "市盈率小于15的股票" | 筛选PE低于指定值的股票 |
| 市净率筛选 | "市净率小于2的股票" | 筛选PB低于指定值的股票 |
| 净利润筛选 | "净利润增长超过30%的股票" | 筛选净利润同比增长的股票 |
| 行业筛选 | "医药行业股票" | 筛选特定行业的股票 |
| 资金流向 | "主力资金净流入的股票" | 筛选资金流入的股票 |
| 涨停板 | "今日涨停的股票" | 筛选涨停股票 |
| 跌停板 | "今日跌停的股票" | 筛选跌停股票 |
| 综合筛选 | "市盈率小于20且净利润增长超过20%的科技股" | 多条件组合筛选 |

## `login token` 存储格式

在 `.xiaoyienv` 文件中，`login token` 按以下格式存储：
- `117859343_login_token`: 用户的国信证券 `login token`

首次使用流程：
1. 首先读取 `.xiaoyienv` 文件中的 `117859343_login_token` 字段
2. 如果不存在或为空，引导用户获取 `login token`
3. 用户提供 `login token` 后，将其写入 `.xiaoyienv`，字段名为 `117859343_login_token`

## 风险提示

选股结果最多仅显示符合条件的100只股票信息，但由于选股结果显示顺序的不确定性，以及系统重启操作等均可能导致相同条件下的股票排序发生变化，请投资者充分知悉。选股结果和实时行情可能有一定差异，选股结果仅作参考，不构成投资建议，请用户自主决策并自行承担投资风险。

## 注意事项

1. **认证方式**: 请求通过 MCP 网关统一鉴权，需提供有效的 `login token`
2. **查询内容**: searchstring 参数需要清晰描述筛选条件，用户输入的中文描述即可
3. **搜索类型**: 根据查询目标选择正确的 searchtype 参数
4. **返回数据**: 返回的股票数据可能包含多个字段，具体字段取决于查询条件
5. **错误处理**: 脚本会捕获请求异常并打印错误信息
6. **风险提示**: 每次调用后固定输出风险提示文案
