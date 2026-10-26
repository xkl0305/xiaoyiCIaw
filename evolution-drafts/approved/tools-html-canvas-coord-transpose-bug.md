# Evolution Proposal: 补强 canvas 方法论坐标转置 bug 教训

- Created-At: 2026-10-25 09:25
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle

## Why This Matters

五子棋 v2 出现"点了没反应 / 红圈画在空位 / 棋子显示错位"，根因是 `place()` 用 `board[x][y]` 而其余代码用 `board[行][列]`，两组数组维度约定不一致导致整体转置错位。且中心对称点 (7,7) 转置后仍原位，掩盖了 bug，直到落非对称点才暴露。该教训补充进既有「纯前端 HTML 交互作品制作与验证方法论」第 5 条，能避免同类 canvas 作品再踩。

## Evidence

- 用户原话："怎么点击不了红圈，你自己再好好测试一下"；"记住固化进化一下"
- 工具踩坑：五子棋 place() 写 board[x][y]，draw()/winAt()/点击换算全用 board[行][列]，坐标转置；AI lastMove 红圈落在空位、玩家点击错位落子。
- 调试发现：真实点击中心 (7,7)、对称点测试全 PASS 掩盖问题；改用非对称点 (3,3)/(10,4) + 每步核对 lastMove 与 board 是否落在同一格才暴露。

## Conflict Points

- 无新增规则冲突；是对 TOOLS.md「纯前端 HTML 交互作品制作与验证方法论」既有第 5 条（逻辑函数与数组下标坐标系保持一致）的**补充细化**（补充 a/b 两点），不覆盖原内容。

## Plan

在 TOOLS.md 方法论第 5 条下追加两点细化教训：
- 补充 a) **写函数与读函数的数组维度约定必须全局统一**：五子棋 `place()` 写成 `board[x][y]` 而渲染/点击/判定用 `board[行][列]`，导致落子、显示、AI lastMove 红圈整体转置错位，表现"点了没反应 / 红圈画空位 / 棋子错位"。
- 补充 b) **中心对称坐标会掩盖转置 bug**：(7,7) 这类横竖对称点转置后仍原位，不易暴露；测试必须用**非对称交叉点**真实点击，且每次核对 AI `lastMove` 是否真落在对应棋盘格上。
