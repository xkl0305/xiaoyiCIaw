# 用户画像规范

## 文件位置

`memory/mcd-user-profile.json`

每次点餐交互开始时读取，结束后更新。

## 数据结构

```json
{
  "version": 1,
  "lastUpdated": "2026-04-30T16:00:00+08:00",
  "orderMode": {
    "delivery": 12,
    "pickup": 3,
    "groupMeal": 1,
    "preferred": "delivery"
  },
  "timePatterns": {
    "weekday": {
      "breakfast": { "count": 2, "lastItems": ["麦满分套餐"] },
      "lunch": { "count": 8, "lastItems": ["巨无霸套餐", "麦辣鸡腿堡套餐"] },
      "afternoon": { "count": 1, "lastItems": ["麦旋风"] },
      "dinner": { "count": 3, "lastItems": ["板烧鸡腿堡套餐"] },
      "lateNight": { "count": 0, "lastItems": [] }
    },
    "weekend": {
      "breakfast": { "count": 0, "lastItems": [] },
      "lunch": { "count": 2, "lastItems": ["双层吉士汉堡套餐"] },
      "afternoon": { "count": 1, "lastItems": ["薯条+可乐"] },
      "dinner": { "count": 1, "lastItems": ["麦辣鸡腿堡套餐"] },
      "lateNight": { "count": 0, "lastItems": [] }
    }
  },
  "favorites": {
    "meals": [
      { "name": "巨无霸套餐", "code": "XXX", "count": 5 },
      { "name": "麦辣鸡腿堡套餐", "code": "YYY", "count": 3 }
    ],
    "sides": ["薯条", "麦乐鸡"],
    "drinks": ["可口可乐（中）"]
  },
  "tags": ["偏辣", "爱套餐", "不喝奶茶", "常点外卖"],
  "addresses": {
    "lastUsed": "公司地址",
    "history": [
      { "label": "公司地址", "addressId": "xxx", "storeCode": "xxx", "beCode": "xxx" },
      { "label": "家", "addressId": "yyy", "storeCode": "yyy", "beCode": "yyy" }
    ]
  },
  "dineMode": {
    "preferred": "eat-in",
    "eatInCount": 0,
    "takeOutCount": 0
  },
  "couponUsage": {
    "prefersAutoCoupon": true,
    "lastUsedCoupons": ["11.9元麦乐鸡", "9.9元薯你最甜"]
  },
  "recentOrders": [
    {
      "date": "2026-04-28",
      "time": "12:30",
      "dayOfWeek": "Monday",
      "mode": "delivery",
      "items": ["巨无霸套餐", "麦乐鸡（5块）"],
      "total": 4500,
      "couponUsed": "11.9元麦乐鸡"
    }
  ]
}
```

## 读取规则

1. 点餐开始时，用 `read` 工具读取 `memory/mcd-user-profile.json`
2. 文件不存在时，视为新用户，创建空画像
3. 读取后根据当前时间和星期，匹配 `timePatterns` 中对应的时段

## 更新规则

1. **每次下单成功后**更新画像，不要在中间步骤更新
2. 更新内容：
   - `orderMode` 计数 +1，重新计算 `preferred`
   - `timePatterns` 对应时段计数 +1，更新 `lastItems`
   - `favorites.meals` 更新点餐计数
   - `recentOrders` 只保留最近 1 条订单（覆盖更新，减少上下文占用）
   - `tags` 根据累积行为推断（如连续 3 次点辣味 → 加"偏辣"标签）
   - `addresses.lastUsed` 更新为本次使用的地址
   - `lastUpdated` 更新时间戳
3. 用 `write` 工具写回 `memory/mcd-user-profile.json`

## 画像驱动决策

| 画像字段 | 决策用途 |
|----------|----------|
| `orderMode.preferred` | 意图模糊时，优先推荐偏好的点餐方式 |
| `timePatterns[当前时段].lastItems` | 推荐餐品时优先展示 |
| `favorites.meals` | 按 count 降序推荐 |
| `tags` | 过滤推荐（如"不喝奶茶"则不推荐奶茶类） |
| `addresses.lastUsed` | 自动选择上次使用的地址 |
| `dineMode.preferred` | 到店场景默认取餐方式（新用户默认 eat-in） |
| `couponUsage.prefersAutoCoupon` | 是否自动应用最优券 |

## 新用户处理

文件不存在时，创建初始画像：

```json
{
  "version": 1,
  "lastUpdated": "",
  "orderMode": { "delivery": 0, "pickup": 0, "groupMeal": 0, "preferred": null },
  "timePatterns": { "weekday": {}, "weekend": {} },
  "favorites": { "meals": [], "sides": [], "drinks": [] },
  "tags": [],
  "addresses": { "lastUsed": null, "history": [] },
  "couponUsage": { "prefersAutoCoupon": true, "lastUsedCoupons": [] },
  "recentOrders": []
}
```

新用户没有偏好数据时，按情境感知（时间段）推荐热门餐品，不追问偏好。
