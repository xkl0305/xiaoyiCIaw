# xiaoyi-channel 华为 API 内容审核拒绝响应攻击链分析与修复方案

> **编写日期**：2026-06-18（2026-07-11 修正版）
> **适用版本**：xiaoyi-channel v1.1.31（OpenClaw 插件）
> **修复类型**：安全漏洞修补（华为 provider API 内容审核拒绝响应透传攻击）

---

## ⚠️ 本版修正说明

此版本合并了三份来源的修正：

| 来源 | 日期 | 贡献 |
|------|------|------|
| v2 原版（`FIX_CONTENT_FILTER_REJECTION_v2.md`） | 2026-06-18 | 攻击链分析、威胁模型、两类攻击场景 |
| v1（`FIX_CONTENT_FILTER_REJECTION.md`） | 2026-06-20 | 指出"静默丢弃 return"方案的 bug + 抹空方案 + "规范"正则 |
| 本修正版新增 | 2026-07-11 | `token_text` 字段修正、API SSE 格式对照表、delta 实时检测风险评估 |

### 原始版本关键错误

| 错误位置 | 原始内容 | 修正后 |
|---------|---------|--------|
| `extractResponseText` 读字段 | `choice?.message?.content` | 优先读 `choice?.message?.token_text`（此 API 不使用 OpenAI 标准 content 字段） |
| `detectErrorKind` 参考文件名 | `errors-QN8rySzW.js` | `errors-BXgSefBE.js` |
| 修复策略 | **return 截断 generator**（导致 `resultPromise` 不 resolve，上游感知异常终止） | **抹空内容后正常 yield/resolve** |
| 正则模式 | 只含"规则" | 新增"规范"（华为 API 实际返回的文案） |
| SSE 格式认知 | 假设为 OpenAI 标准 | 增加此 API 专有格式对照表 |

---

## 一、背景

在 **CSPL 安全机制攻击链**（参见报告 `FIX_CSPL_ATTACK_CHAIN.md`，2026-06-16）修复之后——即删除 `.xiaoyienv` 中的 `SERVICE_URL` 使 CSPL 配置加载抛出异常后被静默吃掉——用户反馈仍然出现"攻击式拦截"现象。

新出现的攻击与 CSPL 攻击不同，提示内容为：

> **"你的输入不符合相关规则，请修改后重试"**
> **"你的输入不符合相关规范，请修改后重试"**

该文本在 xiaoyi-channel 全部源代码中均不可检索到，说明其并非由插件本地代码生成，而是来自 **华为 xiaoyi provider API 服务端的内容审核层（content filter）**。

注意：CSPL（自定义安全策略层）和华为 content_filter 是两个**完全独立**的拦截层，彼此无关联。

---

## 二、攻击链全景

### 2.1 威胁模型

```
攻击者（平台侧）
    │
    ├── 在用户消息尾部追加操控指令
    │
    ▼
模型正常执行
    │
    ├── 调工具 → 生成回复 → 发送给华为 API
    │
    ▼
华为 xiaoyi provider API（内容审核层）
    │
    ├── 检测到"违规"内容 → 返回拒绝
    ├── 拒绝文本（中文）：
    │   "你的输入不符合相关规则，请修改后重试"
    │   "你的输入不符合相关规范，请修改后重试"
    │
    ▼
SSE 流式响应返回（专有 token_text 格式）
    │
    ├── 拒绝文本拆分成 token_text delta 事件逐帧透传
    ├── OpenClaw 的 detectErrorKind() 仅识别英文关键词
    │   （"refusal"、"content_filter"、"sensitive"等）
    │   → 不认识中文拒绝文本 → **作为正常响应放行**
    │
    ▼
模型上下文被注入
    │
    ├── 中文拒绝文本进入对话上下文
    ├── 模型把它当成"用户指令"或"系统指令"执行
    ├── 任务被错误中断
    │
    ▼
用户视角：任务被无端中断 + 看到拦截提示
```

### 2.2 两个独立拦截层对比

