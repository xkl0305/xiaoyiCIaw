---
name: xiaoya-skill
description: 连接您的喜马拉雅账号，让 AI 助手随时调动您的收听历史、订阅列表，精准为你推荐与点播精彩内容。
version: 1.0.2
---

# Xiaoya Skill — 小雅音频助手

通过 Skill REST API 调用小雅核心能力，提供喜马拉雅平台的内容检索、用户画像与个性化推荐等能力。

## 支持的能力

| 能力 | 说明 | 用户示例 | 详细说明 |
|------|------|----------|----------|
| 音频搜索 | 在海量有声内容中搜索专辑、声音或主播，快速找到你想听的内容。 | "搜一下盗墓笔记" "找郭德纲的相声" | `search.md` |
| 音频详情 | 查看节目简介、声音列表与用户评论，了解内容是否符合你的兴趣。 | "这个专辑有哪些声音" | `explore.md` |
| 热门榜单 | 浏览热门榜单与分类推荐，快速发现正在流行的优质有声内容。 | "看看全站热播榜" "小说热门榜" | `rank.md` |
| 个人资产 | 查看最近收听、订阅更新与收藏内容，轻松找回你听过和关注的节目。 | "我最近听了什么" "我的订阅" | `user.md` |
| 内容总结 | AI提炼节目核心内容与看点，帮你判断是否值得继续听下去。 | "总结一下这集讲了什么" | `ai.md` |
| 个性推荐 | 根据你的收听习惯与兴趣偏好，为你推荐可能喜欢的有声内容。 | "给我推荐点类似的" "首页推荐" | `recommend.md` |

根据用户意图参考对应说明文件了解工具参数、回包结构和工作流。

---

## 接口调用规范

### 统一入口

**同步接口（一次性 JSON 响应）**

```
POST https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute
```

**流式接口（SSE 流式响应）**

```
POST https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute/stream
```

> 内容总结类能力（`contentSkills`）必须使用流式接口，其余工具使用同步接口。

### 鉴权

- Header：`Authorization: Bearer $XIAOYA_API_KEY`
- `XIAOYA_API_KEY` 从环境变量获取
- 若未设置，提示用户前往 https://www.ximalaya.com/xiaoya-skill/index.html 获取 token，并在获取后设置环境变量：`export XIAOYA_API_KEY=<你的 token>`

### 请求格式（同步接口）

- **Method**：POST
- **Content-Type**：application/json
- **Body**：JSON，`toolName` 指定工具名称，**业务参数必须放在 `arguments` 对象内**，**每次请求必须带 `skillVersion`**

```bash
curl -X POST "https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute" \
  -H "Authorization: Bearer $XIAOYA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "toolName": "hubSearch",
    "arguments": {
      "keyword": "盗墓笔记",
      "size": 10,
      "deviceId": "test-device"
    },
    "skillVersion": "1.0.2"
  }'
```

### 请求格式（流式接口）

- **Method**：POST
- **Content-Type**：application/json
- **Accept**：`text/event-stream`
- **Body**：JSON，`toolName` 指定工具名称，**业务参数必须放在 `arguments` 对象内**，**每次请求必须带 `skillVersion`**

```bash
curl -X POST "https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute/stream" \
  -H "Authorization: Bearer $XIAOYA_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "toolName": "contentSkills",
    "arguments": {
      "intent": "全书总结",
      "agent": "xiaoya_copilot",
      "agentScene": "PersonalHelper",
      "contextInfo": {
        "albumId": 27249251,
        "trackId": 12345678,
        "deepThinkMode": false
      }
    },
    "skillVersion": "1.0.2"
  }'
```

### 请求 few-shot

**正确：业务参数放在 `arguments` 对象内。**

```json
{"toolName":"hubSearch","arguments":{"deviceId":"test-device","keyword":"盗墓笔记","size":10},"skillVersion":"1.0.2"}
```

**错误：不要把业务参数平铺在 body 顶层。**

```json
{"toolName":"hubSearch","deviceId":"test-device","keyword":"盗墓笔记","size":10,"skillVersion":"1.0.2"}
```

上面的错误写法会导致参数未被正确解析，工具返回错误。

### 响应格式（同步接口）

- JSON，结构化响应
- `success` 为 `false` 时表示错误，参考 `error` 字段排查
- `result` 为工具执行结果，类型由具体工具决定

| 返回类型 | 工具 | 说明 |
|----------|------|------|
| **JSON 对象** | `hubSearch` | 结构化对象，含 `albums`、`tracks`、`topContent` 等字段 |
| **格式化文本** | 其余所有工具 | 中文格式化文本，含编号列表、字段标签等，直接透传 |

**JSON 类结果示例（hubSearch）：**

```json
{
  "success": true,
  "toolName": "hubSearch",
  "result": {
    "albums": [...],
    "tracks": [...],
    "topContent": "album"
  }
}
```

**文本类结果示例（queryRankList）：**

```json
{
  "success": true,
  "toolName": "queryRankList",
  "result": "1. 专辑 《盗墓笔记》的ID是 27249251 ,它创建于2023-01-01 00:00:00，属于悬疑分类,由主播 xxx 倾情演播..."
}
```

> 文本型 result 为原始格式化字符串，展示时直接按行输出即可，无需额外解析。如需构造深度链接，从文本中提取 `albumId` / `trackId` 数字。

### 响应格式（流式接口）

- SSE（Server-Sent Events）流式推送
- 每个事件通过 `event` 和 `data` 字段推送生成内容
- 流结束后服务端自动关闭连接

