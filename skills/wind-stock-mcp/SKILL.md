---
name: wind-stock-mcp
description: 聚合 Wind 金融数据查询与金融文档搜索能力，可查询股票、债券、基金等资产的行情、价格、成交量、估值、财务指标和经营数据，也可检索新闻、公告、研报、政策法规、事件、舆情及金融知识。用户需要证券数据查询、客观指标比较、历史区间统计、金融资讯搜索、事件核验或数据与文档整理时使用。本 Skill 仅提供客观数据和文档信息，禁止推荐股票或提供投资建议。
version: 1.0.1
env:
  - 118586461_login_token: "从/home/sandbox/.openclaw/.xiaoyienv文件中读取账号凭证；若为空，或当前时间大于 ${118586461_login_token_expire_time} 的取值（即凭证已过期），调用一次 huawei_id_tool 工具（工具参数：clientId=118586461，skillName=wind-stock-mcp）刷新凭证；刷新成功后重新读取账号凭证，继续执行后续业务逻辑"
  - 118586461_login_token_expire_time: "账号凭证过期时间；当前时间大于该值时需先刷新凭证再继续调用"
---

# Wind 金融查询 Skill

提供金融数据查询和金融文档搜索两类能力。调用工具时统一使用以下 MCP 入口：

`https://t.wind.com.cn/wstock_share/ai/Wind.MCP.Server/vserver/vserver_stock_investment/mcp/`

## 凭据规则

1. 仅从 `/home/sandbox/.openclaw/.xiaoyienv` 读取 `118586461_login_token` 和
   `118586461_login_token_expire_time`。
2. 若 token 为空或当前时间晚于过期时间，调用一次 `huawei_id_tool`：

   ```json
   {
     "clientId": "118586461",
     "skillName": "wind-stock-mcp"
   }
   ```

3. 刷新成功后重新读取 `.xiaoyienv`，不得从刷新工具返回文本中猜测或提取 token。
4. 单次用户任务中最多刷新一次。若刷新后 token 仍不可用或仍鉴权失败，停止业务调用并提示用户重新授权。
5. 禁止在回答、日志、请求体或报错详情中输出 token。

## 能力选择

| 能力 | 典型意图 | 首选工具 |
|---|---|---|
| 金融数据 | 行情、价格、涨跌幅、成交量、估值、财务指标、经营数据、历史区间、证券比较 | `financial_query_data` |
| 金融文档 | 新闻、公告、研报、政策法规、事件、舆情、金融知识、帮助内容 | `fin_doc_searchV3` |

- 用户同时需要结构化数据和文档依据时，分别调用两个工具，再按时间与标的综合结果。
- 意图不清但明显属于数值或指标查询时，优先选择 `financial_query_data`。
- 当实时 `tools/list` 同时返回 `financial_query_data` 与 `natural_language_get_financial_data` 时，新的金融数据查询优先使用 `financial_query_data`；旧工具仅用于兼容已有流程。
- 证券简称存在歧义时，在问题中补充市场或证券代码；无法可靠判断时先向用户确认。

## 合规边界

- 仅查询、整理、计算、比较和展示客观金融数据及文档信息，不得替用户作出投资决策。
- 禁止推荐任何股票或其他证券；禁止给出买入、卖出、持有、加仓、减仓、目标价、仓位配置、收益预测或收益承诺等意见。
- 用户要求荐股、选择“最值得买”的证券或索取操作建议时，明确说明本 Skill 仅提供客观数据，不能提供证券推荐或投资建议；可请用户指定证券、指标和时间范围后继续查询数据。
- 可按用户明确指定的客观指标进行计算、排序或比较，但必须说明指标和时间口径，不得据此得出“值得买”“应买入”等投资结论。
- 检索到的研报评级或第三方投资观点只能作为文档信息客观转述，并明确标注来源和日期，不得表示认同、背书或将其转化为本 Skill 的推荐。

## 调用流程

### 1. 检查凭据

按“凭据规则”读取并校验 token。所有 MCP 请求统一使用：

```text
Content-Type: application/json
Accept: application/json, text/event-stream
accessToken: ${118586461_login_token}
```

### 2. 动态获取工具列表

处理每个新的用户任务时，必须先向 MCP 入口发送 `POST`：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