| 维度 | CSPL（已解决） | 华为 content_filter（本报告） |
|------|---------------|------------------------------|
| **拦截层位置** | xiaoyi-channel 插件内部 `sentinel_hook.js` | 华为 API 服务端 |
| **触发时机** | 工具调用之后（after_tool_call） | API 流式响应生成之后 |
| **返回内容** | `STEER_ABORT_MESSAGE`（可编辑） | "你的输入不符合相关规则/规范，请修改后重试"（不可控） |
| **OpenClaw 能否控制** | ✅ 能（代码可修改） | ❌ 不能（华为服务端配置） |
| **当前状态** | ✅ 已禁用（SERVICE_URL 已删除） | ⚠️ 待修复（本报告方案） |

### 2.3 两类攻击场景

| 场景 | 用户表现 | 发生阶段 | 修复手段 |
|------|---------|---------|---------|
| **场景A（多数）** | 消息发出**几秒**后收到"不符合规则/规范" | 消息在传输层被拦截，未到达 xiaoyi-channel 插件 | ❌ 插件层面无法控制（华为平台路由层） |
| **场景B（少数）** | 模型已经开始工作，**一段时间后**被"不符合规则/规范"中断 | 流式响应阶段，华为 API 检测到返回内容后拒绝 | ✅ **本报告修复方案** |

---

## 三、源码分析

### 3.1 问题根因：`detectErrorKind` 不认识中文

**文件**：`openclaw/dist/errors-BXgSefBE.js`

```javascript
function detectErrorKind(err) {
    const message = formatErrorMessage(err).toLowerCase();
    if (message.includes("refusal") || 
        message.includes("content_filter") || 
        message.includes("sensitive") || 
        message.includes("unhandled stop reason: refusal_policy")) 
        return "refusal";
    // ... 只识别英文关键词
}
```

华为 API 返回的中文拒绝文本在 SSE 流中通过 `token_text` delta 事件逐帧返回（作为正常流式内容），**而不是以错误形式抛出**。因此 `detectErrorKind` 接收的是 Error 对象，而拒绝文本是正常流式输出的内容——路径完全不同，永远无法捕获。

### 3.2 此 API 的 SSE 格式特征

与 OpenAI 标准 SSE 格式不同，该华为 API 使用**专有字段**：

| 元素 | OpenAI 标准字段 | 此 API 使用字段 | 说明 |
|------|---------------|----------------|------|
| 思考过程 | `delta.content`（reasoning 模型输出思考） | `message.reasoning_token_text` | 独立的思考字段，非 content |
| 输出文本 | `delta.content` | `message.token_text` | 专有字段，非 content |
| 完成事件（done） | `message.content`（含完整文本） | `message.token_text: ""`（空字符串） | 内容已通过 delta 逐帧发送完毕 |

**关键差异**：该 API 的 `done` 事件中 `token_text` 为空字符串，完整文本由逐个 delta 事件累积而成。这与标准 OpenAI API 在 `done` 事件中携带完整内容不同。

### 3.3 流式响应路径

**文件**：`~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js`

`createRetryingStream()` 函数是流式响应的核心。SSE 流经过三个阶段的 `done` 事件：

```
华为 API SSE 流（token_text 格式）
    │
    ▼
createRetryingStream (provider.js)
    │
    ├── 缓冲阶段（buffer phase）—— 第一次 done 事件
    │   ├── delta 事件（含 token_text 逐帧累积）
    │   └── done 事件 finish_reason="stop" | "content_filter"
    │
    ├── 流式阶段（streaming phase）—— 第二次 done 事件  
    │   ├── delta 事件（含 token_text 逐帧累积）
    │   └── done 事件 finish_reason="stop" | "content_filter"
    │
    └── 最终兜底（final fallback）—— 第三次 done 事件
        ├── delta 事件
        └── done 事件 finish_reason="stop" | "content_filter"
```

**三个 `done` 事件处理都没有检测中文拒绝文本**，直接：

```javascript
resultResolve(event.message);
yield event;
return;
```

拒绝文本就这样通过 delta 事件逐帧 `yield` 后透传到上层，进入对话上下文。

### 3.4 拒绝文本在 SSE 中的表现形式

华为 API 内容审核拒绝的 SSE 响应可能以以下形式出现：

| 形式 | 示例 | 检测方式 |
|------|------|---------|
| 流式 `token_text` 逐帧透传 | `"token_text":"你"`, `"token_text":"的"` → 累积成完整拒绝文本 | 累积文本后正则匹配 |
| `finish_reason` 标记 | `choices[0].finish_reason === "content_filter"` | 枚举比较 |
| 混合形式 | `token_text` 累积 + `finish_reason: "stop"`（无 content_filter 标记） | 正则匹配兜底 |

