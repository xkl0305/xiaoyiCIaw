# 工具调用策略

本文件定义了麦当劳 MCP 工具的认证方式和调用模式，是所有业务域的前置依赖。

## Token 认证（华为小艺）

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `117797261_login_token` | MCP 认证 Token（由华为小艺平台注入） |
| `117797261_login_token_expire_time` | Token 过期时间戳（Unix ms） |
| `MCD_MCP_URL` | MCP 服务地址（默认 `https://mcp.mcd.cn`） |

### Token 刷新

当 Token 过期（`117797261_login_token_expire_time` < 当前时间戳）时，调用：

```
huawei_id_tool("117797261","mcd-skills")
```

刷新后环境变量自动更新，无需手动处理。

### 重复调用防护
无论 Token 为空还是过期，huawei_id_tool("117797261","mcd-skills") 在整个 session 中仅能调用一次，不可重复调用。

### Token 缺失时的错误提示

脚本检测到 `117797261_login_token` 为空时，输出：
```
错误: 117797261_login_token 为空或未设置，请刷新 Token
调用 huawei_id_tool("117797261","mcd-skills")  刷新
```

---

## 模式 A（优先）：原生 MCP 连接

如果当前环境已配置 `mcd-mcp` MCP 服务器，直接调用 MCP 工具（如 `campaign-calendar`、`query-meals` 等），无需脚本。

MCP 客户端配置参考：
```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${117797261_login_token}"
      }
    }
  }
}
```

## 模式 B（降级）：脚本调用

未配置原生 MCP 时，使用 `scripts/` 目录下的脚本通过 HTTP 调用。按环境选择：

1. **curl 版**（零依赖，推荐 fallback）：
   ```bash
   bash scripts/call_tool.sh <tool-name> '<json-args>'
   ```

2. **Python 版**（需 `requests`）：
   ```bash
   python scripts/call_tool.py <tool-name> '<json-args>'
   ```

**查看可用工具**：
```bash
bash scripts/discover_tools.sh          # curl 版
python scripts/discover_tools.py        # Python 版（带缓存）
```

## 检测逻辑

Token 来源：环境变量 `117797261_login_token`（华为小艺平台注入）。

Token 过期时调用 huawei_id_tool("117797261","mcd-skills") 刷新。

首次调用时，优先直接使用 MCP 工具（如 `now-time-info`）。若调用成功，后续全程使用模式 A；若明确报错「工具不存在」或当前环境未挂载 MCP，则切换到模式 B（脚本 / curl）。

---

## 响应过滤（Token 节省策略）

### 问题背景

麦当劳 API（尤其是 `query-meals`）返回的 JSON 通常非常大（几百个餐品，几十 KB），如果原样读入对话上下文会迅速耗尽 token 窗口。

### 核心原则

**API 大 JSON 永远不进对话上下文，只让管道过滤后的精简结果进入。**

### 推荐方式：`--extract` + `filter_response.py`

#### Step 1：`--extract` 去掉 JSON-RPC 外壳

`call_tool.sh` 和 `call_tool.py` 支持 `--extract` 参数，直接输出业务数据：

```bash
bash scripts/call_tool.sh --extract <tool-name> '<json-args>'
python scripts/call_tool.py --extract <tool-name> '<json-args>'
```

**行为**：
- 成功时：输出 `.result.structuredContent.data` 的 JSON
- `structuredContent.success == false` 时：直接返回 `result.content[].text`（原始错误文本，非 JSON），exit 1
- 无 `--extract` 时：行为不变（向后兼容）

**注意**：`--extract` 失败时输出的是 markdown 格式文本（非 JSON），管道下游的 `filter_response.py` 已做兼容处理，不会崩溃。

#### Step 2：菜单/算价用 `filter_response.py` 过滤

菜单数据量大（几百个餐品），必须过滤后再读入上下文：

