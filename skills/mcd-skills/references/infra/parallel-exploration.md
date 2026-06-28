# 多方案探索策略

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
查门店/地址 → 查券 → 查菜单（管道过滤）→ 算价（多个方案）→ 一次性展示
```

### 多方案算价

如果需要展示多个餐品方案，对每个方案分别调用 calculate-price：

```bash
# 方案A
bash scripts/call_tool.sh calculate-price '{"storeCode":"xxx","orderType":1,"items":[{"productCode":"yyy","quantity":1}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['result']['structuredContent']['data']; print(f'A: price={d[\"price\"]} takeWayList={d.get(\"takeWayList\",\"\")}')"

# 方案B
bash scripts/call_tool.sh calculate-price '{"storeCode":"xxx","orderType":1,"items":[{"productCode":"zzz","quantity":1}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['result']['structuredContent']['data']; print(f'B: price={d[\"price\"]} takeWayList={d.get(\"takeWayList\",\"\")}')"
```

### 结果展示模板

```markdown
我帮你算了几个方案：

**方案 A：麦辣鸡腿汉堡三件套**（偏好推荐）
- 麦辣鸡腿汉堡三件套 × 1
- 应付：¥25.13

**方案 B："辣"么快乐套餐**（轻食）
- "辣"么快乐套餐 × 1
- 应付：¥18.00

选哪个？或者你想调整餐品？
```

## 不需要多方案的情况

以下场景直接走单一链路：

- 用户明确说了"外卖/麦乐送" → 直接走 mds-ordering-guide
- 用户明确说了"到店/自提/堂食" → 直接走 fc-ordering-guide
- 用户明确说了"团餐/公司订餐" → 直接走 group-meal-ordering-guide
- 用户画像偏好 ≥80% 且无矛盾信号 → 直接按偏好推进
- 非点餐意图（领券、查积分、查活动等） → 直接路由到对应 guide

## Token 节省规则（必须遵守）

所有返回大数据的 API（`query-meals`、`query-store-coupons`、`delivery-query-addresses` 等）必须通过 bash 管道 + python 内联脚本过滤后再使用结果，**绝不将原始 JSON 读入对话上下文**。

详见 `references/infra/tool-calling-strategy.md` 的「响应过滤」章节。
