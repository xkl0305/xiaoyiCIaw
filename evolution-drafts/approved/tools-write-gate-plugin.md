# 进化提案：write-gate 守卫插件用法与时间戳坑沉淀

- **状态**：✅ approved（2026-09-23 用户确认）
- **进化项**：沉淀 write-gate 守卫插件用法 + 时间戳坑经验
- **修改文件**：`TOOLS.md`

## 经验规则

1. **write-gate 用法**：凡写受保护正式文件（MEMORY/USER/SOUL/IDENTITY/TOOLS 及 evolution-drafts/），守卫插件拦截，须先获俞哥确认并写一次性令牌 `.write-gate-allow.json`（`{"allowed":[文件],"exp":<毫秒时间戳>}`）才放行，放行后自动删令牌。
2. **时间戳坑**：令牌 `exp` 必须兼容秒/毫秒——守卫比较用 `Date.now()`（毫秒级），若 `exp` 存秒级导致恒判过期。标准写法统一用毫秒（`Date.now()+5*60*1000`）。
3. **紧急旁路**：`WRITE_GATE_OFF=1` 或 `enabled:false` 可临时关闭守卫（防锁死用，恢复后须重新启用）。

## 落盘位置

- `TOOLS.md` 新增「write-gate：正式文件写操作代码级守卫（2026-09-23 固化）」一节
- 备份：`TOOLS.md.bak-20260923-093656`

## 关联

配套「P0 正式文件写操作前置确认门禁」（进化·强化版）、「案例：措辞微调仍须走流程确认」及 write-gate 插件实现。
