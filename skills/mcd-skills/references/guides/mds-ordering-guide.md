# 麦乐送（外卖/配送到家）

本指南介绍麦乐送（个人外送）相关工具的使用方式与推荐流程。

> 业务流程以「麦乐送」口径编排；错误与重试参见 `references/infra/error-handling.md`；认证与调用方式参见 `references/infra/tool-calling-strategy.md`。

## 麦乐送工具概览

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| delivery-query-addresses | 获取用户可配送地址列表 | 查询用户已创建的配送地址列表，用于外送点餐时选择配并获取对应门店信息（storeCode、beCode） |
| delivery-create-address | 新增配送地址 | 当用户无可配送地址或需新增收货地址时使用，用于创建新的可配送地址 |
| delivery-query-stores | 查询地址可配送门店 | 根据 addressId 查询可配送门店列表，获取 `beCode`、营业状态等 |
| query-store-coupons | 查询用户在当前门店可用券 | 查询用户在当前门店下可使用的优惠券列表，用于点餐时选择可用优惠 |
| query-meals | 查询当前门店可售卖的餐品列表 | 查询当前门店可售卖的餐品菜单（分类、餐品编码、标签等），用于点餐选品 |
| query-meal-detail | 查询餐品详情 | 根据餐品编码查询餐品详情（套餐组成、默认选择等），用于查看套餐包含内容 |
| calculate-price | 商品价格计算 | 根据用户选购商品列表（可含优惠券）计算商品金额、配送费、优惠金额及应付总价 |
| create-order | 创建订单 | 根据门店信息、就餐方式、商品列表等信息创建订单，返回订单详情与支付链接 |
| query-order | 查询订单详情 | 查询订单状态、订单内容、配送信息等，用于用户查看订单进度或确认订单信息 |

## 适用场景

- 用户明确要外卖/送到家/麦乐送/配送

## 自动推进原则

本流程中**唯一需要用户确认的节点是：算完价后、下单前**。其余步骤自动推进：
- 单地址 → 自动选择
- 多地址 → 优先选画像中 `lastUsed` 的地址
- 可用券 → 自动查询，自动应用最优券
- 餐品推荐 → 根据画像偏好 + 当前时段自动推荐

## 标准流程（严格按顺序执行）

```
自动选择配送地址 → 自动查询可用券 → 查询餐品并推荐 → 计算价格 → 【用户确认】 → 创建订单 →（按需）查询订单进度
```

## 展示规则

> **输出前必读**：向用户展示任何业务数据前，必须先读取 [output.md](../../output.md)。

向用户展示**本次**工具返回的业务数据时：

1. 若存在 `assets/genui/<tool-name>.ndjson`，在 skill 根目录执行：
   `bash scripts/call_tool_for_genui.sh --extract <tool-name> '<json>'`
2. stdout 为单行 JSON：看 **`isShowCard`** 决定展示（`true` 时 `query-meals` 另有 `simplify`；其余模板工具 stdout 仍含业务 JSON）；详见 [output.md](../../output.md)）
   - **`isShowCard: true`** → `displayA2UICardByPath` + 总结≤20 字；**禁止** Markdown 表格与复述卡片数据
   - **`isShowCard: false`** → 才使用本 guide「Markdown 回退」或「输出示例」
3. **禁止**对同一 tool+参数再调原生 MCP 或脚本；**禁止**二次装填；`isShowCard=true` 时只调 `displayA2UICardByPath`，勿读 DSL 文件
4. 大菜单若需极简字段，可对本次 JSON 的 `result.structuredContent.data` 在内存中过滤，勿重复 MCP

本 guide 已配置模板：
- `delivery-query-addresses`
- `query-meals`
- `calculate-price`
- `create-order`
- `query-order`

## 工具详情

### delivery-query-addresses — 查询配送地址

**参数**：无需传参

