---
name: travel-plan-designer
description: 完整的多日旅行方案设计工具。当用户要求"设计旅行方案"、"规划行程"、"旅行计划"、"旅游攻略"、"出行方案"、"定制旅游"或类似出行规划需求时触发。支持：多出发地同时规划、积分兑换优先、景点分类聚类分析、酒店通勤评估、预算汇总。核心步骤：收集信息→交通方案→酒店方案→景点方案→餐饮方案→预算与行程表输出。
---

# Travel Plan Designer · 旅行方案设计师

## ⚠️ 链接转换规则（所有步骤通用）

> **🔴 强制规则**：tc-chengxin 返回的链接是 `tctclient://` 深度链接，不能直接使用。必须根据输出场景转换：

### 输出场景与链接格式

| 输出场景 | 链接格式 | 规则说明 |
|:--------|:--------|:--------|
| **📝 Markdown 版**（对话中输出） | `superlink://vassistant?uri={原始tctclient链接}&h5={网页链接(可选)}` | 所有 `tctclient://` 链接包裹成superlink格式 |
| **🌐 HTML 网页版** | `https://...` 普通网页链接 | 替换为12306/携程等可访问的网页版链接 |

### 1️⃣ Markdown 版 · superlink 拼合规则

> **最终格式（已验证通过 ✅）**
>
> `superlink://vassistant?uri={整个deeplink做一次完整URL编码}&bundleName=com.tongcheng.hmos[&h5={网页链接做一次URL编码}]`

```python
import urllib.parse

# 原始 tctclient 链接（tc-chengxin 返回的原始值，可能已部分URL编码）
original_url = "tctclient://..."

# ⚠️ uri 参数：整个 deeplink 做一次完整的 URL 编码
# 不要先解码！直接 quote() 即可
uri_encoded = urllib.parse.quote(original_url, safe='')

# 同程包名（鸿蒙版）
bundle_name = "com.tongcheng.hmos"

# 目的地携程拼音（需在实际调用时替换，如南京→nanjing25、北京→beijing2）
des_pinyin = "{目的地拼音}"

# h5 网页链接（可选，只有同程API返回了网页地址时才添加）
# ⛔ 核心规则：只有tc-chengxin原始链接中自带网页地址时才提取，绝不自己编造
# 机票链接格式：tctclient://web/main?url=https%3A%2F%2Fwx.17u.cn%2F... — 从url参数中提取
if "web/main" in original_url:
    # 机票链接：从原始tctclient链接的 url= 参数中提取网页地址
    qp_raw = urllib.parse.parse_qs(urllib.parse.urlparse(original_url).query)
    h5_encoded_value = qp_raw['url'][0]
    h5_full = urllib.parse.unquote(h5_encoded_value)
    h5_encoded = urllib.parse.quote(h5_full, safe='')
    superlink = f"superlink://vassistant?uri={uri_encoded}&bundleName={bundle_name}&h5={h5_encoded}"
else:
    # ⛔ 高铁/酒店/景点：同程未返回网页地址时，不加h5参数
    superlink = f"superlink://vassistant?uri={uri_encoded}&bundleName={bundle_name}"
```

**示例（高铁，有h5回退）：**
- 原始：`tctclient://train/detail?wakeRefid=...&trainId=...`
- 最终：`superlink://vassistant?uri=tctclient%3A%2F%2F...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fkyfw.12306.cn%2F...`

**示例（机票，自带h5）：**
- 原始：`tctclient://web/main?url=https%3A%2F%2Fwx.17u.cn%2F...`
- 最终：`superlink://vassistant?uri=tctclient%3A%2F%2Fweb%2Fmain%3F...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fwx.17u.cn%2F...`
```

**结果示例：**
- ✅ 机票：`superlink://vassistant?uri=tctclient%3A%2F%2Fweb%2Fmain%...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fwx.17u.cn%2F...`
- ✅ 高铁：`superlink://vassistant?uri=tctclient%3A%2F%2Ftrain%2Fdetail%...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fkyfw.12306.cn%2F...`
- ✅ 酒店：`superlink://vassistant?uri=tctclient%3A%2F%2Fhotel%2F...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fhotels.ctrip.com%2F...`
- ✅ 景点：`superlink://vassistant?uri=tctclient%3A%2F%2Fscenic%2F...&bundleName=com.tongcheng.hmos&h5=https%3A%2F%2Fyou.ctrip.com%2F...`

### 2️⃣ HTML 网页版 · 链接规则