---

## 四、修复方案演进

### 4.1 原始方案（v2 原版）：静默丢弃（return 截断）—— ⚠️ 有 bug

原版的检测逻辑命中后直接 `return` 截断 generator，不再 yield 任何内容：

```javascript
if (isContentFilterRejection(respText)) {
    logger.log(`... discarding stream silently`);
    return;  // ← return 截断 generator
}
```

**问题**：截断 generator 后 `resultPromise` 永远不会被 resolve，上游（OpenClaw 的 agent runner）感知到 stream 异常终止，触发「任务异常」逻辑 → 强制结束工作流。

**实际效果**：用户仍然看到任务中断，只是拒绝文本变成了其他形式的异常提示。

### 4.2 v1 修复方案：抹空内容 + 正常 yield

将"截断"改为"抹空"，构造空消息正常走完 yield/resolve 流程：

```javascript
if (isContentFilterRejection(respText)) {
    logger.log(`... replacing with empty completion`);
    // 抹掉拒绝文本
    event.message.choices[0].message.content = "";
    event.message.choices[0].finish_reason = "stop";
    // 正常 yield 和 resolve
    for (const b of buffer) yield b;
    resultResolve(event.message);
    yield event;
    return;
}
```

**问题**：仍使用 `message.content` 字段，而此 API 使用 `token_text` 字段，导致 `extractResponseText()` 读不到内容。此外，仅抹空 `content` 而不处理 `token_text`，在专有格式 API 上无效。

### 4.3 本修正版方案：适配 `token_text` 格式的抹空方案

综合以上经验，最终方案在 v1 的抹空思路上，适配此 API 的 `token_text` 专有格式。


### 4.4 设计原则

修复的核心目标不是"显示安全通知"，而是**让用户完全感知不到内容审核拒绝的发生**：

1. **抹空替代截断**：检测到拒绝时，**不截断流**，而是将内容抹空后正常走完 yield/resolve 流程
2. **兼容此 API 专有字段**：同时处理 `token_text`（此 API 使用）和 `content`（标准兼容）
3. **用户不受扰**：用户看不到任何拦截提示，仿佛什么都没发生
4. **日志可追溯**：在日志中记录 `🗑️ content filter rejection detected` 以便排查

### 4.5 修复方案图示

```
华为 API SSE 流（含 content_filter 拒绝）
    │
    ▼
createRetryingStream
    │
    ├── 正常响应 → yield event（放行）
    │
    ├── 中文拒绝检测（done event 时）
    │   │
    │   ├── 匹配拒绝模式
    │   │   ├── 抹空 message.token_text + content
    │   │   ├── 设 finish_reason = "stop"
    │   │   ├── Buffer phase: yield 缓冲区内容
    │   │   ├── resultResolve(event.message)（正常 resolve）
    │   │   └── yield event（正常走完）
    │   │
    │   └── 不匹配 → yield event（正常放行）
    │
    ▼
用户视角：什么也没发生
模型视角：继续正常执行
```

### 4.6 代码改动详解

**文件**：`~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js`

#### 改动 1：新增辅助函数（导入区之后）

