# 记忆模板

首次使用时，把此结构复制到 `~/self-improving/memory.md`。

```markdown
# 自我进化记忆

## 已确认偏好
<!-- 用户确认的模式，永不衰变 -->

## 活跃模式
<!-- 观察到 3+ 次的模式，会衰变 -->

## 近期（最近 7 天）
<!-- 待确认的新纠正 -->
```

## 初始目录结构

首次激活时创建：

```bash
mkdir -p ~/self-improving/{projects,domains,archive}
touch ~/self-improving/{memory.md,index.md,corrections.md,heartbeat-state.md}
```

## 索引模板

用于 `~/self-improving/index.md`：

```markdown
# 记忆索引

## 热层(HOT)
- memory.md：0 行

## 温层(WARM)
- （暂无命名空间）

## 冷层(COLD)
- （暂无归档）

上次压缩：从未
```

## 纠正日志模板

用于 `~/self-improving/corrections.md`：

```markdown
# 纠正日志

<!-- 格式：
## YYYY-MM-DD
- [HH:MM] 把 X 改为 Y
  类型：format|technical|communication|project
  上下文：纠正发生的位置
  已确认：pending (N/3) | yes | no
-->
```

## Heartbeat 状态模板

用于 `~/self-improving/heartbeat-state.md`：

```markdown
# 自我进化 Heartbeat 状态

last_heartbeat_started_at: never
last_reviewed_change_at: never
last_heartbeat_result: never

## 最近动作
- 暂无
```
