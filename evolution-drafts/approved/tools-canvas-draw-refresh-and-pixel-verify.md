# Evolution Proposal: 纯前端canvas作品-数据变更必须draw刷新+验证到画面像素层

- Created-At: 2026-10-26 11:05
- Target-File: TOOLS.md
- Trigger-Type: struggle + explicit-instruction

## Why This Matters
- 四国军棋v6做"重新布阵/重新开始"时，两个按钮把棋盘数据(board/setupAll)重新排了，但**漏调 draw() 刷新 canvas**，导致数据变了、画面却没重绘。用户连续反馈"全部没重新布局/故障"，本地测试只检查了 board 数据结构(changed:true)误判正常，实际画面像素没变。这是纯前端canvas作品通用盲区，非单次问题。

## Evidence
- 用户原话："全部没重新布局"、"开始对战变成重新布阵按钮"、"四个按钮里面必有一个有bug"
- 根因：btnShuffle.onclick / btnRestart.onclick 内 setupAll() 改数据后未调用 draw()（悔棋按钮末尾有 draw() 所以正常）
- 我的验证盲区：之前测试用 evaluate 读 board 结构对比(changed:true)判定"重布局生效"，但没看 canvas 像素；定位真因后才改用 toDataURL 前后对比，确认画面未刷新。

## Conflict Points
- 与 TOOLS.md 既有「纯前端 HTML 交互作品制作与验证方法论」第5/6条(真实交互路径验证/canvas尺寸/初始化顺序/亲眼验证)相关但不重复，为新增补充项。

## Plan
在 TOOLS.md「纯前端 HTML 交互作品制作与验证方法论」第5条后新增一条补充规则(编号顺延,当前末尾为补充j):

```
   - **补充 k) 数据变更后必须 draw() 刷新，验证须到 canvas 像素层** — canvas 游戏里，任何修改棋盘/UI 数据的按钮或动作(重新布局/重新开始/重置等)，改完数据后**必须显式调用 draw()**，否则数据变了画面却不刷新，用户看到"点了没反应/没重布局"。(案例: 四国军棋v5 "重新布阵/重新开始"漏调 draw，用户报"全部没重新布局")。验证"按钮是否生效"**不能只看逻辑/数据结构返回值(changed:true 也不代表画面变了)**，必须**对比 canvas 像素**——用 `cv.toDataURL() 前后 !==` 判定画面真实变化，或截图肉眼确认，才能算通过。
```
