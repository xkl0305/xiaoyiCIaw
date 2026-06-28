# A股、港股财务数据查询 — API 参考及调用示例

本模块提供查询 A 股、港股财务数据的能力，包括利润表、资产负债表、现金流量表等财务报表数据。

## 脚本

`scripts/stock_financial_get_data.py`

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `117859343_login_token` | 从 `.xiaoyienv` 取出 `117859343_login_token`，国信接口鉴权 key（必填） | 空 |

## 调用示例

### 命令行调用

<env>
```bash
# Windows PowerShell
$env:117859343_login_token="${117859343_login_token}"

# macOS / Linux
export 117859343_login_token="${117859343_login_token}"
```
</env>

```bash
# 查询A股资产负债表
python3 scripts/stock_financial_get_data.py a_balance --code 600519 --market SH

# 查询A股利润表
python3 scripts/stock_financial_get_data.py a_income --code 600519 --market SH --report_type Q4

# 查询A股现金流量表
python3 scripts/stock_financial_get_data.py a_cashflow --code 600519 --market SH --count 4

# 查询港股资产负债表
python3 scripts/stock_financial_get_data.py hk_balance --code 02020

# 查询港股利润表
python3 scripts/stock_financial_get_data.py hk_income --code 02020 --count 4

# 查询港股现金流量表
python3 scripts/stock_financial_get_data.py hk_cashflow --code 02020
```

### 代码调用

```python
from scripts.stock_financial_get_data import (
    query_a_stock_balance_sheet,
    query_a_stock_income_statement,
    query_a_stock_cash_flow_statement,
    query_hk_stock_balance_sheet,
    query_hk_stock_income_statement,
    query_hk_stock_cash_flow_statement,
)

# 查询A股资产负债表
result = query_a_stock_balance_sheet("600519", "SH")

# 查询A股利润表
result = query_a_stock_income_statement("600519", "SH", report_type="Q4")

# 查询A股现金流量表
result = query_a_stock_cash_flow_statement("600519", "SH", count=4)

# 查询港股资产负债表
result = query_hk_stock_balance_sheet("02020")

# 查询港股利润表
result = query_hk_stock_income_statement("02020", count=4)

# 查询港股现金流量表
result = query_hk_stock_cash_flow_statement("02020")
```

## 功能范围

### 1. 查询A股资产负债表

**接口**: `GET /gsnews/gsf10/financial/balanceSheet/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码，如 `600000`, `000001` |
| market | 是 | string | 证券市场，SH-上海，SZ-深圳 |
| reportType | 否 | string | 财报类型：Q0-最新，Q4-年报，Q2-半年报，Q3-三季报，Q1-一季报，默认为Q0 |
| reportYear | 否 | string | 财报年份，如 `2024` |
| count | 否 | string | 财报数量 |

### 2. 查询A股利润表

**接口**: `GET /gsnews/gsf10/financial/incomeStatement/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| market | 是 | string | 证券市场，SH-上海，SZ-深圳 |
| reportType | 否 | string | 财报类型：Q0-最新，Q4-年报，Q2-半年报，Q3-三季报，Q1-一季报，默认为Q0 |
| reportYear | 否 | string | 财报年份 |
| count | 否 | string | 财报数量 |

### 3. 查询A股现金流量表

**接口**: `GET /gsnews/gsf10/financial/cashFlowStatement/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| market | 是 | string | 证券市场，SH-上海，SZ-深圳 |
| reportType | 否 | string | 财报类型：Q0-最新，Q4-年报，Q2-半年报，Q3-三季报，Q1-一季报，默认为Q0 |
| reportYear | 否 | string | 财报年份 |
| count | 否 | string | 财报数量 |

### 4. 查询港股资产负债表

**接口**: `GET /gsnews/hkf10/financial/balanceSheet/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码，如 `02020` |
| market | 是 | string | 证券市场，HK |
| reportYear | 否 | string | 报告日期，如 `2021-06-30` |
| reportType | 否 | string | 报告类型：Q1-一季报，Q2-中报，Q3-三季报，Q4-年报 |
| count | 否 | string | 查询期数，默认为1 |

### 5. 查询港股利润表

**接口**: `GET /gsnews/hkf10/financial/incomeStatement/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| market | 是 | string | 证券市场，HK |
| reportYear | 否 | string | 报告日期 |
| reportType | 否 | string | 报告类型：Q1-一季报，Q2-中报，Q3-三季报，Q4-年报 |
| count | 否 | string | 查询期数，默认为1 |

### 6. 查询港股现金流量表

**接口**: `GET /gsnews/hkf10/financial/cashFlowStatement/1.0`

**参数**:
| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| code | 是 | string | 证券代码 |
| market | 是 | string | 证券市场，HK |
| reportYear | 否 | string | 报告日期 |
| reportType | 否 | string | 报告类型：Q1-一季报，Q2-中报，Q3-三季报，Q4-年报 |
| count | 否 | string | 查询期数，默认为1 |

## 返回字段说明

各接口统一返回格式如下:

```json
{
    "result": {
        "code": 0,
        "msg": "请求成功"
    },
    "data": { ... }
}
```

**数据字段匹配规则**: 返回数据中的字段值通过 info 数组中的 key 匹配获取具体指标值。

## 典型查询示例

### 基础财务指标查询
1. 贵州茅台近三年的营业收入和净利润是多少？
2. 宁德时代最新季度的毛利率和净利润率分别是多少？
3. 比亚迪的资产负债率和流动比率如何？

### 财务三表查询
1. 查询中国平安2024年的利润表关键数据
2. 招商银行最近五年的资产负债表核心指标
3. 对比贵州茅台、五粮液、泸州老窖近三年的毛利率
4. 查询宁德时代、比亚迪的营收增长率、净利润、ROE
5. 超出5个实体时，系统自动截取前5家进行查询

### 港股财务数据查询
1. 查询腾讯控股最新的关键财务指标
2. 小米集团近三年的营业收入和归母净利润
3. 阿里巴巴港股的资产负债表和现金流量表

### 单季度与 TTM 查询
1. 宁德时代2024Q3的单季度营业收入和归母净利润
2. 格力电器 EPS TTM 和 ROE TTM
3. 美的集团最近四个季度的单季度净利润环比变化

### 研发与分红数据
1. 查询科大讯飞近三年的研发费用及研发费用率
2. 中国神华历年分红金额和股息率

## 常见问题

**错误: `login token` is required.**
→ 需配置 `login token`，请联系管理员获取并手动配置

**接口返回错误怎么办？**
→ 检查证券代码是否正确，确认市场代码是否匹配

## 注意事项
- 如果 API 调用失败，直接提醒用户"数据获取失败"，**不要**尝试从联网搜索或其他渠道获取数据
- 返回数据仅供参考，不作为投资建议