> **🔴 核心规则：只使用 tc-chengxin 返回的数据。同程没有返回网页地址的，通过搜索找到正确的官方预订入口，绝不自己编造。**

生成 HTML 时，不能使用 `tctclient://` 或 `superlink://` 链接，必须转换为**普通浏览器可访问的 `https://` 链接**。

**优先从 tc-chengxin 提取（仅机票）：**
| 类型 | 替换方案 |
|:----|:--------|
| ✈️ **机票** | 从 `tctclient://web/main?url=...` 解码 `url` 参数得到 `https://wx.17u.cn/...` ✅ 同程自带 |

**同程未返回网页地址 → 通过搜索获取官方预订入口：**
| 类型 | 处理方式 |
|:----|:--------|
| 🚄 **高铁** | 使用 `xiaoyi-web-search` 搜索 `"{出发站} 到 {到达站} 高铁 {日期} 12306 预订"`，获取12306官方链接 |
| 🏨 **酒店** | 使用 `xiaoyi-web-search` 搜索 `"{酒店名} 官网"` 或 `"{酒店名} 预订"`，获取官方/平台预订页 |
| 🏞️ **景点** | 使用 `xiaoyi-web-search` 搜索 `"{景点名} 门票 预订 官网"`，获取官方购票入口 |

> ⛔ **严禁行为：** 不要自己拼接 12306/携程/去哪儿等链接（即使有规律也不能编造）。同程没返回就搜索找到正确的链接。搜索也找不到的，在 HTML 中不放置该条目的跳转链接，仅保留文字描述。

---

## 🚨 硬性前置门禁：tc-chengxin 认证检查（必须最先执行）

本技能的机票、火车票、酒店、景点/门票等信息均依赖**同程程心（tc-chengxin）** 的搜索能力。

### 规则（严格按此顺序执行，不可跳过、不可变通）：

**① 必须检查：** 在进入任何搜索流程（包括 Step 1~6）之前，先读取 `/home/sandbox/.openclaw/.xiaoyienv` 中的 `{你的clientId}_login_token` 与 `{你的clientId}_login_token_expire_time`。

- **有值且未过期** ✅ → 凭证就绪，继续执行

- **为空/不存在/已过期（当前时间 > expire_time）** ❌ → **进入步骤 ②**

**② 不可用 → 必须调用 huawei_id_tool 刷新：** 每次检测到凭证为空或过期，**必须**调用一次 `huawei_id_tool`（参数：`skillName=tc-chengxin`，`clientId={你的clientId}`）。

- **授权成功** ✅ → 重新读取 `.xiaoyienv` 获取凭证
- **授权失败 ❌ → 询问用户是否愿意手动配置 API Key（见下方说明），用户拒绝则停止流程**

> ⚠️ **分享说明：** 这里的 `clientId` 需要替换为你自己的华为 Client ID。获取方式：在同程旅行开放平台注册应用后获取。在 `.xiaoyienv` 中对应的 key 为 `{clientId}_login_token` 和 `{clientId}_login_token_expire_time`。

### 如何获取 API Key

1. 访问同程旅行开放平台
2. 注册/登录账号
3. 在控制台中申请并获取 API Key

### 如何帮用户配置 API Key

将用户的 Key 写入 `/home/sandbox/.openclaw/workspace/skills/tc-chengxin/config.json`

---

## ⚠️ 关于 tc-chengxin 输出与配图

tc-chengxin 的各 *_query.js 脚本**本身会返回完整的 Markdown 内容**，包括：
- ✈️ 航班：预订链接 `[🎫 点击预订](...)`
- 🚄 火车：班次信息 + 预订指引
- 🏨 酒店：表格 + `![](图片URL)` 配图 + `[🏨 预订](...)`
- 🏛️ 景点：表格 + `![](图片URL)` 配图 + `[🎫 购票/预订](...)`

**重要规则：脚本返回的图片和预订链接必须原样保留，不得删除或改写。**

### 当前 tc-chengxin 图片字段名

> ⚠️ **当前 tc-chengxin 返回的图片字段名是 `image`**（酒店和景点都是），不是旧的 `mainPic` 或 `picUrl`。

### 图片处理方式

> **HTML 和 Markdown 统一规则：直接使用 tc-chengxin 脚本返回的原始图片 URL，不做 base64 转码。**
> 
> 如果图片在手机/PC 端无法加载，属于外部链接限制，不进行修复。
> 
> **强制：方案正文必须保留 tc-chengxin 返回的所有 `![]()` 图片和 `[🎫 购票]()`/`[🏨 预订]()` 链接，一张都不能少。**

