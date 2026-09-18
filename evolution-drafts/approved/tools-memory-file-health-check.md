# Evolution Proposal: 长期记忆文件(MEMORY.md)健康体检

- Created-At: 2026-09-17
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- MEMORY.md 曾被"固化噪声"污染：内嵌 3683 条纯 hash 记录（`📝 固化: 16位hex`）+ 表格碎片 + 原始英文 prompt，文件膨胀到 2.2MB/5.1万行，影响加载与 token 消耗，甚至一度被系统判定 MISSING。
- 需要一套快速体检清单，避免"文件被噪声撑爆却看不出问题"。

## Evidence
- 用户询问"memory.md 有没有 bug"，体检发现：CELIA_MEMORY_SCENES 配对正常，但存在 3683 条纯 hash 固化记录、6699 条固化记录总量、13 处超长行，均为噪声/污染。
- 结构无损坏，纯粹是体积与噪声问题。

## Conflict Points
- None

## Plan
- 在 TOOLS.md「Additional Tool Details」下新增小节 `### 长期记忆文件(MEMORY.md)健康体检（2026-09-17 固化）`。
- 体检清单：BEGIN/END配对、纯hash固化记录、文件体积、超长行/碎片、结构完整性。
- 清理纪律：备份→仅删噪声→经用户确认再动手。
