# 企业团餐（公司订餐/会议餐/团队餐）

本指南介绍企业团餐相关工具的使用方式与推荐流程。

> 业务流程以「企业团餐」口径编排；错误与重试参见 `references/infra/error-handling.md`；认证与调用方式参见 `references/infra/tool-calling-strategy.md`。

## 企业团餐工具概览

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| delivery-query-addresses | 获取用户可配送地址列表 | 查询已保存的配送地址，取得 `addressId`、`storeCode`、`beCode`（须同一条记录） |
| delivery-create-address | 新增配送地址 | 无地址或需新增收货地址时创建；创建后保存返回的地址与门店关联字段 |
| delivery-query-stores | 查询地址可配送门店 | 根据 addressId 查询可配送门店列表，获取 `beCode`、营业状态等 |
| query-store-coupons | 查询用户在当前门店可用券 | 在已确定门店后，查询当前门店下可用优惠券，用于算价前选券 |
| query-meals | 查询当前门店可售卖的餐品列表 | 查询菜单（分类、餐品编码等），用于团餐选品与数量汇总 |
| query-meal-detail | 查询餐品详情 | 查看配料、规格、套餐组成等 |
| query-meal-assistance | 查询助餐服务 | 获取团餐配送服务选项（`gmServiceCode`），calculate-price 必传 |
| calculate-price | 商品价格计算 | 按选购列表（可含券，以接口为准）计算应付金额 |
| create-order | 创建订单 | 创建团餐订单并返回支付相关信息（以接口返回为准） |
| query-order | 查询订单详情 | 用户追问进度或核对订单时查询 |

## 适用场景

- 用户明确提出公司订餐、会议餐、团队餐
- 需要批量下单、统一送达或集中取餐

## 自动推进原则

团餐场景需要收集人数和预算（这是业务必需信息），但**只在算完价后确认一次下单**。

必须从用户获取的信息：
- 用餐人数（必须）
- 预算（必须，最低起送 300 元）
- 配送地址（无地址时必须创建）

自动推进的步骤：
- 单地址 → 自动选择
- 多地址 → 按画像 lastUsed 自动选择
- 可用券 → 自动查询并应用
- 餐品推荐 → 根据人数+预算+画像自动生成方案

## 标准流程（严格按顺序执行）

```
收集人数与预算 → 自动选择配送地址 → 自动查询可用券 → 查询餐品 → 智能推荐方案 → 计算价格 → 【用户确认】 → 创建订单 →（按需）查询订单进度
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
- 多个地址 → 优先选择画像中 `addresses.lastUsed` 对应的地址；若需用户选择且 `isShowCard=true` 则端侧地址列表卡，**禁止** Markdown 列表复述地址

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

**参数**：`{"addressId": "地址ID", "beType": 6}`

**前置条件**：必须已调用 `delivery-query-addresses` 获取到 `addressId`

**返回字段**：

| 字段 | 说明 |
|------|------|
| `storeCode` | 门店编码 |
| `beCode` | BE 编码（团餐场景必需） |
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

### query-meal-assistance — 查询助餐服务

**参数**：

```json
{
  "storeCode": "门店编码",
  "beCode": "BE编码",
  "orderType": 2,
  "beType": 6,
  "items": [
    { "productCode": "9900005466", "quantity": 5 }
  ]
}
```

**前置条件**：必须已调用 `query-meals` 获取到餐品编码，并确定商品列表

**返回字段**：`mealAssistanceItems[]`，每项含：

| 字段 | 说明 |
|------|------|
| `gmServiceCode` | 服务编码（传入 calculate-price 的必填字段） |
| `gmServiceName` | 服务名称（如"企业团餐配送"） |
| `enable` | 是否可用 |
| `selected` | 是否默认选中 |
| `serviceItems[]` | 子服务项列表 |
| `unusableReason` | 不可用原因（enable=false 时） |
| `promotions[]` | 关联优惠信息 |

**自动处理**：

- 选择 `enable=true && selected=true` 的服务，取其 `gmServiceCode`
- 若无可用服务（全部 `enable=false`）→ 展示 `unusableReason`，提示用户调整商品或更换门店
- 获取到的 `gmServiceCode` 必须传入后续 `calculate-price` 调用

---

### calculate-price — 计算价格

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**团餐场景调用示例**：

```json
{
  "storeCode": "1990165",
  "beCode": "199016502",
  "orderType": 2,
  "beType": 6,
  "gmServiceCode": "来自query-meal-assistance",
  "items": [
    { "productCode": "9900005466", "quantity": 5 },
    { "productCode": "9900004835", "quantity": 5 }
  ]
}
```

**易错点（必读）**：

| 易错项 | 正确做法 | 错误做法 |
|--------|----------|----------|
| 商品编码字段名 | `productCode` | ~~code~~ |
| 商品列表字段名 | `items` | ~~products~~ |
| 团餐(beType=6)是否传 beCode | **必传** | ~~不传~~ |
| 团餐是否传 gmServiceCode | **必传** | ~~不传~~ |

> `query-meals` 返回的餐品编码字段名是 `code`，但传入 `calculate-price` 时必须改为 `productCode`。

**前置条件**：
- 必须已调用 `delivery-query-addresses` 获取门店信息
- 添加任何商品时都需要重新计算价格
- 商品 `productCode` 必须来自 `query-meals` 返回的餐品 `code` 字段

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract calculate-price '<json>'`（模板 `assets/genui/calculate-price.ndjson`）。`isShowCard=true` 时团餐人均等仅写在导语（1 句），**禁止**表格；`false` 时用下方 Markdown 回退。

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
人均费用：¥[price/100/人数]
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
1. 展示订单号、应付金额、人均费用（通过 GenUI 订单卡；卡片内「立即支付」按钮已绑定 `payH5Url`）
2. **H5 支付**：直接使用 create-order 返回的 `payH5Url`；若需文字补充，展示 markdown 超链接：`[点击前往支付](payH5Url)`
3. **移动端**：优先 scheme 链接唤起 App 付款：
   `mcdapp://page?iosPageName=MCDOrderDetailViewController&androidPageName=ComponentOrder&androidPageAction=order_detail&harmonyPageName=OrderDetailPage&parameters=%7B%22orderId%22%3A%22{orderId}%22%2C%22openCashierDesk%22%3A%221%22%7D`
   若 scheme 无法跳转，兜底使用 `payH5Url`（同步骤 2）

