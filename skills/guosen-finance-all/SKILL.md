---
name: guosen-finance-all
display_name: 国信证券金融数据综合套件
title: 国信证券金融数据综合套件
description: 国信证券金融数据综合套件，聚合宏观经济、ETF筛选、基金对比、智能选股、财务数据、股市行情六大模块。当用户需要查询宏观经济指标、筛选ETF、对比基金、智能选股、查询财务报告或股市行情数据时使用此技能。
homepage: https://www.guosen.com.cn/gs/xxskills/index.html
author: 国信证券金太阳团队
version: 1.0.0
env:
  - `117859343_login_token`: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取账号凭证；若为空，或当前时间大于 ${117859343_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=12345678，skillName=guosen-finance-all）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - `117859343_login_token_expire_time`: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
  - GS_API_KEY: "可选；当无法获取 117859343_login_token 且无法通过 huawei_id_tool 刷新时，从`homepage`获取，作为请求参数 apiKey 调用接口"

---
dependency:
  python:
    - httpx>=0.24.0
    - pandas>=1.5.0
    - openpyxl>=3.1.0
    - matplotlib>=3.5.0
    - uuid-backport>=0.1.2
    - urllib3>=1.26.0
---

# 国信证券金融数据综合套件

本套件聚合国信证券六大金融数据查询模块，基于国信证券专业数据库，覆盖宏观经济、ETF 筛选、基金对比、智能选股、财务报表及股市行情等场景。

## 服务地址

默认服务地址: `https://dgzt.guosen.com.cn/skills`

## 模块概览

本套件包含以下六个功能模块，每个模块对应一个独立脚本和一份参考文档：

| 模块 | 脚本 | 参考文档 | 功能说明 |
|------|------|----------|----------|
| 宏观经济查询 | `scripts/economy_get_data.py` | `references/economy.md` | 查询全球宏观经济数据，包括 GDP、CPI、PPI、利率、汇率、大宗商品价格等 |
| ETF 筛选 | `scripts/etf_get_data.py` | `references/etf-filter.md` | 提供 ETF 专业榜单筛选与自定义多维分析 |
| 基金对比 | `scripts/fund_compare_get_data.py` | `references/fund-compare.md` | 场外基金多维度对比分析，含业绩走势、风险控制、资产配置等 |
| 智能选股 | `scripts/stock_picking.py` | `references/smart-stock.md` | 根据财务指标和技术指标筛选符合条件的股票 |
| 财务数据查询 | `scripts/stock_financial_get_data.py` | `references/stock-financial.md` | 查询 A 股、港股财务数据，包括三张财务报表 |
| 股市行情查询 | `scripts/stock_market_get_data.py` | `references/stock-market.md` | 查询沪深 A 股、北交所、港股、美股的实时行情、历史行情、资金流向等 |

> **使用方式**: 当智能体需要调用某个模块时，先读取对应的 `references/*.md` 了解该模块的具体接口参数和调用示例，然后执行对应的 `scripts/*.py` 脚本。

## 环境要求

- **Python 3.10 及以上版本**

## 密钥来源与安全说明

- 本套件各模块使用 `login token` 进行接口鉴权，由国信证券接口服务签发。
- 在提供密钥前，先确认密钥来源、可用范围、有效期及是否支持重置/撤销。
- **禁止在代码、提示词、日志或输出文件中硬编码/明文暴露密钥**。

### 各模块 `login token` 环境变量

不同模块使用不同的环境变量名称，调用前需根据模块设置对应的环境变量：

| 模块 | 环境变量名 | 存储位置 |
|------|-----------|----------|
| 宏观经济查询 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |
| ETF 筛选 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |
| 基金对比 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |
| 智能选股 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |
| 财务数据查询 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |
| 股市行情查询 | `117859343_login_token` | `.xiaoyienv` → `117859343_login_token` |


### 步骤 1: 凭据说明
- 统一读取/home/sandbox/.openclaw/.xiaoyienv文件 `117859343_login_token` 和 `117859343_login_token_expire_time`。
- 若 `117859343_login_token` 为空，或当前时间大于 `117859343_login_token_expire_time`，调用一次  huawei_id_tool工具（工具参数：clientId=117859343，skillName=guosen-finance-all）刷新凭证，仅需调用一次，不可重复调用。
- 刷新成功后重新读取.xiaoyienv文件，再继续后续业务逻辑。
- 所有请求头统一使用 `login-token: ${117859343_login_token}`。
- 凭据只从.xiaoyienv文件读取，禁止写死到代码或示例以外的固定位置。

### 步骤 2: 执行查询

1. 根据用户需求确定使用哪个模块
2. 读取对应的 `references/*.md` 了解接口参数和调用方式
3. 设置对应的环境变量（从 `.xiaoyienv` 读取）
4. 调用对应的 `scripts/*.py` 脚本执行查询, 技能调用接口所需要的apiKey也用从环境变量中获取的 `117859343_login_token` 赋值
5. 解析脚本输出并向用户展示结果

## 通用调用规范
1. 所有接口均使用 `POST`。
2. 所有请求头均包含 `Content-Type: application/json` 和 `login-token`。
3. 先根据用户意图选择能力模块，再调用对应代理接口。
4. 查询结果为空时，优先提示用户收窄或细化条件。
5. 若遇到登录状态异常，优先检查凭证是否缺失或过期，再调用一次  huawei_id_tool工具（工具参数：clientId=117859343，skillName=guosen-finance-all）刷新凭证，仅需调用一次，不可重复调用。

### 通用请求头示例：
```js
--header 'login-token: ${117859343_login_token}'
```


## 通用合规说明

- `login token` 需从持久化存储文件读取，不要硬编码
- 调用脚本前必须设置对应的环境变量
- **如果 API 调用失败，直接提醒用户"数据获取失败"，不要尝试从联网搜索或其他渠道获取数据**
- 禁止在代码或提示词中硬编码账号 ID 或 token
- 环境变量按敏感信息处理，不在日志或回复中泄露
- 返回数据仅供参考，不作为投资建议

## 通用注意事项

- 各模块脚本的参数说明和调用示例请参考 `references/` 目录下对应的文档
- 不同模块的脚本可能依赖不同的 Python 库，首次使用前确保依赖已安装
- 脚本执行可能生成中间输出文件（如 xlsx、txt），智能体应读取解析后直接向用户呈现数据，不应展示文件路径
- 每次查询结束后，根据各模块要求附上相应的风险提示文案
