# Evolution Proposal: 游戏双模式切换实现模式

- Created-At: 2026-10-26 17:01
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction

## Evidence
- 用户确认固化明棋/暗棋双模式切换实现模式(选项②)
- 实战: 明暗大师版用 isMing 变量 + btnMing/btnAn 切换 + draw showType 条件化 + 各模式独立布阵

## Plan
- 已在 TOOLS.md canvas 经验区(补 p 后)追加「补充 q) 游戏双模式切换实现模式」:
  - 模式变量 + 切换按钮 + draw() 按模式分支
  - 各模式独立布阵/文案、切换时状态全重置防混串
