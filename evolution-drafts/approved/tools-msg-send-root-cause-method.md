# Evolution Proposal: 通道文本显示问题的根治方法论

- Created-At: 2026-10-25 06:51
- Target-File: TOOLS.md
- Trigger-Type: user-confirmed（俞哥确认固化本次排查经验）

## Why This Matters
- 本次 ❄️ 收尾空行从"靠执行自查→final归一→补流式partial→源头归一"反复迭代，暴露改文本发送链路的通用排错教训：改错层/改错文件/漏链路会让修复无效。固化方法论避免未来重复踩坑。

## Evidence
- 09-22 加 reply-dispatcher final 归一；10-25 补流式 partial 归一仍空行；最终在 formatter.js sendA2AResponse() 公共出口源头归一，一次覆盖全部发送路径。全程靠 package.json main 确认运行文件、grep sendA2AResponse 调用点 mapping 链路、image_reading 截图定性端侧形态。

## Conflict Points
- None（新增排查经验，与既有「xiaoyi-channel ❄️ 收尾代码级兜底」条目互补，更聚焦"方法论"层面）。

## Plan
- 在 TOOLS.md 新增「通道文本显示问题的根治方法论（2026-10-25）」：①确认运行实际加载文件(package.json main 指向 dist/src)；②mapping 目标消息发送链路(grep sendA2AResponse 所有调用点)；③文本后处理放公共出口源头(formatter.js sendA2AResponse)，而非逐个调用点；④用端侧截图(image_reading)定性端侧真实形态，区分"文本内容的换行"vs"端侧渲染层插空行"。
