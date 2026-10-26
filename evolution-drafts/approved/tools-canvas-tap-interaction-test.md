# Evolution Proposal: 棋盘游戏验证必须走真实交互入口

- Created-At: 2026-10-26 16:57
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle

## Evidence
- 用户："记住固化进化一下这个bug"（红棋吃不了黑棋）
- tap() 里 `if(p.side!=='R')return` 拦截点击黑子 → 攻击永不触发；但直接调 movePiece/canEat 测结算三场景全过，未暴露交互 bug
- 教训：结算函数对 ≠ 交互能用；交互入口(tap)的 `return` 守卫会吞掉合法操作

## Plan
- 已在 TOOLS.md canvas 棋盘验证经验区(补充 o 后)新增「补充 p)」：
  - 验证必须走真实交互入口(tap/click)，禁止绕过事件处理直接调底层结算函数
  - 攻击/走子/吃子/翻子要模拟真实点击路径(先 tap 选子再 tap 目标)断言
  - tap() 这类分发器最容易用 return 守卫吞掉合法操作
