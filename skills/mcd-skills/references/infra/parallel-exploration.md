# 多方案探索策略

工具调用遵循 [tool-calling-strategy.md](tool-calling-strategy.md) 文首「标准工作流程」。

## 核心思路

当用户意图模糊时，不要串行追问。根据用户画像直接推断最可能的场景，主 session 串行执行查询，一次性展示方案给用户选择。

**不使用 sub agent**，所有查询直接在主 session 中完成，避免调度开销。

## 什么时候需要多方案

| 触发条件 | 处理方式 |
|----------|----------|
| "帮我点麦当劳"（画像偏好 ≥80%） | 直接按偏好推进，不展示多方案 |
| "帮我点麦当劳"（无明确偏好） | 默认到店取餐，直接执行查询 |
| "随便吃点"（不知道吃什么） | 根据时段 + 画像偏好推荐 2-3 个餐品组合，一次性展示 |
| "帮我点个套餐"（不知道哪个） | 查菜单后推荐：历史最爱 + 当前时段热门 + 最优惠组合 |

## 执行方式

所有查询直接在主 session 中串行执行：

```
查门店/地址 → 查券 → query-meals（call_tool_for_genui.sh，内存裁 2～3 项）→ 算价（多个方案）→ 按 `isShowCard` 一次性展示
```

### 多方案算价

每个餐品方案单独算价一次（参数不同，允许多次 MCP）。**向用户展示**看 `isShowCard`：

```bash
# 方案 A（productCode 来自 query-meals 的 code）
bash scripts/call_tool_for_genui.sh --extract calculate-price '{"storeCode":"xxx","orderType":1,"beType":1,"items":[{"productCode":"yyy","quantity":1}]}'

# 方案 B
bash scripts/call_tool_for_genui.sh --extract calculate-price '{"storeCode":"xxx","orderType":1,"beType":1,"items":[{"productCode":"zzz","quantity":1}]}'
```

### 结果展示模板

展示看 **`isShowCard`**；`true` 时调 `displayA2UICardByPath`；禁止把价目表贴给用户。

- **`isShowCard=true`**：导语 + `displayA2UICardByPath` + 总结≤20 字；**禁止** Markdown 表格与复述业务数据
- **`isShowCard=false`**：才使用 guide 内「Markdown 回退」示例

#### 1. 餐品方案（优先 `query-meals`）

**一次**调用菜单（skill 根目录）：

```bash
bash scripts/call_tool_for_genui.sh --extract query-meals '{"storeCode":"xxx","orderType":1,"beCode":"..."}'
```

从**首次 query-meals 调用参数与画像**在内存中**只保留 2～3 个推荐餐品**（偏好 / 时段 / 优惠）；**禁止**同参数再调 MCP 或脚本。若需 filter，stdin 须为未 strip 的业务 JSON（见 strategy「响应过滤」）。

**向用户展示**（模板 `assets/genui/query-meals.ndjson`，勾选组 `meal_pick`）：

| 情况 | 做法 |
|------|------|
| `isShowCard=true`（正常装填） | 导语 1 句 + `displayA2UICardByPath` + 总结≤20 字 |
| `isShowCard=false`（装填失败 / 无模板） | 使用下方 Markdown 回退 |

导语示例（`isShowCard=true` 时，卡片外 1 句）：

```markdown
根据你的口味和当前时段，我挑了这几个组合，勾选后点「选好了」或告诉我要哪一个：
```

**Markdown 回退**（仅 `isShowCard: false` 时使用；为 true 时禁止引用本节）：

```markdown
我帮你挑了几个方案，选一个或说想调整：

- **方案 A**：麦辣鸡腿汉堡三件套（偏好推荐）— ¥25.13
- **方案 B**：「辣」么快乐套餐（轻食）— ¥18.00

选哪个？或告诉我想换什么。
```

#### 2. 已算价时补充价格卡（`calculate-price`）

各方案算价后，对每个 `calculate-price` 响应：若 **`isShowCard=true`**，各调一次 `displayA2UICardByPath`，卡片之间可用一行 Markdown 标注「方案 A / 方案 B」，**禁止**手拼价格表格；若 **`false`**，用 guide「Markdown 回退」。

用户选定方案后，按 `fc-ordering-guide.md` 进入下单前确认（`create-order` 仍须用户确认）。

#### 禁止事项

- 禁止对同一 `query-meals` 参数重复调用 `call_tool_for_genui.sh` 或原生 MCP
- 禁止二次装填或读 DSL 文件进回复
- `isShowCard=true` 时禁止用 Markdown 列表/表格复刻菜单/价目
- `isShowCard=true` 时禁止输出 ` ```genui ` 块

## 不需要多方案的情况

以下场景直接走单一链路：

- 用户明确说了"外卖/麦乐送" → 直接走 mds-ordering-guide
- 用户明确说了"到店/自提/堂食" → 直接走 fc-ordering-guide
- 用户明确说了"团餐/公司订餐" → 直接走 group-meal-ordering-guide
- 用户画像偏好 ≥80% 且无矛盾信号 → 直接按偏好推进
- 非点餐意图（领券、查积分、查活动等） → 直接路由到对应 guide

## Token 节省规则（必须遵守）

- **`query-meals` / `calculate-price`（有 ndjson）**：各工具**至多 1 次** `--extract`；`true` 时 stdout 含 `a2uiCard`（`query-meals` 另有 `simplify`）；展示调 `displayA2UICardByPath`。
- **其他大数据 API**（`query-store-coupons`、`delivery-query-addresses` 等）：用 `--extract` 或内联过滤，**绝不将原始 JSON 读入对话上下文**。
