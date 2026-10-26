# Evolution Proposal: HTML棋盘游戏-棋子坐标来源与运行时异常排查

- Created-At: 2026-10-26 01:40
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 2026-10-26 制作军旗人机对战HTML时，连踩4个坑（shuffle未定义、大本营未双占、genMoves取不到坐标、flyAlong混写），其中2个是旧方法论未覆盖的新经验，值得沉淀避免同类任务（象棋/五子棋/军旗/四国军棋等canvas棋盘游戏）再犯。

## Evidence
- 坑A「棋子坐标缺失」：`genMoves(piece)` 内部用 `piece.r / piece.c`，但棋子对象只存 `{t,side,id}`，坐标是 `board[row][col]` 隐含索引——导致走法生成静默返回空（redMoves=0、AI决策失败），而画面因 draw() 用 board 索引遍历仍正常显示，极难察觉。解法：逻辑函数显式传 `(r,c)` 或用 board 索引取，别从棋子对象读隐含字段坐标。
- 坑B「运行时静默中断」：`shuffle` 未定义、`cells.filter(([r])… board[r][c])` 解构漏 c，都在 boot 启动时抛 ReferenceError 导致脚本中断、页面只剩静态默认文案（棋盘空白但 UI 框架在）。解法：用 CDP `Runtime.exceptionThrown` 事件抓运行时异常（比看截图更早、更准），或用 node 提取 `<script>` 做语法校验（只能抓语法，抓不到运行时 ReferenceError）。
- 旧方法论6条已覆盖：真实点击验证/canvas显示尺寸JS硬算/draw空守卫/高度自适应居中/行列索引勿颠倒/image_reading亲眼看图。

## Conflict Points
- 无。此为对既有「纯前端HTML交互作品制作与验证方法论(2026-10-25固化)」的补充新增，不覆盖旧条目。

## Plan
1. 在 TOOLS.md「纯前端 HTML 交互作品制作与验证方法论（2026-10-25 固化，实战：象棋+五子棋 canvas 人机游戏）」区块，追加两条新经验：
   - **补充 c) 棋子坐标从板索引或显式传参，勿从棋子对象读隐含字段** — 棋子对象只存类型/阵营/id，位置是 board[row][col] 隐含索引。逻辑函数（走法生成/AI/判定）必须显式传 (r,c) 或从 board 索引取；若函数内部取 `piece.r/piece.c` 这类不存在的字段，走法会静默返回空而画面（draw 用 board 索引）仍正常，属于难察觉的静默 bug。定位法：断言"生成走法数"。案例：junqi.html genMoves 首版取 piece.r 导致 redMoves=0。
   - **补充 d) 运行时脚本中断用 CDP Runtime.exceptionThrown 抓** — canvas 棋盘启动报 ReferenceError（如函数未定义 shuffle、filter 解构漏参）时，页面脚本中断、棋盘空白但 UI 框架正常显示，易误判"画面没问题"。解法：node 连 CDP 监听 `Runtime.exceptionThrown` + `Page.reload` 抓具体报错栈，比看截图早且准；node `new Function` 语法校验只能抓语法错、抓不到运行时错。
2. 插入位置：在第5条(逻辑函数与数组下标)之后、第6条(验证画面)之前追加 c/d，原内容保留。

## Apply-Text（追加到该区块第5条之后）
```
   - **补充 c) 棋子坐标从板索引或显式传参，勿从棋子对象读隐含字段** — 棋子对象只存 {t,side,id}，位置是 board[row][col] 隐含索引。走法生成/AI/判定等逻辑函数必须显式传 (r,c) 或从 board 索引取；若写成 `genMoves(piece)` 内取 `piece.r/piece.c`，棋子没有这些字段会静默返回空走法（redMoves=0、AI决策失败），而 draw() 用 board 索引遍历画面仍正常，属于难察觉的静默 bug。定位：断言"生成走法数>0"。（案例：junqi.html 首版）
   - **补充 d) 运行时脚本中断用 CDP Runtime.exceptionThrown 抓** — canvas 棋盘游戏启动报 ReferenceError（函数未定义如 shuffle、filter 解构漏参）时脚本中断，棋盘空白但 UI 框架正常，易误判"画面没问题"。解法：node 连 CDP 监听 `Runtime.exceptionThrown` + 触发 `Page.reload` 拿具体报错栈，比截图早且准。注意 `node -e new Function(js)` 只抓语法错、抓不到运行时 ReferenceError。
```
