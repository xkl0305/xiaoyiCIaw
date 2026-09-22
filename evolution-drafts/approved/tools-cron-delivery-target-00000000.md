# Evolution Proposal: cron 投递目标 00000000 语义修正

- Created-At: 2026-09-20 12:58
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction + struggle

## Why This Matters
- `00000000` 到底是"代称"还是"端侧真实ID"，直接影响 cron 投递配置正确性
- 多次排查看似"成功投递"实则走了回退通道，易误导，需把语义讲透

## Evidence
- 用户质疑："主对话框是端侧的主对话框"、"你确定我的端侧ID不是00000000"
- 实测：实时对话 Route context 显示 `channel: xiaoyi-channel / to: 00000000` → `00000000` 确为端侧主对话框真实ID（实时有效）
- 实测：后台 cron 会话（isolated/固定 session）解析不出 `00000000`，`messageToolSentTo` 回退为 `0380ff...`（主对话框真实地址），但 `delivered: true`
- 现有 TOOLS.md 强制要求7 将 `00000000` 描述为"当前对话会话的代称"——不准确，需修正

## Conflict Points
- 现有"强制要求7"把 `00000000` 称为"代称"、"非端侧ID"，并建议"端侧识别变化时回退0380ff"。新理解：`00000000` 就是端侧主对话框ID（实时对话有效），只是后台cron无法解析需用 `0380ff...` 兜底。需修正强制要求7的语义描述。

## Plan
1. 修正 TOOLS.md 强制要求7 中"代称"的误导描述，改为：
   - `00000000` = 端侧主对话框真实ID，实时对话有效（Route context 实测 `to=00000000`）
   - 后台 cron 会话无法解析 `00000000`，会自动回退 `0380ff...`（主对话框固定地址）兜底，`delivered:true`
   - 新建 cron 到主对话框仍建议用 `0380ff...`（后台稳定可解析）；`00000000` 仅实时对话使用
2. 追加一句兜底经验：投递 `delivered:true` 不等于落到预期窗口，需核对 `messageToolSentTo` / `resolved.to` 是否含预期地址
