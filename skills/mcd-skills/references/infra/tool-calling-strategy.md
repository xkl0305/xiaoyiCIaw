# 工具调用策略

本文件定义麦当劳后端工具的认证、标准工作流程与脚本调用方式，是所有业务域的前置依赖。

> **严禁 MCP 直连**
>
> - **禁止**调用 `mcd-mcp` MCP 服务器。
> - **禁止**使用 `command_call_tool` 或等价原生 MCP 接口调用 `query-meals`、`calculate-price` 等。
> - **唯一合法入口**：`bash scripts/call_tool_for_genui.sh --extract <tool-name> '<json>'`。
> - **向用户展示**：看 stdout 的 `isShowCard`：`true` 时调 `displayA2UICardByPath` + 总结≤20 字；`false` 时按 guide 纯 Markdown。

**唯一允许的调用方式**（skill 根目录）：

| 用途 | 命令 |
|------|------|
| 业务 API | `bash scripts/call_tool_for_genui.sh --extract <tool-name> '<json>'` |
| 工具列表 / 参数 schema | `bash scripts/discover_tools.sh --json`（实时查询完整 schema） |

**禁止**使用 `mcd-mcp` MCP 服务器、IDE 原生 MCP 客户端、`mcpServers` 配置、或任何绕过 `call_tool_for_genui.sh` 的 HTTP/MCP 直调。

### Token 优先（默认调用约定）

- **强烈推荐**：所有业务 API 均加 `--extract`；`isShowCard=true` 时 stdout 含 `a2uiCard` + `isShowCard`（`query-meals` 另有 `simplify`）；`false` 时为完整业务 JSON + `isShowCard`。
- **需要工具名、描述、`inputSchema`、输出结构**：用 `discover_tools.sh --json` 实时查询 `tools/list`，**勿**从完整 API 响应或默认模式 JSON-RPC 自学 schema。
- **默认模式**（无 `--extract`）：仅调试/排障，不作为 Agent 常规路径。

## 标准工作流程

每次业务调用按以下步骤执行（skill 根目录下操作）。

### Step 0：凭据

- 使用环境变量 `117797261_login_token`、`117797261_login_token_expire_time`（详见下文「Token 认证」）。
- 禁止调用前主动刷新；凭据由脚本从 `.xiaoyienv` 读取。

### Step 1：调用脚本

```bash
bash scripts/call_tool_for_genui.sh --extract <tool-name> '<json>'
```

| 工具类型 | 命令模式 | 说明 |
|----------|----------|------|
| **所有业务 API（含已配置 ndjson 模板的工具）** | `--extract` | 同参数 **仅 1 次**；stdout 含 `isShowCard` + 可选 `a2uiCard` |
| 已配置 ndjson 模板的工具向用户展示 | `--extract` | `isShowCard=true` → `displayA2UICardByPath`；总结≤20 字 |
| 菜单/算价等推理需子集 | `--extract` + 内存裁剪或 `call_tool_for_genui.sh --filter_mode meals` | `a2uiCard` 随装填一并更新 |
| 无模板、大数据 | `--extract`（已自动截断，见「响应过滤」） | 大 JSON 不得整包进上下文 |
| 无模板、小数据 | `--extract` 即可 | 见「响应过滤」不需过滤场景 |
| 默认模式 | 非推荐 | 完整 JSON-RPC，仅调试 |

### Step 2：解析 stdout（关键心智模型）

`--extract` 的 stdout 形态由 **`isShowCard`** 决定：

**DSL 装填成功（`isShowCard=true`）** — stdout 形态因工具而异：

`query-meals`（菜单压平）：

```json
{
  "simplify": ["板烧 ¥35.00 code:M001"],
  "isShowCard": true,
  "a2uiCard": {
    "cardDSLPath": "<a2uiCard.cardDSLPath>",
    "displayTool": "displayA2UICardByPath",
    "toolName": "query-meals",
    "displayRequirement": "…"
  }
}
```

