# Evolution Proposal: Dual Memory System Data Source Awareness

- Created-At: 2026-07-07 04:46
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 排查记忆/技能库问题时，如果查错表会浪费大量时间
- AutoMemory 写入的数据库和 yaoyao 记忆系统是两套独立的数据源
- 每次修记忆相关 bug 时都需要先确认数据写在哪张表

## Evidence
- 每日维护报告"采集 876 条"但技能库显示"⏭️ no memories"
- 排查发现 AutoMemory(memory_pipeline) 写 .crusheart.db → memories 表
- 技能库代码查的是 main.sqlite → yaoyao_memories 视图
- 两条不同的路，永远查不到数据
- 耗时多轮才定位到根本原因

## Conflict Points
- None

## Plan
1. 在 TOOLS.md 的已有内容后追加一条记忆系统数据源规则
2. 内容：
```md
### 记忆系统双数据源排查指南

OpenClaw 同时运行两套记忆系统，数据写在不同库/表中：

| 系统 | 数据库 | 表 | 谁写入 |
|:----|:------|:---|:-------|
| AutoMemory（memory_pipeline） | `.crusheart.db` | `memories` | 每日维护记忆采集、对话记录 |
| yaoyao 记忆系统（Celia/yaoyao） | `main.sqlite` | `yaoyao_memories` | yaoyao 插件日常对话写入 |

**排查规则：**
- 遇到记忆查询/技能库投喂数据为空时，先确认数据写在哪张表
- 查看 .crusheart.db 的 memories 表：AutoMemory 的写入目标
- 查看 main.sqlite 的 yaoyao_memories 视图：yaoyao 系统的写入目标
- 两个表的查询列不同：memories 用 content, yaoyao_memories 用 user_text/asst_text
- created_at 格式也不同：memories 是 ISO 字符串, yaoyao_memories 也是字符串
```
3. 追加到 TOOLS.md 末尾