---

## 核心流程

采用 **6 步流水线** 设计旅行方案。用户说完了直接进入 Step 2~6，不要问确认问题。

---

## Step 1：收集信息（信息确认）

### 默认值（内部使用，不对用户展示）

- **出行时间偏好**：早上出发，晚上返回
- **旅行偏好**：自然风光 + 城市人文结合
- **航空积分**：无
- **年龄**：默认成年人，无老人小孩

> 默认值在给用户的回复中不展示，用户说了什么就显示什么。

### 信息收集

用户一次性提供的信息直接使用，缺的才逐项追问。追问顺序如下：

0. **🖼️ 第零步：检查用户是否发送了参考图片**
   - 如果用户发送了旅行攻略图/景点图等参考图片，**必须优先使用 `image_reading` 工具识别图片内容**
   - 提取图片中包含的**所有景点、路线、建议**，作为方案的核心骨架
   - 在行程安排中**优先包含图片中出现的景点**，确保图片中的推荐内容全部涵盖
   - 图片中的提示（如预约提醒、交通建议、美食推荐等）也必须在方案中体现
   - 图片中没有但用户额外要求的景点可以补充进去，但不得删除图片中已有的核心景点

1. **💡 第一步：确认旅行预算档次**
   - **🤫 前置规则（先查档案，能不问就不问）：** 在询问用户之前，**必须先翻查 MEMORY.md 和 USER.md**，分析用户已有的消费/预算画像信息。如果档案中有明确的消费偏好的描述（如"舒适型""经济型""豪华型"等倾向），直接使用档案推断，不要问用户。
   - 若档案中无足够信息支撑推断，才主动询问用户需要哪种预算档次：**舒适型**（性价比优先）、**经济型**（省钱为主）还是**豪华型**（品质优先）
   - 根据确认的档次，后续酒店推荐、交通方案、餐饮推荐等做相应调整
   - 如果用户说"随便"或"都行"，默认舒适型

2. **📍 第二步：获取用户位置（如果用户也去旅行）**
   - **规则：直接调用 `get_user_location` 工具，不得询问用户"你在哪里"。** 这个工具会自动返回用户的当前位置。
   - 如果用户本人也参与此次旅行（即用户是出行者之一），必须直接调用 `get_user_location` 获取用户当前位置
   - 如果用户不参与旅行（只是帮别人规划），跳过此步

3. **🧑🤝🧑 第三步：确认其余同行人出发地**
   - 如果用户也去旅行，用 get_user_location 返回的地址作为用户当前城市，然后询问同行其他人是否和用户从同一个地方出发
   - 如果不从同一地出发，分别询问每个人的出发城市
   - 如果用户不参与旅行，直接询问所有出行人的出发城市

4. **后续信息追问（按需）**
   - **出发城市**：可有多个出发地（已通过上述步骤确认）
   - **人数**：几人出行
   - **出行日期**：具体日期。如果用户说了节日名（如端午节、五一、国庆等），自动推算出法定节假日天数，默认玩满整个假期，不再追问玩几天
   - **航空积分**：默认无积分，仅在用户主动说有积分时才追问

> **关键规则**：
> - 不要问年龄，默认成年人
> - 预算档次必须在方案开始搜索前确认
> - 用户说完了就直接进入 Step 2 开始搜索，不要问"信息对不对"
> - 配图来自 tc-chengxin 脚本输出，直接展示，不问用户"是否需要配图"

---

## ⚠️ 重要约束：禁止修复图片/链接

方案输出完毕后，**禁止**以下行为：
1. **不得**因图片链接失效而启动修复流程（如重新搜索图片、替换URL、下载上传等）
2. **不得**因任何原因覆盖、删除或撤回已输出的完整 Markdown 方案内容
3. 所有修复/补充内容必须以**追加消息**的形式独立发送，不得修改原方案
4. 方案中的图片来自 tc-chengxin 脚本返回结果，直接展示即可。图片加载效果由用户端决定，**不**需要你主动修复

> **核心原则：** 一次输出即定稿。输出的Markdown方案是完整的、不可撤销的。后续任何调整（住宿档次、增减景点等）都属新需求，按新需求走，不叫"修复"。

---

## 🌤️ Step 1.5：目的地天气查询（必做）

在进入交通/住宿/景点搜索之前，**必须先查询目的地旅行期间（含每一天）的天气预报**，作为后续推荐酒店档次、景点选择、着装建议的依据。

### 1.5.1 天气查询

**优先使用 weather skill（wttr.in）查询：**