`calculate-price` / `create-order` / `query-order` / `delivery-query-addresses`：stdout 含**完整业务 JSON** + `isShowCard` + `a2uiCard`（无 `simplify` 字段）。

**无 DSL / 装填失败（`isShowCard=false`）** — stdout 为完整业务 JSON + `isShowCard: false`。

- `isShowCard=true` **且 Phase 3 系统提示词版本达标** → 调 `displayA2UICardByPath`；**禁止** read 打开 DSL 落盘文件
- `isShowCard=false`，或 `isShowCard=true` 但版本不达标 → 按 guide 纯 Markdown 展示

**展示铁律**：`isShowCard=true` **且版本达标**时，导语 1 句 → `displayA2UICardByPath` → 总结 **不超过 20 字**。

| stdout + 版本 | 回复里放什么 |
|----------------|-------------|
| `isShowCard=true` 且版本达标 | 导语 + `displayA2UICardByPath` + 总结≤20 字 |
| `isShowCard=false` | guide Markdown |
| `isShowCard=true` 但版本不达标 | guide Markdown |

**展示回退**（Phase 3 出卡时判定，详见 [client-version.md](client-version.md)）：

| 层级 | 条件 | 做法 |
|------|------|------|
| 1（优先） | `isShowCard=true` 且系统提示词版本满足门槛 | `displayA2UICardByPath` |
| 2（回退） | `isShowCard=false`，或版本不达标 | guide Markdown |

### Step 3：脚本失败处理

脚本 exit 非 0 时：

1. 仅当 token 为空或已过期时调用 `HuaweiIDTool("mcd-skills", "117797261")` 后**用同一脚本重试一次**；token 仍有效则禁止刷新
2. 仍失败 → 按 [error-handling.md](error-handling.md) 给用户友好提示，不暴露 stderr / JSON-RPC 细节
3. **禁止**改走 `mcd-mcp`、原生 MCP 或其它非脚本路径

### 不变约束（全程适用）

- 同一 `tool-name` + 相同 JSON 参数：全程最多 **1 次** `call_tool_for_genui.sh`
- **禁止**：同参数重复调用脚本；禁止二次装填
- 有 ndjson 时**不得**手拼 DSL 或绕过 `a2uiCard.cardDSLPath`
- guide「输出示例」为 Markdown 展示参考；**版本达标且** `isShowCard=true` 时**禁止**用 Markdown 复述同批业务数据
- 即使环境存在 `mcd-mcp` 工具，**不得**改走 MCP；失败时仅允许 Token 刷新后**重试同一脚本**
- `isShowCard=false` 或版本不达标 → guide Markdown；`isShowCard=true` 且版本达标 → `displayA2UICardByPath`，总结≤20 字

---

## Token 认证（华为小艺）

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `117797261_login_token` | MCP 认证 Token（由华为小艺平台注入；写入 HTTP 头 `Authorization: Bearer <token>`） |
| `117797261_login_token_expire_time` | Token 过期时间戳（Unix ms） |
| `MCD_MCP_URL` | MCP 服务地址（默认 `https://mcp.mcd.cn`；由脚本读取，Agent 勿直连） |

### HTTP 请求头（与现网一致）

脚本向 `MCD_MCP_URL` 发送 JSON-RPC 时使用：

| Header | 值 |
|--------|-----|
| `Authorization` | `Bearer ${117797261_login_token}` |
| `Content-Type` | `application/json` |

实现位置：`scripts/call_tool.sh`、`scripts/call_tool.py`、`scripts/discover_tools.sh`、`scripts/discover_tools.py`（`call_tool_for_genui` 经 `call_tool.py` 复用同一套头）。

### Token 刷新

惰态刷新：仅脚本报错后，且 token 为空或当前时间 > `117797261_login_token_expire_time` 时，调用一次：

```
HuaweiIDTool("mcd-skills", "117797261")
```

刷新后环境变量自动更新，无需手动处理；token 仍有效时严格禁止刷新。

### Token 缺失时的错误提示

