# Evolution Proposal (approved): 人格视角出图系统CLI双通道+介绍须实查纪律

- Created-At: 2026-11-01 19:15
- Approved-At: 2026-11-01 19:19
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle
- Status: APPROVED (已落盘 TOOLS.md)

## Why This Matters
俞哥要求固化本次对话成果。核心问题不在"双通道"事实本身（TOOLS.md 440/456/474 已固化 bridge 层 ark→huawei_sse 双通道），而在**介绍人格视角出图系统时，我凭推断拍出"单通道无分支"结论，被俞哥"出图单通道吗"质疑后实查才发现 CLI 链路实为双通道（火山 ARK 直连优先 + SSE 代理兜底），且漏了关联已固化的通道经验与"五层标准展示口径"**。与此前 351 行同类反复。故固化重点：介绍技能/系统前须实查实际链路 + 关联 TOOLS.md 已固化经验 + 关联记忆里既定展示口径，禁止凭推断下结论。

## Evidence
- 用户原话："没有按介绍技能来介绍""出图单通道吗""记住固化进化一下""确认"
- 教训：我在「模型/分支对比表」写"单通道无分支"，实查 `helpers/cli_generate.py` 才发现：通道 A=火山 ARK 直连（`channel="ark"`，判 url 含 volces.com 且有 api_key）优先；通道 B=SSE 代理（`_call_seedream_sse`）兜底。
- 记忆里已固化"五层标准展示口径（定位/双通道/衣柜/映射/管线）"，本次开头未关联。

## Conflict Points
不与 TOOLS.md 既有 440/456/474 冲突，属补充强化：既有讲 bridge 层配置双通道与 ARK 退化修复；本次新增 CLI 出图链路 A/B 分支判定明细 + "介绍前须实查+关联已固化经验"硬纪律。与 351 行教训同源强化。

## Plan (已执行)
1. 已在 TOOLS.md seedream 通道区块（「Seedream 双通道体检与补回」后）新增固化记录：CLI 出图双通道（ARK 直连 A 优先 + SSE 代理 B 兜底）+ 硬纪律（介绍须实查链路 + 关联已固化经验，禁止凭推断下结论）。
2. 本文件归档至 evolution-drafts/approved/ 完成流程闭环。
