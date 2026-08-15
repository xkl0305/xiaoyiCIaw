# 输出规范

Phase 3 向用户展示业务数据前必读。工具调用见 [tool-calling-strategy.md](references/infra/tool-calling-strategy.md)；版本门槛见 [client-version.md](references/infra/client-version.md)。

## 决策（`isShowCard` + 系统提示词版本）

| 条件 | 输出形态 |
|------|----------|
| `isShowCard=false` | 纯 Markdown（按 guide「输出示例」） |
| `isShowCard=true` **且**系统提示词版本达标 | 1 句导语 + `displayA2UICardByPath` + 1 句总结（≤20 字） |
| `isShowCard=true` 但版本不达标 | 纯 Markdown（按 guide「输出示例」） |
| 系统提示词无版本信息 | 纯 Markdown |

版本门槛：`系统软件API版本号` ≥ 20（如果没有找到`系统软件API版本号`，`系统Rom版本` >= 20也可以） 且 `xiaoyiAppVersion` ≥ 11.7.6.200（从**当前系统提示词**读取，禁止读沙箱缓存）。

每次 `--extract` 的 stdout **必有** `isShowCard`：

- **`true`**：DSL 装填成功；stdout 含 `a2uiCard` + `isShowCard`；`query-meals` 另有 `simplify`；是否出卡还须在 Phase 3 判定版本
- **`false`**：无模板或装填失败；stdout 含完整业务 JSON + `isShowCard: false`

有 DSL 模板的工具：`query-meals`、`calculate-price`、`create-order`、`query-order`、`delivery-query-addresses`。

## Markdown 展示（`isShowCard=false`，或 `true` 但版本不达标）

按对应 guide「输出示例」正常输出 Markdown（可含表格、列表、图片）。

业务 JSON / `simplify` 用于推理与 Markdown 展示。

## GenUI 卡片展示（`isShowCard=true` 且版本达标）

**GenUI = MCP 业务展示载体**。Agent 回复只允许导语 + toolCall + 短总结；**禁止**与卡片重复的业务 Markdown。

回复固定三块，顺序不可变：

1. **导语** — 1 句；不写价格、品名等业务字段
2. **端侧展示** — toolCall `displayA2UICardByPath({"cardDSLPath":"<a2uiCard.cardDSLPath>"})`
3. **总结** — 1 句，≤20 字

**示例**：

```markdown
帮你查到了这几款餐品。

displayA2UICardByPath({"cardDSLPath":"/tmp/a2uidsl.txt"})

要加购吗？
```

**必须遵守**：

- **禁止**用 read/cat 打开 `a2uiCard.cardDSLPath`
- **禁止**表格、禁止 `![]()` / `<img>`、禁止裸写业务字段
- 版本不达标时**禁止**调 `displayA2UICardByPath`，即使 stdout 含 `a2uiCard`
- **禁止**向用户提及版本号、小艺版本、系统版本、GenUI 门槛、版本判定结果、`isShowCard`、展示路径切换原因
- 版本判定与出卡决策均为**静默内部步骤**；用户回复只含业务内容（卡片或 Markdown）

## stdout 字段分工

| 字段 | 何时有 | 用途 |
|------|--------|------|
| `isShowCard` | 每次 `--extract` | DSL 装填是否成功（非最终展示开关） |
| `a2uiCard` | 仅 `isShowCard=true` | 版本达标时触发展示 |
| `simplify` | 仅 `query-meals` 且 `isShowCard=true` | 菜单摘要；Markdown 兜底时可用 |
| 根级业务 JSON | `isShowCard=false`；或 `true` 时除 `query-meals` 外 | 上下文 / Markdown 数据源 |

## 展示前自检

1. `isShowCard` 是 true 还是 false？
2. 若 true：系统提示词版本是否达标？→ 达标出卡，不达标 Markdown
3. 出卡时总结是否 ≤20 字且无表格？
