# Evolution Proposal: Excel 高级补完经验固化(VBA宏/透视表进阶+DAX/图表进阶)

- Created-At: 2026-10-30 10:24
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + workflow
- Status: approved

## Why This Matters
- Excel 全方向拉满的最后三块:VBA 宏/透视表进阶+Power Pivot/DAX/图表进阶,均有实操验证
- VBA 宏已写真实可用 .bas(批量标记+汇总),Python 等价逻辑验证通过
- 透视表三招(pandas pivot_table 等价验证):交叉+总计/计算字段/多级分组
- 组合图 openpyxl 实做(柱+线双轴)

## Evidence
- VBA: End(xlUp)找尾/ScreenUpdating提速/坑(.xlsm才存宏/宏安全/Option Explicit/F8调试)
- 透视表: 计算字段口径(均价vs求和后除)/切片器连多表需共享数据模型/刷新才含新数据
- 图表: 组合图次坐标轴必勾否则折线贴地/动态图表Ctrl+T表格最稳/迷你图打印不出

## Conflict Points
- 无重复;为 1229「高级方向经验」的 Excel 补完,新增独立小节

## Plan
- TOOLS.md 在 1229 高级条目后新增「Excel 高级补完:VBA/透视表进阶/图表进阶」小节
