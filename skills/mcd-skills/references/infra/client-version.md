# 客户端版本与 GenUI 门槛

GenUI 卡片展示除「有 ndjson 模板且装填成功（`isShowCard=true`）」外，还要求客户端版本同时满足：

| 字段 | 门槛 |
|------|------|
| `系统软件API版本号`或者`系统Rom版本` | ≥ 20 |
| 小艺 App 版本（`xiaoyiAppVersion`） | ≥ 11.7.6.200 |

## 版本来源

- **仅**从**当前系统提示词**读取上述两个字段
- 业务脚本**不**判定版本；`isShowCard` 只表示 DSL 是否装填成功

## Phase 3：出卡前判定（模型职责）

每次向用户展示有模板工具的数据前：

1. 读 stdout 的 `isShowCard`
2. 若 `isShowCard=true`，从**当前系统提示词**读取版本并判定是否同时满足门槛
3. 展示分流：

| 条件 | 输出 |
|------|------|
| `isShowCard=false` | guide Markdown |
| `isShowCard=true` 且版本达标 | 导语 + `displayA2UICardByPath` + 总结≤20 字 |
| `isShowCard=true` 但版本不达标 | guide Markdown（**禁止**调 `displayA2UICardByPath`） |
| 系统提示词无版本信息 | 视为不达标 → guide Markdown |

版本判定在**出卡时**执行，每轮读取系统提示词，不依赖缓存。

## 禁止向用户暴露（强制）
版本判定是**静默内部步骤**，与用户可见回复完全隔离：
1. **禁止**在回复中写出 `系统软件API版本号`、`系统Rom版本`、`xiaoyiAppVersion` 或其具体数值
2. **禁止**说明「版本不达标」「不满足门槛」「无法出卡」「改用 Markdown」等判定结论
4. 版本不达标时：**直接**按 guide 输出业务 Markdown，语气与正常查询一致，不暴露回退原因
5. 版本达标时：**直接**导语 + `displayA2UICardByPath` + 总结，不提及版本或卡片技术细节
用户只需看到业务结果，不需要知道背后走了卡片还是 Markdown 路径。

详见 [output.md](../../output.md)。