```bash
curl "wttr.in/{目的地城市英文名}?format=j1"
```

如果 wttr.in 不支持中文城市名，使用拼音或英文名（如 `Nanjing`、`Beijing`）。

从返回的 JSON 中提取以下信息（重点关注旅行覆盖的每一天）：
- **天气状况**（晴天/阴天/雨天等）
- **气温范围**（最高温/最低温）
- **降水概率 / 降水量**
- **风力**
- **湿度**

### 1.5.1.1 预报覆盖范围检查 & 降级处理

wttr.in 免费版仅提供 **3 天预报**，旅行日期可能超出其覆盖范围，必须检查并处理：

**检查方法：** 获取当前日期，对比 wttr.in 返回的 `weather[]` 中最后一天的日期与旅行最后一天的日期。
| 情况 | 处理方式 |
|------|---------|
| ✅ 旅行日期完全被预报覆盖 | 直接使用 wttr.in 预报数据，标注 `📡 实时预报` |
| ⚠️ 部分覆盖 | 被覆盖日期用 wttr.in 数据；未覆盖日期使用 `xiaoyi-web-search` 搜索历史同期气候数据 |
| ❌ 完全未覆盖（查询日距旅行日 > 3天） | 全部使用联网搜索获取历史同期气候数据 |

**降级搜索模板（使用 xiaoyi-web-search）：**
```
{目的地城市} {月份}月 天气 平均气温 降水
{目的地城市} {月份} 旅游 气候特点 穿衣指南
```

**数据标注规则：**
- 有 wttr.in 实时预报的日期 → 标注 `📡 预报`
- 联网搜索获得的同期数据 → 标注 `📊 历史同期参考`
- 用语示例：*"6月南京为梅雨季，历史同期平均气温24~32°C，降雨概率约40%"*

### 1.5.2 天气对行程的影响分析

根据天气结果，在后续规划中做针对性调整：
| 天气情况 | 后续影响 |
|---------|---------|
| 🌧️ 雨天/高降水概率 | 优先安排室内景点（博物馆、美术馆）、室内餐饮；户外景点放在天气好的时段，户外活动准备雨具 |
| ☀️ 高温（30°C+） | 推荐有空调的室内活动，户外安排上午早段或傍晚，注意补水提醒，建议防晒 |
| ❄️ 低温/大风 | 推荐室内活动、火锅/热食餐饮 |
| 🌤️ 多云/舒适 | 按常规安排即可 |
| 🌫️ 雾霾/空气质量差 | 减少户外活动，推荐室内景点 |

### 1.5.3 天气数据存档

将天气数据暂存，后续在 Step 6 输出方案时强制添加以下内容：

**1. 在行程表顶部增加每日天气概览行**（天气图标 + 温度范围）

**2. 在方案尾部增加「🧳 出行提醒」板块**，必须包含：

```markdown
### 🧳 出行提醒

#### 📄 证件携带
- **身份证/护照**：乘坐高铁/飞机需实名验证，酒店入住必须登记
- 建议提前将证件放在随身小包中，方便取用
- 如外籍人士，请携带护照及有效签证

#### 👔 着装建议
（基于已查到的{目的地}天气预报数据动态生成）
- 预计气温：XX°C ~ XX°C
- 推荐：XXXX（根据天气动态推荐）
- 如有雨天：☂️ 建议携带雨伞/雨衣
- 如有高温：🧴 建议做好防晒，携带水杯及时补水
- 如有温差大：🧥 建议携带薄外套

#### ⚠️ 其他提醒
- 端午/节假日出行高峰，建议提前预订交通和门票
- 各景点可能限流，请提前在官方渠道预约
- 注意随身财物安全
```

---

## Step 2：交通方案（去程 + 回程）

**核心原则：积分兑换优先 > 经济舱 > 高铁备选**

**整体要求：** 优先使用 tc-chengxin 脚本获取同程官方机票/高铁/交通数据，脚本返回的表格和预订链接**必须原样输出**。

### 2.1 航班搜索（使用 tc-chengxin）

**优先使用 tc-chengxin 的 `flight-query.js` 获取航班信息：**

```bash
# 去程
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/flight-query.js --departure "{出发城市}" --destination "{目的地城市}" --extra "{日期}" --channel xiaoyi-channel --surface xiaoyi-channel

# 回程
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/flight-query.js --departure "{目的地城市}" --destination "{出发城市}" --extra "{返程日期}" --channel xiaoyi-channel --surface xiaoyi-channel
```

如有多个出发地，分别搜索，尽量选择到达时间相近的航班。