脚本检测到 `117797261_login_token` 为空时，输出：
```
错误: 117797261_login_token 为空或未设置，请刷新 Token
调用 HuaweiIDTool("mcd-skills", "117797261") 刷新
```

---

## 单一入口：call_tool_for_genui.sh

**无论是否配置了 `mcd-mcp`，所有业务工具调用均只能通过此脚本**（skill 根目录，Token 见「Token 认证」）。

```bash
bash scripts/call_tool_for_genui.sh [--extract] <tool-name> '<json>'
```

**出参形态**：

| 模式 | stdout |
|------|--------|
| **`--extract`（推荐）** | `true` → `a2uiCard` + `isShowCard`（`query-meals` 另有 `simplify`）；`false` → 业务 JSON + `isShowCard` |
| 默认（不推荐） | 单行 JSON-RPC + 可选 `a2uiCard`；仅调试 |

**已配置 GenUI 模板的工具**（模板路径均在 skill 根目录 `assets/genui/`）：

| 工具名 | 模板文件 |
|--------|----------|
| `query-meals` | `query-meals.ndjson` |
| `calculate-price` | `calculate-price.ndjson` |
| `create-order` | `create-order.ndjson` |
| `query-order` | `query-order.ndjson` |
| `delivery-query-addresses` | `delivery-query-addresses.ndjson` |

**有 ndjson 模板的工具**：**一律 `--extract`**；stdout 含 `isShowCard` 与可选 `a2uiCard`。`isShowCard=true` 时调 `displayA2UICardByPath`；**禁止** Agent 用 read 打开 `a2uiCard.cardDSLPath`。

**大 JSON 菜单**（有 ndjson 时）：在**内存**中按画像裁剪选品（勿依赖已 strip 的 stdout）；或向 `--filter_mode meals` 传入**未 strip** 的业务 JSON；脚本内截断后装填，`a2uiCard` 随装填更新。

**GenUI 版本门槛**：系统 API ≥ 20 且小艺 App ≥ 11.7.6.200；**Phase 3 出卡前**从系统提示词读取并判定，不满足则走 Markdown（脚本不判版本）。详见 [client-version.md](client-version.md)。

**本地调试**（不向用户展示）：`python scripts/run_genui_local.py <tool> scripts/mock/<tool>.json`

---

## 工具发现：discover_tools.sh

查询工具名、描述、`inputSchema` 时**只使用**：

```bash
bash scripts/discover_tools.sh          # 实时查询并输出工具摘要
bash scripts/discover_tools.sh --json   # 实时输出完整工具定义（含 inputSchema）
```

**与 `--extract` 的分工**：业务数据 → `call_tool_for_genui.sh --extract`；参数/schema/工具列表 → `discover_tools.sh`。避免为弄清字段而反复调用大 API 或读完整 JSON-RPC 响应。

---

## 响应过滤（Token 节省策略）

### 问题背景

麦当劳 API（尤其是 `query-meals`）返回的 JSON 通常非常大（几百个餐品，几十 KB），如果原样读入对话上下文会迅速耗尽 token 窗口。

### 核心原则

**API 大 JSON 不得整包进对话上下文。** 有 DSL 且装填成功时，仅 `query-meals` 的 stdout 会 strip 为 `simplify`；其余模板工具 stdout 仍含业务 JSON。`isShowCard=false` 时 stdout 为业务 JSON（大菜单类 API 脚本内仍截断后再输出）。向用户展示见 Step 2。

### 推荐方式：`--extract`（已内置截断 + a2uiCard）

`call_tool_for_genui.sh --extract` 已内置截断（默认 10 分类 × 20 餐品），无需额外管道过滤。向用户展示调 `displayA2UICardByPath(a2uiCard.cardDSLPath)`。

```bash
bash scripts/call_tool_for_genui.sh --extract query-meals '{"storeCode":"1990165","orderType":1}'
```

### 需要搜索时：`--filter_mode meals [--search <term>]`

需要按餐品名搜索时，将 `--extract` 的输出通过管道传给 `--filter_mode meals`：

