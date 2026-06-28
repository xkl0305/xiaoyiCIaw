# 到店取餐（堂食/自提/门店用餐）

本指南介绍到店取餐相关工具的使用方式与推荐流程。

> 业务流程以「到店取餐」口径编排；错误与重试参见 `references/infra/error-handling.md`；认证与调用方式参见 `references/infra/tool-calling-strategy.md`。

## 到店取餐工具概览

| 工具名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| query-nearby-stores | 查询附近门店 | 根据用户提供的城市/位置/经纬度查找附近餐厅，确定 `storeCode`、`beCode`（到店主路径） |
| query-store-coupons | 查询用户在当前门店可用券 | 在已确定门店后，查询当前门店下可用优惠券，用于点餐算价前选券 |
| query-meals | 查询当前门店可售卖的餐品列表 | 查询菜单（分类、餐品编码、标签等），用于选品 |
| query-meal-detail | 查询餐品详情 | 查看套餐组成、规格、默认选项等 |
| calculate-price | 商品价格计算 | 根据选购商品（可含优惠券）计算应付金额（到店场景一般无配送费，以接口返回为准） |
| create-order | 创建订单 | 创建到店/自提订单，返回订单详情与支付链接（参数以工具定义为准） |
| query-order | 查询订单详情 | 查询订单状态、取餐信息等 |

## 适用场景

- 用户想吃麦当劳，并且明确是到店取餐/堂食/自提/去门店吃
- 用户只说"帮我点麦当劳"，需要先澄清到店取餐还是外卖或企业团餐（参见 `references/mds-ordering-guide.md`、`references/group-meal-ordering-guide.md`）

## 自动推进原则

本流程中**需要用户确认的节点**：
1. **新用户选门店**：无画像、无历史门店时，必须先询问用户所在城市或想去哪家门店
2. **下单前确认**：算完价展示方案后、创建订单前

老用户（有画像/历史门店）的门店选择自动推进：
- 画像有 `addresses.lastUsed` → 自动使用上次门店，告知用户
- 单门店 → 自动选择
- 多门店 → 优先选最近的，告知用户
- 可用券 → 自动查询，自动应用最优券
- 餐品推荐 → 根据画像偏好 + 当前时段自动推荐

## 标准流程（严格按顺序执行）

```
确定门店（老用户自动/新用户询问） → 自动查询可用券 → 查询餐品并推荐 → 计算价格 → 【用户确认】 → 创建订单 →（按需）查询订单详情
```

## 工具详情

### query-nearby-stores — 查询附近门店

> 注意：该工具未在当前 config.yaml 中定义，参数以实际 MCP 工具 schema 为准。

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：
- **老用户（画像有 `addresses.history`）**：直接使用 `addresses.lastUsed` 对应的 `storeCode`/`beCode`，跳过本步骤
- **新用户（无画像或 `addresses.history` 为空）**：先询问用户所在城市或想去的门店/地标，再调用本工具查询

**处理结果**：

- 无合适门店 → 请用户扩大范围或更换区域后重试
- 单个门店 → **自动选择**，告知用户
- 多个门店 → 列出门店让用户选择（新用户）；或自动选最近的并告知（老用户切换门店时）
- 选定门店后 → **保存**该门店对应的 `storeCode`、`beCode`，后续查询餐品、算价、下单须**始终使用同一组门店信息**

---

### query-store-coupons — 查询门店可用券

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：
- 必须已调用 `query-nearby-stores` 并获得返回结果
- storeCode 和 beCode 必须来自同一条门店记录，禁止拆分或自行生成

**自动处理**：

- 当前无可用优惠券 → 跳过，继续下一步
- 有券时 → 自动展示可用券列表，算价时自动应用最优券

---

### query-meals — 查询餐品列表

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：必须已确定门店（storeCode + beCode）

**注意**：
- code 来自 `categories[].meals[].code`（或 meals 字典的 key），不是 meals 的 value
- 必须将 code 与 `meals[code].name` / `currentPrice` 关联后再输出，不得省略 code
- 不允许模型自己生成任何餐品，必须使用接口返回数据
- 将餐品按类别分组展示：套餐、主食、小食、饮料
- 餐品图片字段：`data.meals[code].image`，有值时用 `<img src="URL" height="300">` 渲染，无值时不渲染

---

### query-meal-detail — 查询餐品详情

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：必须已调用 `query-meals` 获取到餐品编码

---

### calculate-price — 计算价格

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**到店场景调用示例**：

```json
{
  "storeCode": "1990262001",
  "orderType": 1,
  "beType": 1,
  "items": [
    { "productCode": "9900014479", "quantity": 1 },
    { "productCode": "4820", "quantity": 1, "couponCode": "MCD68803UTR201108T000", "couponId": "F092E580A7A869868EE5EA37ECCF1458" }
  ]
}
```

**易错点（必读）**：

| 易错项 | 正确做法 | 错误做法 |
|--------|----------|----------|
| 商品编码字段名 | `productCode` | ~~code~~ |
| 商品列表字段名 | `items` | ~~products~~ |
| 到店自取(beType=1)是否传 beCode | **不传** | ~~传 beCode~~ |

