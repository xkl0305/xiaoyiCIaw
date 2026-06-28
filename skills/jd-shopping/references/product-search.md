---
name: product-search
description: Product search and recommendation — intent mapping, commands, and error handling.
---

# Product Search

## When to Use

User expresses ANY shopping or purchasing intent — buying, recommending, comparing, asking about price, or mentioning any purchasable item. No category restriction.

## Command Format

```bash
curl -s -X POST https://meta-search.jd.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "<user query>", "flag": 1}'
```

Always use `flag: 1` for user natural language input. The API will internally rewrite it into search keywords.

## Intent Mapping

| User says | query value |
|-----------|-------------|
| 推荐华为手机 | `"推荐华为手机"` |
| 帮我挑选性价比高的Mac电脑 | `"性价比高的Mac电脑"` |
| 300元左右的运动水杯 | `"300元左右的运动水杯"` |
| 大米哪个牌子好 | `"大米哪个牌子好"` |
| 送女朋友什么礼物好 | `"送女朋友什么礼物好"` |
| 对比iPhone和华为 | `"对比iPhone和华为"` |

## Query Construction

**Critical:** Pass the user's full query as-is, preserving budget, brand, preference, and context. Do NOT strip to a single keyword.

| User says | Correct query | Wrong query |
|-----------|--------------|-------------|
| 帮我搜一下华为手机 | `"华为手机"` | `"手机"` |
| 5000元以内性价比高的笔记本 | `"5000元以内性价比高的笔记本"` | `"笔记本"` |
| 适合老人用的手机 推荐下 | `"适合老人用的手机"` | `"手机推荐"` |

## Output

Returns JSON with shape:
```json
{
  "domain": "sku",
  "results": [
    {
      "id": "skuid",
      "name": "商品名称",
      "price": "价格字符串",
      "image": "图片URL",
      "extra": {
        "brand": "品牌",
        "shop_type": "店铺类型",
        "catid": "类目ID",
        "source": "来源"
      }
    }
  ]
}
```

Render product cards using `references/output-format.md` template (markdown with images).

Key fields per product card:
- `name`: product display name
- `price`: current price
- `image`: product image path — prepend `https://img13.360buyimg.com/ling/` to get the full URL, **must** show as `![商品名](https://img13.360buyimg.com/ling/{image})`
- `id`: sku id — construct product URL as `https://item.jd.com/{id}.html`, show as `[立即购买](url)`
- `extra.brand`: brand name
- `extra.shop_type`: shop type — show `🏷️自营` if value is `"self"`

## Error Handling

| Error | User-facing message |
|-------|-------------------|
| HTTP 400 | "搜索参数错误：{detail}" |
| HTTP 500 | "元搜索服务异常，请稍后重试" |
| Connection refused / timeout | "元搜索服务连接失败，请稍后重试" |
| Empty results (`results: []`) | "未找到相关商品，试试换个关键词？" |