**前置条件**：无

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract delivery-query-addresses '{}'`（模板 `assets/genui/delivery-query-addresses.ndjson`）。

**处理结果**：

- 无地址 → 引导创建（询问城市、姓名、性别、手机、地址、门牌号）
- 单个地址 → **自动选择**；`isShowCard=true` 时调 `displayA2UICardByPath`，不在 Markdown 复述地址；`false` 时用 Markdown 回退
- 多个地址 → 优先选择用户画像中 `addresses.lastUsed` 对应的地址；若需用户选择且 `isShowCard=true` 则端侧地址列表卡，**禁止** Markdown 列表复述地址

**保存关键信息**：`addressId`、`storeCode`、`beCode`（须来自同一条地址记录，后续步骤必需）

---

### delivery-create-address — 新增配送地址

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：所有必填参数必须从用户输入中获取，不得使用示例值或凭空生成

**错误处理**：

- 参数校验失败 → 返回具体错误提示（如手机号格式错误、必填项为空）
- 地址创建失败 → 提示稍后重试
- 该地址没有可配送门店 → 提示该地址暂不支持配送

---

### delivery-query-stores — 查询可配送门店

**参数**：`{"addressId": "地址ID", "beType": 2}`

**前置条件**：必须已调用 `delivery-query-addresses` 获取到 `addressId`

**返回字段**：

| 字段 | 说明 |
|------|------|
| `storeCode` | 门店编码 |
| `beCode` | BE 编码（外送场景必需） |
| `businessStatus` | 营业状态 |
| `businessStartTime` | 营业开始时间 |
| `businessEndTime` | 营业结束时间 |

**处理结果**：
- 单门店 → 自动选择
- 多门店 → 选择营业中的门店
- 无可配送门店 → 提示用户更换地址

---

### query-store-coupons — 查询门店可用券

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：
- 必须已调用 `delivery-query-addresses` 并获得返回结果
- storeCode 和 beCode 必须来自同一条地址记录，禁止拆分或自行生成

**自动处理**：

- 当前无可用优惠券 → 跳过，继续下一步
- 有券时 → 自动展示可用券列表，算价时自动应用最优券

---

### query-meals — 查询餐品列表

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：必须已确定门店（storeCode + beCode）

**注意**：
- code 来自 `categories[].meals[].code`（或 meals 字典的 key），不是 meals 的 value
- 必须将 code 与 `meals[code].name` / `currentPrice` 关联后再输出，不得省略 code
- 不允许模型自己生成任何餐品，必须使用接口返回数据
- 将餐品按类别分组展示：套餐、主食、小食、饮料
- 餐品图片字段：`data.meals[code].image`；**`isShowCard=true` 时由端侧卡片展示，禁止 Markdown 图片**；`false` 时有值用 `<img src="URL" height="300">`，无值不渲染

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract query-meals '<json>'`（模板 `assets/genui/query-meals.ndjson`）。

---

### query-meal-detail — 查询餐品详情

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：必须已调用 `query-meals` 获取到餐品编码

---

### calculate-price — 计算价格

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**麦乐送场景调用示例**：

```json
{
  "storeCode": "1990165",
  "beCode": "199016502",
  "orderType": 2,
  "beType": 2,
  "items": [
    { "productCode": "9900005466", "quantity": 1 },
    { "productCode": "4820", "quantity": 1, "couponCode": "MCD68803UTR201108T000", "couponId": "F092E580A7A869868EE5EA37ECCF1458" }
  ]
}
```

**易错点（必读）**：

| 易错项 | 正确做法 | 错误做法 |
|--------|----------|----------|
| 商品编码字段名 | `productCode` | ~~code~~ |
| 商品列表字段名 | `items` | ~~products~~ |
| 外送(beType=2)是否传 beCode | **必传** | ~~不传~~ |

> `query-meals` 返回的餐品编码字段名是 `code`，但传入 `calculate-price` 时必须改为 `productCode`。

**前置条件**：
- 必须已调用 `delivery-query-addresses` 获取门店信息
- 添加任何商品时都需要重新计算价格
- 商品 `productCode` 必须来自 `query-meals` 返回的餐品 `code` 字段

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract calculate-price '<json>'`（模板 `assets/genui/calculate-price.ndjson`）。

**Markdown 回退（calculate-price，仅 `isShowCard: false` 时使用；为 true 时禁止引用本节表格）**：

```
商品明细：

| 餐品 | 单价 | 数量 | 小计 |
|------|------|------|------|
| [productName] | ¥[originalSubtotal/100] | [quantity]份 | ¥[subtotal/100] |

价格明细：

|  | 原价(元) | 优惠金额(元) | 小计(元) |
|:---:|:---:|:---:|:---:|
| 商品价格 | ¥[productOriginalPrice/100] | -¥[差额/100] | ¥[productPrice/100] |
| 外送费 | ¥[deliveryOriginalPrice/100] | -¥[差额/100] | ¥[deliveryPrice/100] |
| 打包费 | ¥[packingOriginalPrice/100] | -¥[差额/100] | ¥[packingPrice/100] |