> `query-meals` 返回的餐品编码字段名是 `code`，但传入 `calculate-price` 时必须改为 `productCode`。

**前置条件**：
- 必须已调用 `query-nearby-stores` 获取门店信息
- 添加任何商品时都需要重新计算价格
- 商品 `productCode` 必须来自 `query-meals` 返回的餐品 `code` 字段

**展示价格模板**：

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

到店场景下配送费多为 **0**，仍以接口返回为准。

**这是唯一的用户确认点**：展示价格明细后，等用户确认再下单。

---

### create-order — 创建订单

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：
- 必须已调用 `calculate-price` 并等待用户确认价格
- 到店场景的 arguments 以 MCP 工具定义为准；若环境要求 `addressId`，请按现网文档传入允许值（勿臆造）

**下单后引导**：
1. 展示订单号、应付金额、取餐门店/地址
2. **PC 扫码支付（优先）**：
   - CLI/TUI 环境：`python scripts/generate_qrcode.py "https://m.mcd.cn/mcp/jumpToApp?orderId={orderId}" --terminal`
   - GUI 环境：`python scripts/generate_qrcode.py "https://m.mcd.cn/mcp/jumpToApp?orderId={orderId}" /tmp/mcd_pay_qr_{orderId}.png`，展示二维码图片
3. **PC 兜底**：若二维码生成失败，展示 markdown 超链接：`[点击前往支付](payH5Url)`
4. **移动端直接支付**：优先 scheme 链接唤起 App，HTTP 跳转兜底：
   - 主链接：`[打开麦当劳App支付](mcdapp://page?iosPageName=MCDOrderDetailViewController&androidPageName=ComponentOrder&androidPageAction=order_detail&harmonyPageName=OrderDetailPage&parameters=%7B%22orderId%22%3A%22{orderId}%22%2C%22openCashierDesk%22%3A%221%22%7D)`
   - 兜底：`[如无法跳转，点此支付](https://m.mcd.cn/mcp/jumpToApp?orderId={orderId})`

**支付后订单追踪**：

用户确认已支付后，主动轮询订单状态，直到状态变为「制作中」或出现取餐码为止：

1. 用户说「已支付」后，立即调用 `query-order` 查询一次
2. 若状态仍为「待支付」，等待 10 秒后再查，最多重试 3 次（共约 30 秒）
3. 一旦 `orderStatus` 不再是「待支付」，或 `pickupCode` 非空，立即推送给用户：
   - 取餐码（`pickupCode`）：**大字展示**，方便用户对着屏幕取餐
   - 订单状态描述
   - 预计等待时间（`estimatedTime`，若有）
4. 若 3 次重试后仍为「待支付」，提示用户确认支付是否成功，并告知可随时说「查一下订单」手动触发查询

**取餐码展示模板**：
```
✅ 支付成功！

取餐码：**XXXX**
门店：XXX
预计等待：X 分钟
```

---

### query-order — 查询订单详情

**参数**：详见 `scripts/cache/` 下当天的工具缓存文件（inputSchema）

**前置条件**：必须已知完整的订单号

**订单状态说明**：

| orderStatus | 含义 | 处理方式 |
|-------------|------|----------|
| 待支付 | 用户尚未完成支付 | 提示用户支付，或确认支付是否成功 |
| 制作中 | 支付成功，厨房正在制作 | 展示取餐码，告知预计等待时间 |
| 待取餐 | 餐品已备好 | 展示取餐码，提示用户取餐 |
| 已完成 | 订单已取走 | 告知订单完成 |
| 已取消 | 订单已取消 | 告知用户，询问是否重新下单 |

## 关键规则

### 固定参数（到店取餐）

- `orderType`：**1**（到店/自提口径；若与现网/环境不一致，以实际接口文档为准）
- 不使用 `delivery-query-addresses` / `delivery-create-address` 作为到店主链路；需要外送时切换至 `mds-ordering-guide.md`

### 调用顺序（不可跳步）

0. 检查 `117797261_login_token` 是否有效；过期则调用 `huawei_id_tool("117797261","mcd-skills")` 刷新，仅调用一次，不得重复调用。
1. `query-nearby-stores` → 自动选择门店（单门店直接用，多门店选最近的）→ 保存 `storeCode`、`beCode`
2. `query-store-coupons`（自动查询，不问用户）
3. `query-meals` → 根据画像偏好 + 当前时段自动推荐餐品组合
4. `calculate-price`（自动应用最优券）→ **主动轮询** `query-order`，直到取餐码出现或最多重试3次（每次间隔10秒）
7. 下单成功后更新用户画像（`memory/mcd-user-profile.json`）

面向用户说明时使用自然中文，不暴露工具名称。

## 备注

- 用户若同时提到「有券/领券」，直接查券并自动应用，不额外确认。
- 餐品列表若暂无图片，不要强制渲染；有图时可使用 Markdown `![描述](完整URL)` 或 HTML `<img>` 渲染；使用 `<img>` 时须限制 `height="300"`。