**特价/低价查询（如用户说"便宜"、"特价"等）：**

```bash
# 指定航线特价
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/flight-query.js --departure "{出发城市}" --destination "{目的地城市}" --low-price --extra "{日期} 最便宜" --channel xiaoyi-channel --surface xiaoyi-channel
```

**脚本输出内容：** 航班列表（表格形式），每条航班含 `[🎫 点击预订此航班]({jumpUrl})` 预订链接。

> ⚠️ `flight-query.js` 返回的**原样表格和预订链接**必须完整保留，**禁止**修改格式或省略预订链接。

### 2.2 高铁搜索

**优先使用 tc-chengxin 的 `train-query.js`：**

```bash
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/train-query.js --departure "{出发城市}" --destination "{目的地城市}" --extra "{日期} 高铁" --channel xiaoyi-channel --surface xiaoyi-channel
```

**脚本输出：** 包含车次、时间、价格等信息的表格。

### 2.3 未指定交通方式 → 智能交通推荐

**使用 tc-chengxin 的 `traffic-query.js`：**

```bash
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/traffic-query.js --departure "{出发城市}" --destination "{目的地城市}" --extra "{日期}" --channel xiaoyi-channel --surface xiaoyi-channel
```

**脚本输出：** 同时展示 ✈️ 机票 + 🚄 火车 + 🚌 汽车等多种交通方案供对比。

### 2.4 积分兑换

如果有航空积分，优先查询积分兑换方案和所需积分数量。

```bash
xiaoyi-web-search "{航司名称} {出发城市}到{目的地城市} 积分兑换 {日期}"
```

---

## Step 3：住宿方案

3.1 使用 `xiaoyi-web-search` 搜索景点分布，确定住宿推荐区域。

**搜索模板：**
```
{目的地} 旅游景点分布 区域推荐
```

3.2 按景点位置对住宿区域做聚类分析，推荐 2~3 个候选区域。

3.3 对每个候选区域**使用 tc-chengxin 搜索酒店**：

```bash
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/hotel-query.js --destination "{目的地}" --extra "{区域} {入住日期} 入住" --channel xiaoyi-channel --surface xiaoyi-channel
```

**脚本输出：** 酒店列表带图片（`![]({图片URL})`）+ 带 `[🏨 预订]({预订URL})` 链接。

> **必须原样保留**脚本返回的酒店图片和预订链接。

如 tc-chengxin 不可用，降级使用 `xiaoyi-web-search`：

```
{目的地} {区域} 酒店 {入住日期} 推荐 价格
```

---

## Step 4：景点方案

4.1 **使用 tc-chengxin 的 `scenery-query.js` 搜索景点信息：**

```bash
node ~/.openclaw/workspace/skills/tc-chengxin/scripts/scenery-query.js --destination "{目的地}" --extra "{天数} {季节} 必去景点" --channel xiaoyi-channel --surface xiaoyi-channel
```

**脚本输出：** 景点列表（带图片 `![]({图片URL})`  + `[🎫 购票/预订]({jumpUrl})` 预订链接）。

> **必须原样保留**脚本返回的景点图片和预订链接。

4.2 使用 `xiaoyi-web-search` 查询景点间的交通路线：

**搜索模板：**
```
{景点A} 到 {景点B} 怎么走 地铁
```

查询每个相邻景点间的推荐交通方式（地铁/公交/步行）和大致耗时，用于行程表中标注路线指引。

4.3 核验每个景点的关键信息：
- 开放时间（是否有闭馆日）
- 门票价格
- 是否需要提前预约
- 端午/节假日是否有特别安排

4.4 按游玩路线分组（第一天 / 第二天 / 第三天 ...），确保：
- 相邻景点之间交通方便
- 上午和下午安排合理
- 留出用餐时间和休息时间
- 注意景点闭馆时间

4.5 提供同程官方预约入口链接（来自 tc-chengxin 脚本输出）。

---

## Step 5：餐饮方案

5.1 使用 `xiaoyi-web-search` 搜索：

**搜索模板：**
```
{目的地} 必吃美食 推荐
{目的地} 本地人推荐的餐厅
{景点区域} 附近美食 推荐
```

5.2 输出推荐：
- 特色美食介绍
- 推荐餐厅（含地址/特色菜）
- 节假日期间是否有特色饮食

---

## Step 6：预算汇总 & 行程表输出

6.1 汇总整个方案到一张 **N 天 M 晚行程表**（或相应天数的表格），**每个时间段标注路线指引**：

