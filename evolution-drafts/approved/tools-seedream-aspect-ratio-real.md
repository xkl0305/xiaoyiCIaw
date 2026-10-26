# 种子提案: 华为通道横竖方画幅真像素实测

- 日期: 2026-10-21
- 状态: approved
- 进化项: 补充 TOOLS.md 「seedream 生图排错与 size 支持实测」段,补真·比例像素证据
- 修改文件: TOOLS.md(seedream size 段)

## 补充规则
1. 华为横/竖/方靠 prompt 构图词实现,且输出硬件真实比例
2. 实测像素: 横屏3K=4704x2016;竖屏3K=2304x4096;方形2K=2048x2048
3. --size 只认2K/3K,4K系no_image
4. _SIZE_MAP仅对ark/siliconflow生效,华为SSE读prompt意图