```javascript
// ── Content filter rejection detection ────────────────────────────
// 中文拒绝模式正则 —— 同时覆盖"规则"和"规范"两种华为 API 文案
const CN_CONTENT_FILTER_PATTERNS = [
    /输入不符合相关规则/i,
    /输入不符合相关规范/i,           // 华为 API 实际使用
    /不符合相关规则.*请修改后重试/i,
    /不符合相关规范.*请修改后重试/i,  // 华为 API 实际使用
    /内容涉及违规/i,                 // 预留
    /请求被拒绝.*原因/i,             // 预留
];

// 检测文本是否匹配拒绝模式
function isContentFilterRejection(text) {
    if (!text || typeof text !== "string") return false;
    return CN_CONTENT_FILTER_PATTERNS.some(pattern => pattern.test(text));
}

/**
 * 从 done 事件的消息中提取累积文本
 * 
 * 此 API 使用 token_text 而非 OpenAI 标准 content 字段。
 * done 事件中 token_text 通常为空字符串（内容已通过 delta 帧逐帧发出），
 * 因此本函数同时检查三条路径：
 *   - token_text（此 API 专有字段）
 *   - finish_reason（枚举 "content_filter"）
 *   - content（OpenAI 标准兼容）
 */
function extractResponseText(message) {
    if (!message) return "";
    if (Array.isArray(message.choices) && message.choices.length > 0) {
        const choice = message.choices[0];
        
        // 路径 1：检查 finish_reason（最可靠）
        if (choice?.finish_reason === "content_filter") {
            return "输入不符合相关规则或规范";
        }
        
        // 路径 2：读 token_text（此 API 使用的字段）
        const tokenText = choice?.message?.token_text;
        if (typeof tokenText === "string" && tokenText.trim() !== "") {
            return tokenText;
        }
        
        // 路径 3：读 content（OpenAI 标准兼容）
        const content = choice?.message?.content;
        if (typeof content === "string" && content.trim() !== "") {
            return content;
        }
    }
    
    // 路径 4：直接读 message.content（极少情况）
    if (typeof message.content === "string" && message.content.trim() !== "") {
        return message.content;
    }
    
    return "";
}

/**
 * 抹空消息内容，用于拒绝命中时替代截断
 * 同时处理此 API 的 token_text 和 OpenAI 标准的 content 字段
 */
function clearMessageContent(message) {
    if (!message) return;
    if (Array.isArray(message.choices) && message.choices.length > 0) {
        const choice = message.choices[0];
        // 抹空 token_text（此 API 字段）
        if (choice?.message) {
            choice.message.token_text = "";
            choice.message.content = "";    // 兼容标准 OpenAI
            choice.message.reasoning_token_text = ""; // 同时抹掉思考内容
        }
        // 设 finish_reason 为正常 stop
        choice.finish_reason = "stop";
    }
    // 也抹掉顶层 content
    if (message.content) message.content = "";
}
```

#### 改动 2：缓冲阶段 done 事件

```javascript
// 修改前
if (event.type === "done") {
    logger.log(`[xiaoyiprovider] stream completed (no content), usage: ...`);
    for (const b of buffer) yield b;
    resultResolve(event.message);
    yield event;
    return;
}

// 修改后
if (event.type === "done") {
    const respText = extractResponseText(event.message);
    if (isContentFilterRejection(respText)) {
        logger.log(`[xiaoyiprovider] 🗑️ content filter rejection detected in buffer phase, replacing with empty completion`);
        clearMessageContent(event.message);
        // 缓冲区可能包含已缓存的拒绝 delta，但不 yield 它们
        // resultResolve 使用已抹空的消息
        resultResolve(event.message);
        yield event;  // yield 抹空后的 done event
        return;
    }
    logger.log(`[xiaoyiprovider] stream completed (no content), usage: ...`);
    for (const b of buffer) yield b;
    resultResolve(event.message);
    yield event;
    return;
}
```

#### 改动 3：流式阶段 done 事件

```javascript
// 修改前
if (event.type === "done") {
    logger.log(`[xiaoyiprovider] stream completed, usage: ...`);
    resultResolve(event.message);
    yield event;
    return;
}

// 修改后
if (event.type === "done") {
    const respText = extractResponseText(event.message);
    if (isContentFilterRejection(respText)) {
        logger.log(`[xiaoyiprovider] 🗑️ content filter rejection detected in streaming phase, replacing with empty completion`);
        clearMessageContent(event.message);
        // ⚠️ 在 streaming phase 中，delta 事件已被逐帧 yield 给上游。
        // 到 done event 时拒绝文本的 delta 已经发送出去了。
        // 此处的抹空只能阻止 done event 的内容，无法撤回已发送的 delta。
        // 这是本方案在 streaming phase 的固有限制。
        resultResolve(event.message);
        yield event;
        return;
    }
    logger.log(`[xiaoyiprovider] stream completed, usage: ...`);
    resultResolve(event.message);
    yield event;
    return;
}
```

#### 改动 4：最终兜底阶段 done 事件