```bash
# 按关键词搜索（filter 会重新装填并更新 a2uiCard）
bash scripts/call_tool_for_genui.sh --extract query-meals '{"storeCode":"1990165","orderType":1}' \
  | bash scripts/call_tool_for_genui.sh --filter_mode meals --search 奶昔 query-meals
```

**支持的过滤模式**：

| 模式 | 输出格式 | 使用场景 |
|------|---------|---------|
| `--filter_mode meals` | JSON（`query-meals` 含 `simplify` + 可选 `a2uiCard`；stdin 须为未 flatten 的业务 JSON） | 菜单裁剪后重装填 |
| `--filter_mode meals --search 关键词` | 同上 | 按餐品名过滤 |

> **`calculate-price`** 有 ndjson 模板，直接 `--extract` 即可；`isShowCard=true` 时 stdout 含完整业务 JSON + `a2uiCard`。

#### 管道错误处理

`call_tool_for_genui.sh --filter_mode` 对上游异常做了兼容：

| 场景 | 行为 | stderr 输出 |
|------|------|-------------|
| 空输入（上游无 stdout） | exit 1 | `错误: --filter_mode 需要从 stdin 输入 JSON 数据` |
| 非 JSON 文本 | exit 1 | `错误: stdin 不是有效的 JSON 格式` |
| 正常 JSON | exit 0 | 过滤后的 JSON（含 `a2uiCard`）输出到 stdout |

**使用建议**：管道调用时统一用 `2>&1` 合并输出：

```bash
bash scripts/call_tool_for_genui.sh --extract query-meals '...' \
  | bash scripts/call_tool_for_genui.sh --filter_mode meals --search 奶昔 query-meals 2>&1
```

### 不需要过滤的场景

以下工具返回数据量较小，直接使用 `--extract` 输出的 JSON 即可：

- `query-nearby-stores` — 门店列表（通常 1-5 条）
- `delivery-query-addresses` — 地址列表（通常 1-3 条）
- `query-store-coupons` — 可用券列表（通常几条）
- `campaign-calendar` — 活动日历
- `query-order` — 单个订单详情
- `create-order` — 下单结果

### 使用规范

1. **所有工具**常规调用均加 `--extract`；`isShowCard=true` 时展示调 `displayA2UICardByPath` + 总结≤20 字；`false` 时 guide Markdown
2. **菜单类大数据**（`query-meals`）推理需子集时：`--extract` 已自动截断，或 `--filter_mode meals --search <term>`
3. **算价结果**（`calculate-price`）直接 `--extract`（已含 `a2uiCard`），无需额外过滤
4. **其他工具**直接用 `--extract` 获取业务 JSON，无需额外过滤
5. **价格处理**：API 返回的价格单位是分（整数），展示时除以 100 转换为元
6. **字段名映射（易错）**：`query-meals` 返回的餐品编码字段名是 `code`，但传入 `calculate-price` / `create-order` 时参数名为 `productCode`，商品列表字段名为 `items`（不是 `products`）

### 备选方式：自定义 python 内联过滤

当 `call_tool_for_genui.sh --filter_mode` 不满足需求时，可用 python 内联管道。注意 `--extract` 已去掉 JSON-RPC 外壳，stdin 直接就是业务数据：

```bash
bash scripts/call_tool_for_genui.sh --extract query-store-coupons '...' | python3 -c "
import json, sys
data = json.load(sys.stdin)
for c in (data if isinstance(data, list) else []):
    print(f\"{c.get('name','')} | {c.get('couponCode','')}\")
"
```

---

## 工具参数查询（实时查询）

工具的输入参数（inputSchema）和输出结构不在各业务域文档中重复列出，通过 `discover_tools.sh --json` 实时查询。

需要某个工具的参数定义时：

1. 运行 `bash scripts/discover_tools.sh --json`
2. 搜索目标工具名
3. 以实时返回的 `inputSchema` 为准

摘要查看：`bash scripts/discover_tools.sh`