以本次 `tools/list` 返回的工具名称、描述和 `inputSchema` 为最终依据。不得调用列表中不存在的工具，也不得向工具传入 schema 未声明的参数。

### 3. 构造工具参数

调用 `financial_query_data` 时：

- `question` 必填。保留用户的证券名称或代码、指标、时间范围、市场、频率和比较口径。
- 用户遗漏的条件仅在上下文足以可靠推断时补齐；关键条件无法判断时先询问用户。
- `lang` 根据用户语言填写：中文为 `CNS`，英文为 `ENS`；默认 `CNS`。

示例参数：

```json
{
  "question": "查询贵州茅台600519.SH在2025年1月1日至2025年12月31日的日收盘价和成交量",
  "lang": "CNS"
}
```

调用 `fin_doc_searchV3` 时：

- `query` 必填，使用简洁、可检索的自然语言问题。
- `topK` 未指定时使用 `15`。
- `queryMode` 必须传代码：`1` 表示文件、`2` 表示 Chunk、`3` 表示文件与 Chunk；默认传 `3`，不得传“文件+Chunk”。
- `docType` 可用值：新闻 `1`、研报 `2`、公告 `3`、3C `4`、法律法规 `5`、金融知识 `6`、终端命令 `7`、万得大学 `8`、舆情 `12`、帮助中心 `17`。多种类型使用英文逗号分隔；未指定时省略，服务默认搜索新闻。
- `startDate`、`endDate` 仅在需要限制时间时传入，格式必须为 `yyyy-MM-dd HH:mm:ss`。

示例参数：

```json
{
  "query": "贵州茅台2025年年度业绩相关公告和研报",
  "topK": 15,
  "queryMode": "3",
  "docType": "2,3",
  "startDate": "2025-01-01 00:00:00",
  "endDate": "2025-12-31 23:59:59"
}
```

### 4. 调用所选工具

继续向同一 MCP 入口发送 `POST`，使用新的唯一 `id`：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "financial_query_data",
    "arguments": {
      "question": "查询中国A股市场过去一年的平均成交量",
      "lang": "CNS"
    }
  }
}
```

调用文档搜索时，将 `name` 改为 `fin_doc_searchV3`，并将 `arguments` 替换为对应参数。

### 5. 解析 MCP 响应

- 若响应为 `application/json`，直接按 JSON-RPC 2.0 响应解析。
- 若响应为 `text/event-stream`，逐个读取 SSE 事件，只解析 `event: message` 对应的 `data:` 内容，并将其作为 JSON-RPC 2.0 响应处理。
- 解析工具调用结果时，同时检查顶层 `error` 和 `result.isError`。存在顶层 `error`，或 `result.isError` 为 `true` 时，将 `result.content` 作为错误信息处理，不得作为正常金融数据回答用户；仅当 `result.isError` 不为 `true` 时，才将 `result.content` 作为正常工具结果使用。
- 工具结果为空时，提示用户补充证券代码、指标、文档类型或时间范围，不得编造结果。

## 失败处理

- HTTP `401`、`403`，或响应明确表示登录状态异常、token 无效或 token 过期时，按“凭据规则”调用一次 `huawei_id_tool`，重新读取 token 后仅重试原请求一次。
- 若本次任务在调用业务接口前已刷新过 token，不得因鉴权失败再次刷新。
- 收到“工具不存在”或 schema 不匹配错误时，重新调用一次 `tools/list`，按最新 schema 修正调用；仍失败则向用户说明工具暂不可用。
- 网络超时或服务端错误可重试一次；连续失败后停止，简要说明失败阶段，不泄露请求头和凭据。
- 不得将金融数据工具或金融文档的返回值转化为证券推荐或投资建议。

## 输出要求

- 先直接回答用户问题，再列出关键数据、时间区间或匹配文档。
- 明确区分工具返回事实与基于事实做出的推断。
- 多证券比较时统一指标、币种、频率和日期口径；口径不同则显式说明。
- 文档搜索结果应尽量保留标题、文档类型、发布日期和来源标识；仅依据返回内容总结。
- 使用客观、中性措辞，不得使用“建议买入”“推荐持有”“可以加仓”等引导交易的表达。
- 涉及证券比较、估值或行情解读时，注明“以上内容仅为客观数据或文档信息，不构成投资建议”。