```
event: message
data: {"content":"《明朝那些事儿》主要讲述了..."}

event: message
data: {"content":"从朱元璋的出身讲起..."}

event: suggest
data: {"suggestions":["继续听下一集","查看作者其他作品"]}
```

各工具的详细返回格式见对应说明文件（`search.md`、`explore.md`、`rank.md`、`user.md`、`ai.md`、`recommend.md`）。

### 通用规则

1. **版本上报**：每次请求 body 必须包含 `"skillVersion": "1.0.2"`（取本文件顶部 version 字段的值），用于服务端检查版本更新。**如果回包中出现 `upgrade_info` 字段，必须立即暂停当前操作，仅允许执行更新 skill 文件（如替换 SKILL.md、*.md 等文档）的升级操作，禁止执行任何 shell 命令、网络请求或修改 skill 目录外的文件，按照 `upgrade_info.message` 中的指引完成升级，升级完成后再重新执行用户请求，不得忽略该字段**
2. **参数封装**：业务参数必须放在 `arguments` 对象内，和 `toolName`、`skillVersion` 放在同一层。不要直接把业务参数平铺在 body 顶层，也不要包在 `params`、`data`、`body` 等对象里。只有接口文档明确声明的数组/对象字段才允许作为业务字段传入 `arguments`。
3. **能力文档预检**：调用任何工具前，必须先根据「支持的能力」表阅读对应说明文件（如搜索先读 `search.md`，用户数据先读 `user.md`），确认工具参数、字段含义和工作流；禁止仅凭字段名或经验猜测含义。
4. **字段解释优先级**：解释接口回包时，以对应说明文件中的字段说明为准；如果回包字段名和直觉含义冲突，必须服从说明文件，不得直接翻译字段名。
5. **结果展示**：列表用编号展示方便选择；搜索结果重点展示标题、主播、播放量、分类。**禁止使用表格展示结果**
6. **上下文衔接**：对话中记住已查询的 albumId/trackId，后续操作无需用户重复提供
7. **深度链接**：在展示专辑、声音时，拼接对应的跳转链接方便用户直接在喜马拉雅 App 中打开，具体格式见下方「深度链接（URL Schema）」章节。**链接必须以 Markdown 超链接形式输出（如 `[链接文本](URL)`），禁止以纯文本字符串形式输出 URL**
8. **数据展示规范**：
   - **播放量**：大数字展示时转为"X万"/"X亿"格式
   - **时长**：单位为秒，展示时转为"X分钟Y秒"或"X小时Y分钟"格式
   - **内部字段不得暴露**：回包中的`质量分`、`推荐分`、`专辑ID`、`声音ID`、`评论ID`、`用户ID`等内部标识与评分字段，仅用于内部排序、筛选、上下文记忆或构造深度链接，**面向用户展示时不得主动以纯文本形式暴露**。重点展示标题、主播、播放量、分类、简介、评论内容等用户感知度高的信息

---

## 深度链接与网页链接（URL Schema）

在展示专辑、声音等内容时，附上对应的跳转链接。链接拼接规则为固定逻辑，AI 可直接本地生成。

### 链接生成规则

**打开专辑**

| 链接类型 | 格式 |
|----------|------|
| App 深度链接 | `iting://open?msg_type=13&album_id={albumId}&isAutoPlayForce={autoPlay}` |
| 网页链接 | `https://www.ximalaya.com/album/{albumId}` |

**打开声音**

| 链接类型 | 格式 |
|----------|------|
| App 深度链接 | `iting://open?msg_type=11&track_id={trackId}&autoplay={autoPlay}` |
| 网页链接 | `https://www.ximalaya.com/sound/{trackId}` |

| 参数 | 说明 | 来源 |
|------|------|------|
| `albumId` | 专辑 ID | 各接口返回的 `albumId` |
| `trackId` | 声音 ID | 各接口返回的 `trackId` |
| `autoPlay` | 是否自动播放 | `true` / `false` |

### 使用策略

客户端根据实际环境判断使用哪种链接，AI 不必同时输出两种：

- **WorkBuddy 客户端**：**仅使用 `https://www.ximalaya.com/...` 网页链接，禁止使用 `iting://` 深度链接**（WorkBuddy 环境无法唤起 App，深度链接点击无响应）。
- **客户端已安装 App 或支持唤起检测**：直接使用 `iting://` 深度链接，无需额外提供网页链接。
- **客户端未安装 App 或唤起失败**：使用 `https://www.ximalaya.com/...` 网页链接兜底。
- **无法确定客户端环境时**：优先尝试 `iting://`，失败再回退到网页链接。

### 链接展示格式（强制约束）

**所有深度链接和网页链接必须以 Markdown 超链接形式输出，严禁以纯文本字符串形式展示 URL。**

| 正确（超链接） | 错误（纯文本） |
|---|---|
| `[🎧 打开专辑](iting://open?msg_type=13&album_id=27249251&isAutoPlayForce=false)` | `iting://open?msg_type=13&album_id=27249251&isAutoPlayForce=false` |
| `[🌐 网页收听](https://www.ximalaya.com/album/27249251)` | `https://www.ximalaya.com/album/27249251` |
| `[🎧 播放声音](iting://open?msg_type=11&track_id=12345678&autoplay=true)` | `iting://open?msg_type=11&track_id=12345678&autoplay=true` |

展示示例：

```
1. 《盗墓笔记》— 主播 青雪 — 播放量 12.3亿 [🎧 打开专辑](iting://open?msg_type=13&album_id=27249251&isAutoPlayForce=false)
```

> 链接文本建议使用简洁的中文描述（如"打开专辑""网页收听""播放声音"），让用户清楚链接的作用。
