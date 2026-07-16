# 输出格式参考【xiaoyiclaw 渠道】

_本文件为 xiaoyiclaw 渠道专属覆盖版，与 `scripts/lib/formatters.js`（xiaoyiclaw 定制副本）行为一致。_

> 🔸 **本渠道与基础版的两点差异**
> 1. **预订/跳转链接仅含 app 链接**：统一渲染为 `🔗 [app 预订](...)`，链接优先取 API 的 `superlinkRedirectUrl`，没有时取 `redirectAppUrl`；**不输出 PC 链接、不输出移动端 H5 链接**。
> 2. **酒店、景区强制卡片 + 图片**：即便 `channel=webchat`（默认走表格）也强制以卡片展示，每条结果顶部含 Markdown 图片 `![名称](image)`，`image` 取自对应资源对象的 `image` 字段。

---

## 📊 格式选择规则

逻辑由 `resolve_output_mode({ channel, surface })` 实现（各 `*-query.js` 共用），用于决定**表格 vs 卡片**。在 xiaoyiclaw 渠道还需叠加：

| 资源 | 展示形态 | 链接形式 |
|------|---------|---------|
| **酒店 / 景区** | **始终卡片 + 顶部图片**（忽略 `use_table`） | `🔗 [app 预订](...)` |
| 火车 / 机票 / 汽车 / 度假 / 行程规划 | 按 `resolve_output_mode` 决定表格或卡片 | `🔗 [app 预订](...)` |

> 说明：酒店/景区的「表格」入口（`format_hotel_table` / `format_scenery_table`）在本渠道已改为委托卡片渲染，故无论 `surface` 取值如何，最终都是带图卡片。

---

## 🔗 预订链接（`render_booking_buttons`）

| 模式 | 输出 |
|------|------|
| Markdown | `🔗 [app 预订](url)`（url 优先取 `superlinkRedirectUrl`，没有时取 `redirectAppUrl`） |
| 纯文本（`use_plain_link`） | `🔗 app：url` |
| `superlinkRedirectUrl` 与 `redirectAppUrl` 均为空/无效 | 空字符串（该条不展示预订链接） |

> ⚠️ 链接 URL 以脚本输出为准，不要根据示例重写。小艺 RobotId 场景下优先使用网关短链化后的 `superlinkRedirectUrl`；只有下游未返回 `superlinkRedirectUrl` 时，才兜底使用 `redirectAppUrl`，该兜底值可能是 `tctclient://` app 原生唤起协议。

---

## 🏨 酒店输出格式（卡片 + 图片）

```markdown
### 🏨 上海南京路步行街锦江都城南京饭店
![上海南京路步行街锦江都城南京饭店](https://pavo.elongstatic.com/i/ori/nw_Nr4186e27m.jpg)
**价格** ¥689 | **星级** 高档型 | **评分** ⭐4.8（4379条）
**品牌** 锦江都城
**设施** 停车场;免费wifi
**地址** 黄浦区 · 山西南路200号
🔗 [app 预订](https://wx.17u.cn/short/abc123)

---
```

- 图片来自 `hotel.image`，仅在有值时渲染。
- **品牌 / 设施 / 距离 / 推荐理由** 仅在字段有值时展示；**地址** 若存在 `countyName` 则拼接为 `区县 · 地址`。

---

## 🏞️ 景区输出格式（卡片 + 图片）

```markdown
### 🏞️ 杭州宋城
![杭州宋城](https://img.ly.com/scenery_songcheng.jpg)
**城市** 杭州 | **星级** 4A | **评分** ⭐4.8（14186条）
**门票** ¥260 | **开放时间** 未公布
**特点** 世界三大名秀之一
🔗 [app 预订](https://wx.17u.cn/short/def456)

---
```

- 图片来自 `scenery.image`，仅在有值时渲染。
- `needExtend=true` 时追加交通指引、票务信息、优惠政策、景区介绍、温馨提示等扩展块（规则同基础版）。

---

## 🚄 火车票 / ✈️ 机票 / 🚌 长途汽车 / 🧳 度假 / 🗺️ 行程规划

这些品类的表格/卡片列定义与基础版一致，**唯一差异是预订列/行只渲染 app 链接**。示例（火车票表格）：

```markdown
| 车次 | 出发站 | 到达站 | 出发时间 | 到达时间 | 运行时长 | 价格 | 预订 |
|------|--------|--------|---------|---------|---------|------|------|
| 🚅 G7209 | 苏州 | 上海 | 07:25 | 08:06 | 41 分 | 二等座¥42.0, 一等座¥69.0 | 🔗 [app 预订](https://wx.17u.cn/short/ghi789) |
```

其余品类（机票/特价机票/汽车/度假/行程规划/中转联程/补偿交通）的字段与列规则参见基础技能说明，链接形式统一替换为 `🔗 [app 预订](脚本输出的 app URL)`。该 URL 通常是 `superlinkRedirectUrl` 短链；若下游未返回该字段，则为 `redirectAppUrl` 兜底值。

---

## ⚠️ 输出强制要求

> 🚨 **以下内容是脚本输出的一部分，必须原样完整输出！**

1. **酒店/景区图片**（`![...](...)`）必须保留，不得删除或改写图片 URL。
2. **每个资源的 app 预订链接**必须输出，不得省略、替换或伪造。
3. **不要自行补充 PC / 移动端链接** —— 本渠道按设计仅提供 app 链接。
4. **不要把示例 URL 当作固定格式**。短链、`https://` 链接或 `tctclient://` 兜底协议都必须按脚本输出原样保留。
5. 底部引导语原样保留。

---

_同程旅行 · 让旅行更简单，更快乐_
