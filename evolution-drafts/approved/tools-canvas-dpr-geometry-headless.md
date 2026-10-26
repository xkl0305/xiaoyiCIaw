# Evolution Proposal: canvas高清setTransform(DPR)+几何测量验证+headless三宽度截图
- Created-At: 2026-10-26 14:21
- Target-File: TOOLS.md
- Trigger-Type: struggle + explicit-instruction
- 要点: ①canvas高清必须setTransform(dpr)+cv.width=cssW*dpr, 勿用固定scale(2); ②布局验证以getBoundingClientRect/scrollWidth几何为准, 勿轻信image_reading"偏右/截断"误报; ③多设备headless三宽度--screenshot验证, dispatchEvent在headless不触发canvas点击。