优惠总计：-¥[discount/100]
应付总额：¥[price/100]
```

询问用户确认后再下单。

**这是唯一的用户确认点**：展示价格明细后，等用户确认再下单。

---

### create-order — 创建订单

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：
- 必须已调用 `calculate-price` 并等待用户确认价格
- 必须已调用 `delivery-query-addresses` 获取 addressId、storeCode、beCode

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract create-order '<json>'`（模板 `assets/genui/create-order.ndjson`）。

**下单后引导**：
1. 展示订单号、应付金额、配送地址（通过 GenUI 订单卡；卡片内「立即支付」按钮已绑定 `payH5Url`）
2. **H5 支付**：直接使用 create-order 返回的 `payH5Url`；若需文字补充，展示 markdown 超链接：`[点击前往支付](payH5Url)`
3. **移动端**：优先 scheme 链接唤起 App 付款：
   `mcdapp://page?iosPageName=MCDOrderDetailViewController&androidPageName=ComponentOrder&androidPageAction=order_detail&harmonyPageName=OrderDetailPage&parameters=%7B%22orderId%22%3A%22{orderId}%22%2C%22openCashierDesk%22%3A%221%22%7D`
   若 scheme 无法跳转，兜底使用 `payH5Url`（同步骤 2）

**支付后订单追踪**：

用户确认已支付后，主动轮询订单状态，直到状态变为「配送中」或「已完成」为止：

1. 用户说「已支付」后，立即调用 `query-order` 查询一次
2. 若状态仍为「待支付」，等待 10 秒后再查，最多重试 3 次（共约 30 秒）
3. 一旦 `orderStatus` 不再是「待支付」，立即推送给用户：
   - 订单状态描述
   - 骑手信息（若有）
   - 预计送达时间（`estimatedTime`，若有）
4. 若 3 次重试后仍为「待支付」，提示用户确认支付是否成功，并告知可随时说「查一下订单」手动触发查询

**订单状态说明**：

| orderStatus | 含义 | 处理方式 |
|-------------|------|----------|
| 待支付 | 用户尚未完成支付 | 提示用户支付，或确认支付是否成功 |
| 制作中 | 支付成功，厨房正在制作 | 告知预计送达时间 |
| 配送中 | 骑手已取餐，正在配送 | 展示骑手信息和预计送达时间 |
| 已完成 | 订单已送达 | 告知订单完成 |
| 已取消 | 订单已取消 | 告知用户，询问是否重新下单 |

---

### query-order — 查询订单详情

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：必须已知完整的订单号

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract query-order '<json>'`（模板 `assets/genui/query-order.ndjson`）。

**订单状态说明**：见上方「支付后订单追踪」章节

## 关键规则

### 固定参数（个人麦乐送）

- `beType`：**2**（个人外送场景；若与现网/环境不一致，以实际接口文档为准）
- `orderType`：**2**（外送）

### 调用顺序（不可跳步）

0. 检查 `117797261_login_token` 是否有效；过期则调用 `HuaweiIDTool("mcd-skills", "117797261")` 刷新
1. `delivery-query-addresses` → 自动选择地址 → 保存 `addressId`、`storeCode`、`beCode`
2. `delivery-query-stores`（addressId + beType=2）→ 确认门店可配送、获取 `beCode`
3. `query-store-coupons`（自动查询，不问用户）
4. `query-meals` → 根据画像偏好 + 当前时段自动推荐餐品组合
5. `calculate-price`（自动应用最优券）→ **展示方案，等待用户确认**
6. `create-order`
7. 用户确认支付后 → **主动轮询** `query-order`，直到状态变化或最多重试 3 次（每次间隔 10 秒）
8. 下单成功后更新用户画像（`memory/mcd-user-profile.json`）

面向用户说明时使用自然中文，不暴露工具名称。

## 备注

- 用户如果同时提到「有券/领券」，直接查券并自动应用，不额外确认。
- 餐品列表若暂无图片，不要强制渲染；有图时可使用 Markdown `![描述](完整URL)` 或 HTML `<img>` 渲染；使用 `<img>` 时须限制 `height="300"`。
