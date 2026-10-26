# Evolution Proposal: 读图通道故障排查三层法 + 脚本 debug 需 import sys

- Created-At: 2026-10-26 15:54
- Target-File: TOOLS.md
- Trigger-Type: struggle + explicit-instruction

## Evidence
- 用户："skill 脚本一个潜在bug 修了——原来 import sys 缺失会导致 debug 打印时崩，记住固化进化一下"
- image_reading 连续报「Premature close」（工具连接层故障）
- xiaoyi 脚本全链路：上传成功+SSE建立+解析正常，但 API 端 streamContent 一路为空 → null（服务端未吐内容，非脚本 bug）
- 脚本 debug 加 file=sys.stderr 崩：`name 'sys' is not defined` → 需先 import sys

## Plan
- 已落 TOOLS.md「图像理解场景接口使用要求」小节末尾新增「读图失败排查三层法」：
  1. 读图遇障勿反复硬试 image_reading，先分清故障层
  2. 三层定位：image_reading(工具连接) → xiaoyi-image-understanding脚本(上传/SSE) → 小艺API端(streamContent空=服务端)
  3. 脚本 debug 用 file=sys.stderr 前务必 import sys
