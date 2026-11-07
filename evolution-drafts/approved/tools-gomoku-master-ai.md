# Evolution Proposal: 五子棋大师级 AI 引擎 + 走子类搜索不污染悔棋栈

- Created-At: 2026-10-28 23:06
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- 五子棋"大师级"AI 有清晰可复用的引擎方案（精细棋型评估+negamax 迭代加深），未来做五子棋/黑白棋等棋类可直接套用
- 走子类游戏搜索里 place/undo 复用玩家历史栈会污染悔棋，通用 bug 模式

## Evidence
- 用户原话："难易程度为大师级"、"记住固化进化一下"
- 大师级 AI 实测：5 步即形成五连获胜（v4）；粗糙窗口计分(v3)强度不足
- 修复 v3："undo(){ hist.pop() }" 被搜索复用污染玩家悔棋栈

## Conflict Points
- 与补充 r"AI undo 索引错位"是不同 bug（r 是下标写错、本项是复用栈污染），互补无冲突

## Plan
1. TOOLS.md「补充 u」后追加「补充 v) 五子棋大师级 AI 引擎 + 搜索不污染悔棋栈」
2. 内容：大师级 AI 五件套（精细分档评估/四方向线段扫描/negamax 迭代加深+alpha-beta/启发式排序+候选裁剪/顶层预检+时间盒）+ 搜索禁复用玩家 hist 栈（用独立 sp() 函数）