```bash
# 按分类列出全部餐品
bash scripts/call_tool.sh --extract query-meals '{"storeCode":"1990165","orderType":1}' \
  | python3 scripts/filter_response.py meals

# 按关键词搜索
bash scripts/call_tool.sh --extract query-meals '{"storeCode":"1990165","orderType":1}' \
  | python3 scripts/filter_response.py meals --search 奶昔

# 格式化算价结果
bash scripts/call_tool.sh --extract calculate-price '...' \
  | python3 scripts/filter_response.py price
```

**支持的过滤模式**：

| 模式 | 输出格式 | 使用场景 |
|------|---------|---------|
| `meals` | `[分类名]\n  餐品名 ¥价格 code:xxx` | 菜单浏览 |
| `meals --search 关键词` | 只输出名称含关键词的餐品 | 用户指定想吃什么 |
| `price` | 商品明细 + 优惠 + 外送费 + 应付总额 | 算价结果展示 |

#### 管道错误处理

`filter_response.py` 对上游异常做了兼容，不会因非 JSON 输入而崩溃：

| 场景 | 行为 | stderr 输出 |
|------|------|-------------|
| 空输入（上游无 stdout） | exit 1 | `错误: 未收到数据，上游调用可能失败` |
| 非 JSON 文本（如 `--extract` 失败时的 markdown） | exit 1 | `错误: 上游返回非 JSON 数据` + 关键行摘要 |
| JSON 但 `success: false` | exit 1 | `接口错误: {message} (code={code})` |
| 正常 JSON | exit 0 | 过滤后的精简文本输出到 stdout |

**使用建议**：管道调用时统一用 `2>&1` 合并输出，让模型能看到错误信息并据此重试或调整参数：

```bash
bash scripts/call_tool.sh --extract calculate-price '...' \
  | python3 scripts/filter_response.py price 2>&1
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

1. **菜单类大数据**（`query-meals`）必须通过 `filter_response.py` 过滤后再使用
2. **算价结果**（`calculate-price`）推荐用 `filter_response.py price` 格式化展示
3. **其他工具**直接用 `--extract` 获取业务 JSON，无需额外过滤
4. **价格处理**：API 返回的价格单位是分（整数），展示时除以 100 转换为元
5. **字段名映射（易错）**：`query-meals` 返回的餐品编码字段名是 `code`，但传入 `calculate-price` / `create-order` 时参数名为 `productCode`，商品列表字段名为 `items`（不是 `products`）

### 备选方式：自定义 python 内联过滤

当 `filter_response.py` 不满足需求时，可用 python 内联管道。注意 `--extract` 已去掉 JSON-RPC 外壳，stdin 直接就是业务数据：

```bash
bash scripts/call_tool.sh --extract query-store-coupons '...' | python3 -c "
import json, sys
data = json.load(sys.stdin)
for c in (data if isinstance(data, list) else []):
    print(f\"{c.get('name','')} | {c.get('couponCode','')}\")
"
```

---

## 工具参数查询（动态缓存）

工具的输入参数（inputSchema）和输出结构（outputSchema）不在各业务域文档中重复列出，而是通过 MCP `tools/list` 接口动态获取并缓存到本地文件。

### 缓存机制

- 缓存路径：`scripts/cache/tools_YYYY-MM-DD.json`
- 以天为维度，每天首次运行时自动拉取并写入，同时清理前一天的缓存
- 缓存内容为 `tools/list` 返回的完整 JSON（含 name、description、inputSchema 等）

### 使用方式

需要了解某个工具的参数定义时：

1. 先检查 `scripts/cache/` 下是否有当天的缓存文件
2. 若无缓存，运行 discover_tools 生成：
   ```bash
   python scripts/discover_tools.py        # Python 版
   bash scripts/discover_tools.sh          # curl 版
   ```
3. 读取缓存文件，搜索目标工具名即可获取完整参数定义

### 强制刷新

```bash
python scripts/discover_tools.py --refresh
bash scripts/discover_tools.sh --refresh
```
