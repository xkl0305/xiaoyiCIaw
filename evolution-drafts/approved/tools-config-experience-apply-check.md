# 进化提案：配置类经验需落地核对现状

- 状态：**已确认（approved，2026-09-25）**
- 修改文件：TOOLS.md

## 背景
"supervisord 一次性脚本 startsecs=0"经验 2026-08-09 已固化到 TOOLS.md，但 2026-09-25 巡检发现 supervisord.conf 的 watch_paired 实际仍是 startsecs=2（FATAL）——文档经验写了，但配置没落实。

## 经验规则
1. **文档经验 ≠ 配置已落实**：配置类经验固化后，必须核实现状真的改了，不只停留在文档文字。
2. 可能原因：当初只写文档没实际改配置，或配置被后续更新/重建覆盖。
3. 巡检时发现"文档经验 vs 实际配置"不一致，要主动对齐（改配置并确认生效）。

## 处理
watch_paired startsecs 2→0 已修复，状态 FATAL→EXITED。
