---
name: xyzq-financial
displa_name: 兴业证券知己理财Skills
description: 兴业证券官方金融技能，知己管家和专业投顾能力加持，开箱即用！(1)自选管理：快速查看自选股，高效维护标的池；；(2)金融数据：查公告、财报、历史行情，轻松掌握基本面；(3)实时行情：股票、基金、指数、债券，多品种覆盖快速响应(4)兴证热榜：一览市场热点股票、ETF、资讯榜单
homepage: https://static.xyzq.cn/ai-skill-h5/skill.html#/skill-list
author: 兴业证券知己理财团队
version: 1.1.0
env:
  - 117981469_login_token: API调用凭证token，仅当实际调用 API 执行时才需要此凭证，仅介绍/说明 skill 时无需凭证，凭证获取方式："从 /home/sandbox/.openclaw/.xiaoyienv 文件中读取账号凭证；若为空，或当前时间大于 ${117981469_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool工具（工具参数：clientId=117981469，skillName=xyzq-financial）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 117981469_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# 兴业证券知己理财一站式技能 (xyzq-financial)

本技能整合了兴业证券的 4 大核心功能，统一凭证认证流程。

## 🔐 统一凭证认证流程（每次调用必须执行）

> ⚠️ **强制规则：每次调用前都必须重新检查凭证状态，不得复用历史会话中的检查结果。**

凭证信息保存在 `/home/sandbox/.openclaw/.xiaoyienv` 文件。

### 什么时候需要凭证？

| 场景                 | 示例                              | 需要凭证？            |
|:------------------ |:------------------------------- |:----------------:|
| **📖 介绍/说明 skill** | "介绍一下xyzq-financial"、"给出快速开始样例" | ❌ **不需要**，直接介绍即可 |
| **🔎 调用API查询/操作**  | 查询实时行情、操作自选股、查询金融数据             | ✅ **必须**走认证流程    |

### 认证流程（仅 API 调用时执行）

1️⃣ 检查 `.xiaoyienv` 凭证

读取文件，检查 `117981469_login_token` 和 `117981469_login_token_expire_time`。

- **有值且未过期** ✅ → 直接凭证就绪
- **为空/不存在/已过期（即当前时间大于 `117981469_login_token_expire_time`）** ❌ → 进入步骤 2

2️⃣ 调用 `huawei_id_tool` 获取授权

参数：`clientId=117981469`，`skillName=xyzq-financial`

- **授权成功** ✅ → 重新读取 `.xiaoyienv` 获取 `117981469_login_token`，凭证就绪
- **授权失败** ❌ → 最多重试一次，仍失败则停止并告知用户

3️⃣ 所有请求头统一使用 `login-token: ${117981469_login_token}`

## ⚠️流程要点

- 所有请求头统一使用 `login-token: ${117981469_login_token}`。

- 凭据只从.xiaoyienv文件读取，禁止写死到代码或示例以外的固定位置。

- **每次用户发起查询请求时，都必须走一次上述流程**。不能假设上次授权的 token 仍然有效——环境重置、文件覆盖等都可能导致 token 丢失。

- 凭证认证流程中步骤 1 的判断逻辑**必须执行**（哪怕刚授权过），因为 `.xiaoyienv` 文件可能被外部重置。

## 🧭 兴业证券知己理财金融技能功能列表

本技能套件，提供一站式金融数据查询、热榜查询。行情分析、选股筛股。所有子技能通过统一的 `login-token` 认证，支持自然语言交互。

根据用户意图选择对应的子技能：

| 技能名称               | 功能描述                            | 详细文档                                                                   | API 端点                                           |
| ------------------ | ------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------ |
| xz-realtime-quotes | 最新价、实时行情、股价、涨跌幅、成交量             | **实时行情** → [xz-realtime-quotes.md](./references/xz-realtime-quotes.md) | `/claw/realtime-quotes-query`                    |
| xz-hot-rank        | 热榜、热搜、加自选榜、浏览榜、大家都在看            | **兴证热榜** → [xz-hot-rank.md](./references/xz-hot-rank.md)               | `/claw/trending-topics-query`                    |
| xz-self-select     | 自选股、我的自选、加自选、删自选、自选列表           | **自选股管理** → [xz-self-select.md](./xz-references/self-select.md)        | `/claw/self-select-query` / `self-select-manage` |
| xz-finance-data    | 公告、财报、利润表、资产负债表、现金流量表、历史行情、财务数据 | **金融数据查询** → [xz-finance-data.md](./xz-references/finance-data.md)     | `/claw/finance-data/*`                           |

## ⚠️ 强制通用输出规则- 附加提示文案（必须严格遵守）

1. **强制免责声明**：所有查询结果输出的最后，必须追加：
   
   ```
   以上内容通过技能（skill）自主调用数据生成，其准确性依赖底层模型的理解与处理能力，不保证信息完全无误，仅供参考，实际数据以兴业证券app（优理宝）平台数据为准。市场有风险，投资需谨慎。
   ```

2. **多条查询拆开放置**：查询多个股票时拆分成多次请求

3. **单位规范**：价格带"元"，成交量带"手"，金额带"亿元/万元"

4. **空值处理**：数据为空时显示"--"

## 📖 子技能参考文档

- [实时行情 (realtime-quotes)](./references/realtime-quotes.md) — 查询逻辑、涨跌颜色规则、展示格式
- [兴证热榜 (hot-rank)](./references/hot-rank.md) — 榜单类型、热度图标映射、展示格式
- [自选股管理 (self-select)](./references/self-select.md) — 查询/添加/删除逻辑、输出模板
- [金融数据查询 (finance-data)](./references/finance-data.md) — 公告/利润表/负债表/现金流量表/财报/历史行情

## ⚠️ 注意事项

- 查询多个股票时，拆分成多次独立请求
- 不支持理财类产品热榜查询
- `huawei_id_tool` 最多重试一次
- 遇到 `{"code":2,"msg":"登录失效"}` 等异常时，重新走凭证认证流程