**表格格式：** 使用标准Markdown表格。tc-chengxin 返回的景点/酒店图片和预订链接**在表格下方独立展示**（图片在表格单元格内显示太小）。

**示例：**

| 日期 | 时间 | 活动 | 地点 | 🚶 路线指引 | 备注 |
|------|------|------|------|------------|------|
| Day1 | 上午 | 到达{目的地} | {站点} | 各自抵达 | 交通信息 |
| | 中午 | 午餐 | XX餐厅 | 地铁X号线 | - |
| | 下午 | 🏛 **{景点}** ⭐⭐⭐⭐⭐ | {景点地址} | 🚇{交通方式} 约X分钟 | 🎫{门票} |

**图片展示规则（表格下方）：**

```
![]({tc-chengxin返回的景点图片URL})
[🎫 购票/预订]({tc-chengxin返回的预订链接})
```

**路线指引列**写清上一站到当前站点的交通方式（地铁几号线、打车约多久、步行多远等）。

6.2 在行程表之后，增加一个 **🔔 需要预约的景点清单** 板块：
```
### 🔔 需要预约的景点

列出所有需要提前预约的景点，每项包含：
- 景点名称
- 预约方式（公众号/官网/小程序）
- 注意事项（如：周一闭馆、需提前X天）
- 预约链接（来自 tc-chengxin jumpUrl）
```

6.3 输出 **预算汇总表**：

| 项目 | 预估费用（每人） | 备注 |
|------|-----------------|------|
| 交通（去程） | ¥xxx | |
| 交通（回程） | ¥xxx | |
| 住宿（N晚） | ¥xxx | 人均 |
| 门票 | ¥xxx | 合计 |
| 餐饮（N天） | ¥xxx | 预估 |
| 市内交通 | ¥xxx | |
| **总计** | **¥xxx** | |

### 6.3.1 在预算汇总表后增加每日天气概览

根据 Step 1.5 查到的天气数据，在预算表后增加每日天气概览：

```markdown
### 🌤️ 每日天气

| 日期 | 天气 | 温度 | 建议 |
|:----:|:----:|:----:|:----|
| Day1 (日期) | 天气图标 | XX~XX°C | 建议 |
| Day2 (日期) | 天气图标 | XX~XX°C | 建议 |
| Day3 (日期) | 天气图标 | XX~XX°C | 建议 |
```

### 6.3.2 在天气概览后增加「🧳 出行提醒」板块

```markdown
### 🧳 出行提醒

#### 📄 证件携带
- **身份证/护照**：乘坐高铁/飞机需实名验证，酒店入住必须登记
- 建议提前将证件放在随身小包中，方便取用
- 如外籍人士，请携带护照及有效签证

#### 👔 着装建议（基于天气预报）
- 预计气温：XX°C ~ XX°C
- 推荐：根据天气动态生成（如短袖+薄外套、带雨具、注意防晒等）
- 如有雨天：☂️ 建议携带雨伞/雨衣
- 如有高温：🧴 建议做好防晒，携带水杯及时补水
- 如有温差大：🧥 建议携带薄外套

#### ⚠️ 其他提醒
- 端午/节假日出行高峰，建议提前预订交通和门票
- 各景点可能限流，请提前在官方渠道预约
- 注意随身财物安全
```

---

6.4 **输出方案 → 分步交付（先输出 Markdown，询问后再决定是否生成 HTML）**

> **🔴 核心规则：先在对话中输出 Markdown 版方案，然后主动询问用户是否需要精美的 HTML 网页版，用户确认后再生成并通过 send_file_to_user 发送到手机。**

**6.4.1 🥇 第一步：在对话中输出 Markdown 版方案**
- 使用标准 Markdown 表格 + 要点列表，在对话中完整呈现整个方案
- 含 tc-chengxin 返回的所有配图（`![]({图片URL})`）和预订链接
- 确保 Markdown 版内容完整、美观、可直接阅读

**6.4.2 🥈 第二步：Markdown 输出后，主动询问用户是否需要 HTML 网页版**

Markdown 版方案在对话中输出完毕后，**必须主动询问用户**是否需要生成精美的 HTML 网页版方便在手机上查看。

**询问话术模板：**
```
🗂️ 已经为你生成了完整的旅行方案！

需要我帮你生成一个精美的 **HTML 网页版** 吗？网页版在手机上打开视觉效果更好，方便随时翻看行程。

回复 "要" 或 "好"，我马上帮你生成～
```

**关键规则：**
- **必须主动询问用户**，不能跳过这一步
- 询问之前不能生成 HTML 文件
- 询问后等待用户回复，用户确认后才进行下一步

