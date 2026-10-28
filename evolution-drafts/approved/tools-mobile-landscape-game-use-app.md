# Evolution Proposal: 手机端锁横屏游戏直接走 App，别在网页里折腾横屏

- Created-At: 2026-10-28 22:05
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle

## Why This Matters
- 手机浏览器（尤其鸿蒙自带浏览器）对网页横屏的支持不可靠且无法绕过，实测多轮兜底全部失效；此结论可避免未来同类任务重复踩坑 6+ 轮

## Evidence
- 用户原话："看样子只有搞APP这一种方法"、"记住固化进化一下，手机端搞横屏游戏HTML文件不行需要搞APP这种方式"
- 红十游戏横屏实测 6+ 轮失败：CSS 旋转 view（方位错乱）→ orientationchange 监听（不触发）→ 400ms 轮询 innerWidth（视口尺寸不更新）→ canvas clientWidth 自检重排（仍不生效）；用户截图证实横屏时画面为竖屏 buffer 被 CSS 拉伸（牌面超宽变形、AI 位置错乱）
- 最终解法：DevEco Studio 工程 module.json5 配置 `"orientation": "landscape"` 锁横屏 + Index.ets 用 Web 组件加载 `$rawfile` 内置 HTML，App 打开即横屏，一步到位

## Conflict Points
- None（TOOLS.md 既有"横屏"条目均为图像生成比例话题，无冲突）

## Plan
1. 在 TOOLS.md「canvas 游戏开发经验」补充系列末尾（补充 t 之后）追加「补充 u）手机端锁横屏游戏交付方式」条目
2. 内容：手机浏览器横屏不可靠的实测结论 + 直接走 App 的正解（DevEco orientation landscape + Web 组件 rawfile）+ 工程模板路径 workspace/hongshi-app/
