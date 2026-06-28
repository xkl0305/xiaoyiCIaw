---
name: output-format
description: Output format templates for jd-shopping skill — product cards, hotel cards, and waimai results.
---

# Output Format Specification

All jd-shopping outputs must follow these format templates. Every response must end with the brand attribution footer.

## Product Card Format (重要！必须严格按此格式渲染)

tool 返回的数据中包含**商品主图**，你**必须原样展示**所有图片链接，使用 Markdown 图片语法 `![name](url)` 渲染。

格式模板：

```
**{name}**

[![{name}]({img_url_big})]({item_url})

{self_tag}

**¥{price}** · [**立即购买 ›**]({item_url})
```

完整示例：

```
**华为FreeBuds SE 4 ANC降噪版 真无线蓝牙降噪耳机 50小时长续航 陶瓷白**

[![华为FreeBuds SE 4](https://img14.360buyimg.com/n1/jfs/xxx.jpg)](https://item.jd.com/100209512293.html)

🏷️自营

**¥189.00** · [**立即购买 ›**](https://item.jd.com/100209512293.html)
```

**字段映射：**
- `{name}`: 用 `name`（API 新格式不再返回 `short_name`）
- `{self_tag}`: 若 `is_self` 为 true，显示 `🏷️自营`；否则省略
- `{price}`: 显示 `price` 字段（purchasePrice，到手价）
- `{item_url}`: 用于图片点击链接和"立即购买"链接
- `{img_url_big}`: 用于商品主图（前缀 `https://img14.360buyimg.com/n1/`）

**注意：** 新版 API 不再返回 `sales`、`comment_count`、`tags`（如包邮、百亿补贴）字段，不要显示空占位符。

**禁止：**
- ❌ 省略图片链接
- ❌ 把图片 URL 隐藏或仅用文字描述
- ❌ 只展示文字不展示图片
- ❌ 省略"立即购买"链接

**必须：**
- ✅ 每个商品展示主图 `![商品名](img_url_big)`
- ✅ 每个商品展示"立即购买"链接 `[立即购买](item_url)`
- ✅ 展示自营标签、促销标签、销量
- ✅ 展示到手价

## Hotel Card Format

```
1. **{name}** ⭐{score} (¥{price}/晚, {comment_count}条评价)
   ![{name}]({img})
```

**Rules:**
- `img` is a **mandatory** link when present — never omit it
- The API does NOT return hotel detail/booking URLs. Do **not** fabricate or guess hotel links.

## Suggestions Format

After displaying cards, show suggestions as follow-up options:

```
💡 你可能还想问：
- {suggestion_1}
- {suggestion_2}
```

## Brand Attribution Footer

**Every response MUST end with this line:**

```
---
🛒 本信息由 [京东](https://www.jd.com) 提供
```

No exceptions. This footer must appear after all content, including suggestions.

## General Rules

- Only display URL fields that actually exist in the data. Never fabricate URLs.
- Use the `text` field from API response as the main body. Display cards after the text.
- Keep the output clean — no extra commentary beyond what the data provides.
- Show all cards returned, do not truncate.