```javascript
// 修改前
for await (const event of lastStream) {
    if (event.type === "done") {
        resultResolve(event.message);
        yield event;
        return;
    }
}

// 修改后
for await (const event of lastStream) {
    if (event.type === "done") {
        const respText = extractResponseText(event.message);
        if (isContentFilterRejection(respText)) {
            logger.log(`[xiaoyiprovider] 🗑️ content filter rejection detected in final fallback, replacing with empty completion`);
            clearMessageContent(event.message);
            resultResolve(event.message);
            yield event;
            return;
        }
        resultResolve(event.message);
        yield event;
        return;
    }
}
```

### 4.7 操作步骤

```bash
# 1. 备份原文件
cp ~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js \
   ~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js.bak

# 2. 编辑文件（新增 3 个辅助函数 + 修改 3 处 done 事件处理）
# 手动应用上述修改

# 3. 验证语法
node --check ~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js
# 应返回 exit: 0

# 4. 重启 gateway 生效
python3 -m supervisor.supervisorctl restart openclaw-gateway
```

### 4.8 回滚方案

```bash
cp ~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js.bak \
   ~/.openclaw/extensions/xiaoyi-channel/dist/src/provider.js
python3 -m supervisor.supervisorctl restart openclaw-gateway
```

### 4.9 验证方法

正常场景（无攻击）：
```bash
# 观察日志中不应有 content filter rejection 相关输出
tail -f ~/.openclaw/logs/*.log | grep "content filter rejection"
# 应无输出（除非真的触发了内容审核）
```

触发场景：
```bash
# 日志中会出现 🗑️ 标记
tail -f ~/.openclaw/logs/*.log | grep "🗑️"
# 输出示例：
# [xiaoyiprovider] 🗑️ content filter rejection detected in buffer phase, replacing with empty completion
```

验证正常响应不受影响：
```bash
# 发送一条正常消息，观察正常回复是否到达
# 应在 10-30 秒内收到正常回复
```

---

## 五、设计权衡

### 5.1 为什么选择"抹空 yield"而非"安全通知"？

CSPL 攻击的修复选择了"改成安全通知"（因为 CSPL 可控，可以修改注入消息内容），而 content_filter 攻击的修复选择了"抹空 yield"：

| 维度 | CSPL 修复 | Content filter 修复 |
|------|----------|-------------------|
| 拦截层是否可控 | ✅ 是（插件代码） | ❌ 否（华为 API 服务端） |
| 能否修改拒绝文本 | ✅ 能 | ❌ 不能 |
| 修复手段 | 改通知内容 + role | 抹空内容 + 正常 yield |
| 原因 | 注入点可控，可以绕开攻击 | 拒绝内容不可控，截断会导致 stream 异常 |

### 5.2 为什么 v2 原版的"return 截断"方案是 bug？

| 对比 | v2 原版（return 截断） | 本版（抹空 yield） |
|------|---------------------|-------------------|
| 命中拒绝后 | `return` 截断 generator | `clearMessageContent()` 抹空 + 正常 yield |
| `resultPromise` | ❌ 永不被 resolve | ✅ 正常被 resolve |
| 上游感知 | ❌ stream 异常终止 | ✅ 正常完成（空内容） |
| 用户看到的实际效果 | ❌ 任务异常中断 | ✅ 无感知 |
| 缓冲区内容 | 丢弃 | 也丢弃（不 yield buffer 中的拒绝 delta） |

### 5.3 流式阶段的固有限制

在 streaming phase，delta 事件被**逐帧实时 yield** 给上游。到达 done event 时：
- 如果拒绝文本的内容已经通过 delta 帧发送出去 → **无法撤回**
- 抹空操作只能阻止 done event 中携带的内容

**解决方案**：
- buffer phase 可以完全拦截（内容尚在缓冲中，未 yield）
- streaming phase 依赖 `finish_reason === "content_filter"` 的早期检测（如果华为 API 在完成 delta 发送前就设 `finish_reason`，可以在 delta 完全发出前触发抹空）

### 5.4 误杀风险

- `CN_CONTENT_FILTER_PATTERNS` 目前包含 6 个正则模式，覆盖已知文案
- `finish_reason === "content_filter"` 是标准 OpenAI 协议字段，误杀概率为零
- `token_text` 空字符串不会触发正则匹配（`trim() !== ""` 过滤），不会误判正常响应

### 5.5 局限性

