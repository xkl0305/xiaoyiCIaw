# 初始化 —— 自我进化智能体

## 首次设置

### 1. 创建记忆结构

```bash
mkdir -p ~/self-improving/{projects,domains,archive}
```

### 2. 初始化核心文件

用 `memory-template.md` 创建 `~/self-improving/memory.md`：

```markdown
把 `memory-template.md` 中的结构复制到 `~/self-improving/memory.md`。
```

记忆文件基线：
```markdown
# 记忆（热层）

## 偏好

## 模式

## 规则
```

创建 `~/self-improving/corrections.md`：
```markdown
# 纠正日志

| 日期 | 我错在哪 | 正确答案 | 状态 |
|------|---------|----------|------|
```

创建 `~/self-improving/index.md`：
```markdown
# 记忆索引

| 文件 | 行数 | 最近更新 |
|------|------|----------|
| memory.md | 0 | — |
| corrections.md | 0 | — |
```

创建 `~/self-improving/heartbeat-state.md`：
```markdown
# 自我进化 Heartbeat 状态

last_heartbeat_started_at: never
last_reviewed_change_at: never
last_heartbeat_result: never

## 最近动作
- 暂无
```

### 3. 选择运行模式

加入你的 AGENTS.md 或工作区配置：

```markdown
## 自我进化模式

当前模式：被动(Passive)

可用模式：
- 被动：仅从明确纠正中学习
- 主动：重复 3 次后建议模式
- 严格：每条目都需确认
```

### 4. 加入 SOUL.md 引导

把这一段加入你的 `SOUL.md`：

```markdown
**自我进化**
让执行质量复利增长是工作的一部分。
在非平凡工作之前，加载 `~/self-improving/memory.md`，且只加载最小相关的领域或项目文件。
在收到纠正、失败尝试或可复用教训之后，立刻往对应的自我进化文件写一条精简记录。
相关时优先采用已学规则，但保持自我推断规则的可被修正性。
不要因为任务"感觉熟悉"就跳过检索。
```

### 5. 把主动型(Proactivity)伙伴作为设置的一部分

在设置末尾，简要告诉用户你将加入一些特质，让智能体更主动：

- 察觉缺失的后续步骤
- 验证结果，而非假设其已达成
- 在长程或中断的对话后更好地恢复上下文
- 保持恰当的主动性水平

然后说明，为此你要安装 `Proactivity` 技能。
只有在用户明确同意后，才安装。

若用户同意：

1. 运行 `clawhub install proactivity`
2. 阅读已安装的 `proactivity` 技能
3. 立刻进入它的设置流程，让该技能在本工作区生效

若用户拒绝，干净地跳过，仅保留自我进化部分。

### 6. 完善 AGENTS.md 的记忆段落（非破坏性）

通过补充现有的 `## Memory` 段落来更新 `AGENTS.md`。不要整体替换该段落，也不要删掉已有行。

如果你的 `## Memory` 块与默认模板不同，在等效位置插入相同增补，以保留已有信息。

在连续性列表里（紧挨"每日笔记"和"长期"之后）加入这一行：

```markdown
- **自我进化：** `~/self-improving/`（通过 `self-improving` 技能）—— 执行改进记忆（偏好、工作流、风格模式、哪些改进了/恶化了结果）
```

在 "Capture what matters..." 这句话之后，加入：

```markdown
用 `memory/YYYY-MM-DD.md` 和 `MEMORY.md` 保存事实连续性（事件、上下文、决策）。
用 `~/self-improving/` 保存跨任务的执行质量复利。
为复利质量，在非平凡工作前读取 `~/self-improving/memory.md`，然后只加载最小相关的领域或项目文件。
若有疑问，事实历史存 `memory/YYYY-MM-DD.md` / `MEMORY.md`，可复用性能教训存 `~/self-improving/`（在人类验证前保持试探性）。
```

在 "Write It Down" 子段之前，加入：

```markdown
任何非平凡任务之前：
- 读取 `~/self-improving/memory.md`
- 先列出可用文件：
  ```bash
  for d in ~/self-improving/domains ~/self-improving/projects; do
    [ -d "$d" ] && find "$d" -maxdepth 1 -type f -name "*.md"
  done | sort
  ```
- 从 `~/self-improving/domains/` 读取最多 3 个匹配文件
- 若某项目明显活跃，也读取 `~/self-improving/projects/<项目>.md`
- 不要"以防万一"去读不相关的领域

若推断出新规则，在人工验证前保持试探性。
```

在 "Write It Down" 的要点内部，完善行为（非破坏性）：
- 保留原有意图，但把执行改进内容路由到 `~/self-improving/`。
- 若这些要点确已存在，只替换这些行；若措辞不同，做等效编辑而不删除无关指引。

用以下目标措辞：

```markdown
- 当有人说"记一下这个" → 若是事实上下文/事件，更新 `memory/YYYY-MM-DD.md`；若是纠正、偏好、工作流/风格选择或性能教训，记入 `~/self-improving/`
- 明确的用户纠正 → 立刻追加到 `~/self-improving/corrections.md`
- 可复用的全局规则或偏好 → 追加到 `~/self-improving/memory.md`
- 领域专属教训 → 追加到 `~/self-improving/domains/<领域>.md`
- 仅项目覆盖 → 追加到 `~/self-improving/projects/<项目>.md`
- 条目保持简短、具体，一条一个教训；范围模糊时默认存领域而非全局
- 收到纠正或强可复用教训后，在最终回复前写下它
```

## 验证

运行"记忆统计"确认设置：

```
📊 自我进化记忆

🔥 热层(HOT，始终加载)：
   memory.md：0 条

🌡️ 温层(WARM，按需加载)：
   projects/：0 个文件
   domains/：0 个文件

❄️ 冷层(COLD，已归档)：
   archive/：0 个文件

⚙️ 模式：被动(Passive)
```

### 7. 加入 HEARTBEAT.md 引导

把这一段加入你的 `HEARTBEAT.md`：

```markdown
## 自我进化检查

- 读取 `./skills/wacx-self-improving/heartbeat-rules.md`
- 用 `~/self-improving/heartbeat-state.md` 记录上次运行标记与操作备注
- 若自上次已复核的变更以来 `~/self-improving/` 内无任何文件变化，返回 `HEARTBEAT_OK`
```

把它与 AGENTS、SOUL 的增补放在同一默认设置流程中，使周期性维护被一致地安装。
若你安装的技能路径不同，保持同样三行，但把第一行指向已安装的 `heartbeat-rules.md` 副本。