---

### query-order — 查询订单详情

**参数**：需要参数 schema 时使用 `bash scripts/discover_tools.sh --json` 实时查询（inputSchema）

**前置条件**：必须已知完整的订单号

**向用户展示**：`bash scripts/call_tool_for_genui.sh --extract query-order '<json>'`（模板 `assets/genui/query-order.ndjson`）。

## 团餐智能推荐

根据人均预算（总预算÷人数）推荐：

| 人均预算 | 推荐搭配 |
|---------|---------|
| 20元以下 | 小食 |
| 20-30元 | 汉堡+小食 或 汉堡+饮料 |
| 30-40元 | 汉堡+薯条/小食+饮料 |
| 40-50元 | 汉堡+薯条+小食+饮料 |
| 50元以上 | 丰富组合，优先不重复小食 |

**特殊偏好优先**：如果用户要求全主食/全小食/全饮料，先满足特殊需求，再补充其他品类。

提供 2-3 个方案供选择。各方案算价若 `isShowCard=true`，每张卡片 + 短总结，**禁止**表格；仅 `isShowCard=false` 时可用独立表格与对比总览表。

## 关键规则

### 固定参数（企业团餐）

- `beType`：**6**（企业团餐场景；若与现网/环境不一致，以实际接口文档为准）
- `orderType`：**2**（外送）

### 调用顺序（不可跳步）

0. 检查 `117797261_login_token` 是否有效；过期则调用 `HuaweiIDTool("mcd-skills", "117797261")` 刷新
1. 收集需求（人数、预算）→ 预算检查（最低起送 300 元）
2. `delivery-query-addresses` → 自动选择地址 → 保存 `addressId`、`storeCode`、`beCode`
3. `delivery-query-stores`（addressId + beType=6）→ 确认门店可配送、获取 `beCode`
4. `query-store-coupons`（自动查询，不问用户）
5. `query-meals` → 根据人数+预算+画像自动生成推荐方案
6. `query-meal-assistance` → 获取 `gmServiceCode`
7. `calculate-price`（自动应用最优券 + gmServiceCode）→ **展示方案，等待用户确认**
8. `create-order`
9. （按需）`query-order`
10. 下单成功后更新用户画像（`memory/mcd-user-profile.json`）

面向用户说明时使用自然中文，不暴露工具名称。

## 备注

- 团餐直接给出 2-3 个推荐方案，用户选择后直接算价确认，减少来回追问。
- 餐品列表若暂无图片，不要强制渲染；有图时可使用 Markdown `![描述](完整URL)` 或 HTML `<img>` 渲染；使用 `<img>` 时须限制 `height="300"`
