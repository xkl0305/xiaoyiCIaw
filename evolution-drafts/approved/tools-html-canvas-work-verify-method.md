# Evolution Proposal: HTML Canvas 交互作品制作与验证方法论

- Created-At: 2026-10-25 08:58
- Updated-At: 2026-10-25 09:02
- Target-File: TOOLS.md
- Trigger-Type: struggle + workflow

## Why This Matters

制作纯前端 HTML 交互作品（如象棋/五子棋这类 canvas 人机游戏）时，连续多轮被用户指出"点不动 / 画面变形 / 外框比例错"，根因集中在 canvas 渲染、初始化顺序、布局、验证方式。均已踩坑实测，值得固化为可复用方法论，避免同类任务反复返工。

## Evidence

- 用户原话：
  - "棋盘动不了"；"棋盘画面不对"
  - "怎么变成不是正方形的窗口了"；"外框为什么是竖屏，你横屏、竖屏、正方形，分不清楚吗"
- 工具踩坑摘要：
  - 真实点击坐标与 canvas 显示尺寸（CSS vs 内部像素/DPR）错位 → 点了没反应
  - canvas 用 CSS `width:100%` 强制撑宽、高度被视口压 → 棋盘横向拉伸变形（aspect 从 0.9 变 1.38）
  - `resize()->draw()` 遍历空 board 抛异常 → 后续 `newGame()` 未执行 → 白板无棋子
  - 卡片 `height:100%` 撑满屏高 → 竖屏外框变竖长条
  - 五子棋 `winAt` 行列索引颠倒（board[col][row] vs board[row][col]）→ 胜利检测/AI 识别五连失效

## Conflict Points

- None（TOOLS.md 已有 image_reading 强制规则，本次为新增"客户端 HTML 交互作品制作验证"主题，不冲突）

## Plan

在 TOOLS.md 追加「纯前端 HTML 交互作品制作与验证方法论（2026-10-25 固化）」，要点：
1. **必须走真实用户交互路径验证**：真实点击/触摸事件 + 正确坐标换算，勿只调逻辑函数（象棋"点不动"就是漏了 canvas 显示尺寸与内部像素错位）。
2. **canvas 显示尺寸用 JS 硬算**：`cv.style.width/height` + `cv.width=cssW*dpr`，按目标宽高比在 JS 里算好；勿依赖 CSS `width/aspect-ratio`（不同浏览器对 canvas 替换元素缩放处理差异导致变形）。
3. **初始化顺序坑**：`resize()->draw()` 遍历空数据结构会抛异常，导致后续 init 未执行→白板。`draw()` 开头必须加空守卫（`if(!data||!data.length) return`），或先 init 再 resize。
4. **页面整体布局**用高度自适应 + 内容居中（`height:auto` + `margin:auto`），勿 `height:100%` 撑满屏（竖屏变竖长条）；主内容尺寸用 JS 按视口可用高（`innerHeight` 预留头尾）取 `min(宽,高)`。
5. **逻辑函数与数组下标坐标系保持一致**（行列/交叉点索引勿颠倒），否则胜利检测、AI 走子全失真。
6. **验证画面必须亲眼看**：本地无可视化浏览器时，起接收 POST server + `canvas.toDataURL` 导出 PNG + `image_reading` 读图，勿只看逻辑值判"画面正常"。