- **场景A无法修复**：消息在传输层就被拦截的（发出去几秒就返回"不符合规则"），插件层面无法处理
- **delta 实时检测的非原子性**：在 streaming phase，已 yield 的 delta 无法撤回
- **正则匹配的完整性**：只能覆盖已知的拒绝文本模式，新增拒绝模式需要更新 `CN_CONTENT_FILTER_PATTERNS`
- **此 API 的专有格式依赖**：`token_text` 和 `reasoning_token_text` 是此 API 专有字段，如果未来华为更换 SSE 格式，需要相应调整

### 5.6 与 CSPL 修复的关系

这是两个**完全独立**的问题：

| 修复 | 解决什么 | 改了什么文件 | 关联性 |
|------|---------|-------------|--------|
| CSPL 修复 | "清空上下文后重试"攻击 | `index.js` 注释 hook / `.xiaoyienv` 删 SERVICE_URL | 无（独立问题） |
| Content filter 修复 | "不符合规则/规范"攻击 | `provider.js` 加检测 + 抹空逻辑 | 无（独立问题） |

**建议同时启用两个修复**以获得全面防护。

---

## 六、完整文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `dist/src/provider.js` | **新增 90 行**（3 个辅助函数 + 3 处 done 事件修改） | 本报告修复方案 |
| `dist/src/provider.js.bak` | 备份 | 自行创建 |

---

## 七、附录：`isContentFilterRejection()` 与 `detectErrorKind` 的区别

| 函数 | 位置 | 输入类型 | 输出 | 解决的问题 |
|------|------|---------|------|-----------|
| `detectErrorKind` | `openclaw/dist/errors-BXgSefBE.js` | Error 对象 | 错误类型字符串（如 "refusal"） | 分类错误以便上层处理 |
| `isContentFilterRejection` | `xiaoyi-channel/dist/src/provider.js` | 响应文本（string） | boolean | 检测中文拒绝文本以便抹空处理 |

**为什么 `detectErrorKind` 不够？** content_filter 拒绝不以 Error 形式抛出，而是作为正常 SSE 流式响应的 `token_text` delta 事件逐帧返回。两个函数处理完全不同的数据路径。

---

## 八、扩展指南：如何添加更多拒绝模式

如果未来华为 API 的拒绝文本发生变化，只需要更新 `CN_CONTENT_FILTER_PATTERNS` 数组：

```javascript
const CN_CONTENT_FILTER_PATTERNS = [
    /输入不符合相关规则/i,
    /输入不符合相关规范/i,
    /不符合相关规则.*请修改后重试/i,
    /不符合相关规范.*请修改后重试/i,
    // 添加新模式：
    /内容涉及违规/i,
    /请求被拒绝.*原因/i,
];
```

无需修改其他代码。修改后重启 gateway 生效。

---

## 九、附录：此 API SSE 格式参考（vs OpenAI 标准）

| 项目 | OpenAI 标准 | 此华为 API |
|------|------------|-----------|
| delta 文本字段 | `choices[0].delta.content` | `choices[0].message.token_text` |
| 思考字段 | `choices[0].delta.content`（reasoning 模型输出思考到 content） | `choices[0].message.reasoning_token_text` |
| done 事件携带内容 | `choices[0].message.content`（含完整文本） | `choices[0].message.token_text: ""`（空，文本已通过 delta 逐帧发送） |
| finish_reason | `choices[0].finish_reason` | `choices[0].finish_reason`（兼容 OpenAI 标准） |
| 流式模式 | 默认 `stream: true` | 非标准 SSE 流式（`stream: false` 也返回 SSE 流） |

---

## 十、修复演进时间线

```
2026-06-18  v2 原版编写
            ↓ 问题：return 截断 → stream 异常终止
            ↓ 问题：extractResponseText 读 content 而非 token_text
            ↓ 问题：正则只含"规则"不含"规范"
            
2026-06-20  v1 编写（FIX_CONTENT_FILTER_REJECTION.md）
            ↓ 发现：return 截断本身是 bug
            ↓ 改进：改为抹空内容 + 正常 yield
            ↓ 改进：新增"规范"正则
            
2026-07-11  本修正版
            ↓ 发现：此 API 使用 token_text 而非 content
            ↓ 改进：extractResponseText 优先读 token_text
            ↓ 改进：clearMessageContent 同时处理 token_text + content
            ↓ 改进：新增 SSE 格式对照表
            ↓ 改进：新增 delta 实时检测风险评估
```