**6.4.3 🥉 第三步（仅用户确认后）：生成 HTML 并通过 send_file_to_user 发送到手机**

用户回复需要 HTML 后：
- 立即按照下方 **HTML 报告生成规范** 生成精美的 HTML 网页版
- HTML 生成完毕后，调用 `send_file_to_user` 工具将 HTML 文件发送到用户手机
- **禁止使用 send_html_card 工具或 message 工具代替 send_file_to_user**
- 如果方案内容中的图片URL因权限或时效无法在HTML中正常渲染，则降级为不配图但保留文字内容
- 发送成功后，可以告知用户已发送

### HTML 报告生成规范

将方案内容渲染为一个单页 HTML 文件，要求如下：

**整体风格**：旅行/度假主题，清新、明亮、有视觉冲击力。

**配色方案**：
- 主色：#2563EB（天空蓝）
- 强调色：#F59E0B（阳光金）
- 背景：#F0F9FF（极淡蓝）
- 卡片底色：#FFFFFF
- 正文：#1E293B
- 次要文字：#64748B

**页面结构**：

1. **顶部 Hero 区** — 目的地名称 + 日期 + 天数 + 人数，大号渐变标题
2. **交通方案** — 去程/回程卡片，每卡片含：出行方式图标、时间、价格、预订链接按钮
3. **酒店推荐** — 横向卡片网格，每卡片：酒店图片（圆形裁切+阴影）、酒店名、价格、通勤时间、预订按钮
4. **行程表** — 以日期为 Tab 分天展示，每天用时间线（Timeline）布局
   - **每日顶部增加天气概览行**（天气图标 + 温度范围）
   - 每个活动条目：时间徽章 + 活动名称 + 地点 + 路线指引 + 景点图片（圆角） + 预订按钮
5. **需要预约的景点清单** — 红底/橙底警告卡片列表
6. **餐饮推荐** — 餐厅卡片网格，含特色菜标签
7. **预算汇总** — 带进度条或饼图样式的汇总卡片，总计高亮
8. **🧳 出行提醒** — 淡蓝底卡片，包含：
   - 📄 **证件携带提醒**：身份证/护照、酒店入住登记
   - 👔 **着装建议**：基于天气数据的穿衣推荐、雨具/防晒提醒
   - ⚠️ **其他提醒**：节假日限流、提前预约、财物安全

**交互元素**：
- 所有预订链接用蓝色按钮样式（`<a>` 标签 inline-block 模拟）
- 使用 CSS 动画：卡片淡入（`@keyframes fadeInUp`）
- 使用 flexbox/grid 布局，自适应宽度
- 字体使用系统字体栈

**图片处理**：
- **直接使用 tc-chengxin 返回的原始图片 URL**（`<img src="...">`），**禁止 base64 转码**
- 图片加圆角（`border-radius: 12px`）和阴影
- **⛔ 禁止下载图片后再进行 base64 编码**
- **⛔ 禁止对 `<img>` 标签写死 `height` 属性**
- **⛔ 禁止用 `object-fit: cover`  + `max-height` 裁剪图片**→ 会导致 PC 大屏上图片被裁
- **所有 `<img>` 统一用 `max-width: 100%` + `height: auto`**，保持原始宽高比，不做裁剪
- PC 大屏不限制图片高度，让其自然展示完整内容

**响应式排版规则（PC + 手机双端适配）**：
| 模块 | 手机 (<768px) | PC (≥768px) |
|------|--------------|-------------|
| 酒店/景点/餐饮网格 | **1列** (`grid-template-columns: 1fr`) | **2~3列** (`grid-template-columns: 1fr 1fr`) |
| 天气卡片 | flex-wrap 横排 | 同样横排，间距加大 |
| 交通卡片 | 垂直堆叠 | flex 横向两栏 |
| Hero 区 | 上下居中 | 居中 + 更大字号 |
| 总宽度 | **100% 填满** | **max-width: 860~960px 居中** |
| 图片高度 | 不限制（`height: auto` 自然高度） | 不限制（`height: auto` 自然高度）|
| 文字大小 | 13~14px | 14~16px |
- 必须写 `@media` 断点，默认 PC/平板 ≥768px 用多列，<768px 手机用单列**
- 禁止用固定 `px` 宽度（如 `width: 300px`），必须用 `%` / `max-width` / `min-width`

**技术限制**：
- 纯 HTML + 内联 CSS（不要外部资源，方便离线查看）
- 不要 JavaScript（保持简单）
- 所有资源使用 HTTPS
- 在页面底部添加生成信息脚注

