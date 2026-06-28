# JD Assistant API Specification

This document contains the complete API specification for calling JD Assistant API directly.
Use this when Python is not available (e.g. mobile environments).

## Endpoint

**URL:** `http://apigate-pre.shoppingbot.jd.local/v1/assistant/chat?channel=0&client_id=1721890337`

**Optional query parameters:**
- `&latitude={lat}&longitude={lng}` — required for food delivery, optional otherwise

**Method:** POST

## Request Headers

Required headers:

```
Content-Type: application/json;charset=utf-8
Accept-Charset: UTF-8
Origin: https://aigc-s.jd.com
user-agent: jdapp;android;15.2.90;;;M/5.0;appBuild/101798
Client-Version: 13.6.3
Connection: keep-alive
```

Optional: `Cookie: pt_pin={pin};` — if a JD user pin is available, include it for personalized results.

## Request Body

```json
{
  "content": "<user query text>",
  "scene_id": 1,
  "conversation_id": "<empty string for first query, or ID from prior response>",
  "new_conversation": true,
  "no_greeting": 0
}
```

**Field rules:**
- `content`: the user's search query as-is
- `scene_id`: always 1
- `conversation_id`: empty string `""` for first query; for follow-ups, use the conversation_id from the prior response
- `new_conversation`: `true` for first query, `false` for follow-ups
- `no_greeting`: `0` for first query, `1` for follow-ups (when conversation_id is set)

## Response Format (SSE)

The response is a Server-Sent Events stream. Each event is a line prefixed with `data: ` followed by JSON. The stream ends with `data: [DONE]`.

**Example stream:**
```
data: {"msg_type": 21, "content": "thinking..."}
data: {"msg_type": 1, "content": "为您推荐以下"}
data: {"msg_type": 1, "content": "华为手机："}
data: {"msg_type": 3, "content": {"data": ["查看详情", "对比价格"]}}
data: [DONE]
```

## Message Types (msg_type)

| msg_type | Name | content type | Action |
|----------|------|-------------|--------|
| 1 | Text chunk | `string` | Append to response text. This is the main content. |
| 3 | Suggestions | `{"data": ["s1", "s2", ...]}` | Extract suggestion strings for follow-up options. |
| 25 | Product cards | `{"data": [{"sku_list": [...]}]}` | Extract product SKU data (see below). |
| 35 | Hotel/flight cards | `{"trip_data": [...]}` | Extract structured card data (see below). |
| 21 | Thinking | `string` | Status indicator. May ignore or show as "thinking..." |
| 27 | Planning | `string` | Status indicator. May ignore. |
| 24 | Action | `string` | Status indicator. May ignore. |

## Hotel Card Structure (msg_type 35)

```json
{
  "trip_data": [
    {
      "hotel_card": {
        "hotelId": 1905920,
        "hotelName": "麗枫酒店(北京亦庄开发区京东总部店)",
        "price": 300,
        "score": 4.8,
        "img": "https://img14.360buyimg.com/hotel/jfs/t1/.../xxx.jpg",
        "commentCount": "688",
        "cityName": "北京",
        "groupName": "锦江酒店（中国区）",
        "todayBookable": 1
      }
    }
  ]
}
```

Key fields per hotel:
- `hotelId`: unique hotel identifier (no valid public detail URL available)
- `hotelName`: hotel display name
- `price`: starting price per night
- `score`: guest rating (e.g. 4.8)
- `img`: hotel main image URL — **must** be displayed
- `commentCount`: number of reviews

Display each hotel as: `- **{hotelName}** (评分: {score}, ¥{price}/晚, {commentCount}条评价) [酒店图片]({img})`

## Product Card Structure (msg_type 25)

```json
{
  "data": [
    {
      "sku_list": [
        {
          "sku_id": "100012345678",
          "product_name": "华为Mate 70 Pro",
          "full_name": "华为Mate 70 Pro 12GB+256GB 曜石黑",
          "price": "5499.00",
          "img_url_big": "https://img14.360buyimg.com/n1/jfs/xxx.jpg",
          "item_url": "https://item.jd.com/100012345678.html",
          "commentcount_fuzzy": "50万+",
          "good": "98%"
        }
      ]
    }
  ]
}
```

Key fields per SKU:
- `sku_id`: unique product identifier
- `product_name` / `full_name`: product display name (use `product_name`, fall back to `full_name`)
- `price`: current price
- `img_url_big`: main product image URL — **must** be displayed
- `item_url`: product detail page URL — **must** be displayed
- `commentcount_fuzzy`: approximate review count
- `good`: positive review rate

Display each product as: `- **{product_name}** (¥{price}) [商品主图]({img_url_big}) | [商品详情]({item_url})`

## Parsing Algorithm

1. Read response line by line
2. For each line:
   - Skip empty lines
   - Skip lines not starting with `data: `
   - Strip the `data: ` prefix
   - If remaining text is `[DONE]`, stop
   - Parse remaining text as JSON
   - Route by `msg_type` per the table above
3. Concatenate all text chunks (msg_type 1) into the full response
4. Collect all suggestions (msg_type 3) into a list
5. Collect all cards (msg_type 35) into a list

## Error Handling

- HTTP status != 200: report the status code and response body to the user
- JSON parse failure on a single line: skip that line, continue processing
- Network timeout (60s): report timeout to the user

## Multi-Turn Conversations

To maintain conversation context:
1. First query: send with `conversation_id: ""`, `new_conversation: true`
2. Generate a conversation ID: `jd_conv_` + first 8 chars of MD5 hash of the query
3. Follow-up queries: send with that conversation_id, `new_conversation: false`, `no_greeting: 1`

## Intent-Specific Notes

**Food delivery (外卖):** Always include `latitude` and `longitude` query parameters in the URL. Without location, the API cannot return nearby restaurants.

**Hotel search (酒店):** Location is optional but improves results. Hotel results arrive as msg_type 35 cards, not as text.

**Product search (商品):** No special parameters needed beyond the base request.
