# ai — 内容总结

AI 提炼节目核心内容与看点，帮你判断是否值得继续听下去。

## 工具列表

> **注意**：`contentSkills` 不走标准 MCP 同步接口，而是通过 xyos-api-service 的 **SSE 流式接口**（`/execute/stream`）直连内容生成服务。调用时必须使用流式请求格式。

| 意图 (intent) | 说明 | 典型场景 |
|--------------|------|---------|
| `全书总结` | 针对整张专辑生成全书总结 | "这本书讲了什么" |
| `本书大纲` | 生成专辑内容大纲 | "这本书的章节结构是什么" |
| `核心概要` | 针对单条声音生成核心概要 | "这集讲了什么" |
| `内容大纲` | 生成单条声音的内容大纲 | "这集的要点有哪些" |
| `价值亮点` | 提炼单条声音的价值亮点 | "这集有哪些精彩观点" |
| `名词解释` | 对内容中的专业名词进行解释 | "解释一下这个词" |

## 接口说明

**统一入口（SSE 流式）**

```
POST https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute/stream
```

- `toolName`: `contentSkills`
- 返回格式：`SseEmitter`（SSE 流式推送生成内容）

### 请求参数

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `intent` | String | 是 | 技能意图，见上方「意图」表 |
| `agent` | String | 否 | 代理标识，如 `xiaoya_copilot` |
| `agentScene` | String | 否 | 场景标识，如 `PersonalHelper`、`PlayPageTips` |
| `contextInfo` | Object | 否 | 上下文信息，详见下文 |

#### contextInfo 可选字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `trackId` | Long | 当前播放声音 ID，**所有意图必填**。即使是专辑类意图（全书总结、本书大纲），也需要传入当前播放的 trackId，服务端会通过 trackId 关联专辑上下文 |
| `deepThinkMode` | Boolean | 是否开启深度思考模式，默认 `false` |
| `albumId` | Long | 当前专辑 ID，专辑类意图（全书总结、本书大纲）建议传入 |

> **注意**：`trackId` 为所有意图的必填参数，缺失时会返回 `"参数错误！"`。即使是专辑类意图（全书总结、本书大纲），也需要传入当前播放的 trackId。

### 请求示例

```bash
curl -X POST "https://api.ximalaya.com/xyos-api-service/api/v1/skill/execute/stream" \
  -H "Authorization: Bearer $XIAOYA_API_KEY" \
  -H "Content-Type: application/json" \
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

### 响应说明

接口通过 SSE 流式推送生成内容。流式结束后服务端会自动关闭连接。

```
event: message
data: {"content":"《明朝那些事儿》主要讲述了..."}

event: message
data: {"content":"从朱元璋的出身讲起..."}

event: suggest
data: {"suggestions":["继续听下一集","查看作者其他作品"]}
```

## 工作流

1. 用户问"总结一下这集讲了什么" → 调用 `contentSkills`，`intent` 传 `核心概要`，`contextInfo.trackId` 传入当前声音 ID → 流式返回总结内容
2. 用户问"这本书讲了什么" → 调用 `contentSkills`，`intent` 传 `全书总结`，`contextInfo.trackId` 传入当前播放声音 ID，`contextInfo.albumId` 传入当前专辑 ID → 流式返回全书总结
3. 用户问"解释一下这个名词" → 调用 `contentSkills`，`intent` 传 `名词解释`，`contextInfo.trackId` 传入当前声音 ID → 流式返回名词解释

## 数据展示规范

- **内部标识不得暴露**：`contextInfo` 中的 `trackId`、`albumId` 等内部标识仅用于接口传参或内部上下文记忆，**面向用户展示时不得主动以纯文本形式暴露**。流式输出应直接呈现总结、大纲或解释内容本身