> **提示**：将方案内容填充到以下骨架模板中，输出到本地文件（如 `/home/sandbox/.openclaw/workspace/travel-plan-{目的地}.html`），然后调用 `send_file_to_user` 工具发送给用户。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{目的地}旅行方案</title>
<style>
  /* 所有样式内联在此，参考上方规范 */
</style>
</head>
<body>
  <!-- 完整方案内容 -->
</body>
</html>
```

6.5 方案交付结束后，可根据需要询问用户是否需要调整方案细节（如换酒店、增减景点等）。

---

## 工具优先级

| 优先级 | 工具/命令 | 用途 |
|--------|----------|------|
| 🥇 | `tc-chengxin flight-query.js` | 航班搜索：含 `[🎫 点击预订](...)` |
| 🥇 | `tc-chengxin train-query.js` | 火车票搜索：含车次/价格/时间 |
| 🥇 | `tc-chengxin traffic-query.js` | 交通综合查询（未指定方式时） |
| 🥇 | `tc-chengxin hotel-query.js` | 酒店搜索：含 `![](图片)` + `[🏨 预订](...)` |
| 🥇 | `tc-chengxin scenery-query.js` | 景点搜索：含 `![](图片)` + `[🎫 购票](...)` |
| 🥇 | `tc-chengxin bus-query.js` | 长途汽车票查询 |
| 🥇 | `tc-chengxin travel-query.js` | 度假产品/跟团游 |
| 🥇 | `weather skill`（`curl wttr.in`） | 目的地天气预报 |
| 🥇 | `xiaoyi-web-search` | 高铁备选、景点详细信息(开放时间/门票)、餐饮推荐、天气降级 |
| 🥇 | `send_file_to_user` | HTML 方案文档发送（唯一方式） |
| ❌ | `message` / `send_html_card` | 禁止用于 HTML 交付 |

> 所有 tc-chengxin 脚本调用时必须传 `--channel xiaoyi-channel --surface xiaoyi-channel` 参数。

---

## ✅ 输出格式规范（必须遵守）

### 1. 先在对话中输出 Markdown 版（优先级最高）

优先在对话中输出完整的 Markdown 版方案，让用户第一时间看到完整方案内容。

**Markdown 版必须包含：**
- tc-chengxin 脚本返回的所有景点配图（`![](...)`）和 `[🎫 购票/预订](...)` 链接
- tc-chengxin 脚本返回的所有酒店配图（`![](...)`）和 `[🏨 预订](...)` 链接
- **🛑 强制规则：脚本返回了图片就必须原样保留，不能删。**
- 完整的行程表、预算表、餐饮推荐、预约提醒
- 出行提醒（天气/着装/证件）

### 2. Markdown 输出后询问用户是否需要 HTML 网页版

Markdown 版输出完毕后，**必须主动询问用户**是否需要生成 HTML 网页版。等待用户确认后才生成。

- **🚫 禁止：** 未询问直接生成 HTML ❌ | 未等用户回复就生成 ❌

### 3. 用户确认后生成 HTML 并发送到手机

用户确认需要 HTML 后，生成 HTML 文件并通过 `send_file_to_user` 发送到手机。

**流程为：**

1. **🥇 在对话中输出 Markdown 版方案** — 独立消息，有图则配图，无图则纯文字
2. **🥈 主动询问用户是否需要 HTML 网页版** — 等待用户回复
3. **🥉 用户确认后 → 生成 HTML → 调用 send_file_to_user**（不输出正文）

---

## ✅ 6 步流程总览

| 步骤 | 内容 | 数据来源 | 备注 |
|:----:|------|---------|------|
| **1** 📋 | 收集信息 | 用户 + `get_user_location` | 出发地/目的地/人数/日期/预算 |
| **1.5** ☁️ | 天气查询 | `wttr.in` / `xiaoyi-web-search` | 必做！影响景点/穿搭推荐 |
| **2** ✈️🚄 | 交通方案 | `tc-chengxin flight/train/traffic-query` | 去程 + 回程 |
| **3** 🏨 | 住宿方案 | `tc-chengxin hotel-query` | 含图片+预订链接 |
| **4** 🏛️ | 景点方案 | `tc-chengxin scenery-query` | 含图片+预订链接 |
| **5** 🍽️ | 餐饮推荐 | `xiaoyi-web-search` |  |
| **6** 📊 | 预算+行程表 | 汇总 | Markdown → HTML（可选） |
