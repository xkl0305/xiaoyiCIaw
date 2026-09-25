# Evolution Proposal: ❄️ 收尾空行代码级根治方案（reply-dispatcher 收尾归一）

- Created-At: 2026-09-22 21:09
- Target-File: TOOLS.md
- Trigger-Type: explicit-instruction（俞哥要求"记住固化进化一下"）

## Why This Matters
- "❄️ 收尾空行"是反复出现的执行懈怠（当日抓 5+ 次）。仅靠"发前自查"纪律（2026-08-01）与 SOUL.md P0 门禁均无效，因为根因在**生成文本时多打换行**。本次从机制层根治：在 xiaoyi-channel 发送终帧前加"收尾归一"，不再依赖执行纪律。需固化此修复方案与备案，供未来排错复用。

## Evidence
- 俞哥连续多轮指出"怎么又回车空行了/到底修复了没有"，明确"坚持改"。
- 补丁已在 `~/.openclaw/extensions/xiaoyi-channel/dist/src/dispatch/reply-dispatcher.js` 行 370-382 应用：`const normalizedFinalText = fullFinalText.replace(/\s*❄️\s*$/, "❄️")`，final 帧 `text` 改用归一值。
- 单元测试通过（❄️前空行/换行/后空格均归一，正常/无❄️/中间❄️不误伤）；gateway 已于补丁后重启（RUNNING，加载新代码）。

## Conflict Points
- 与 TOOLS.md「操作后回复强制❄️收尾自查（2026-08-01）」、SOUL.md「P0 发送前强制收尾自查门禁」为**升级/补充关系**：不自查纪律→新增代码兜底机制，二者并存（执行自查 + 发送前强制归一双保险），不冲突。

## Plan
- 在 TOOLS.md 追加一条「xiaoyi-channel ❄️ 收尾代码级兜底（2026-09-22 根治）」，记录：①问题根因（生成多打换行，系统原样转发）；②代码修复点（reply-dispatcher.js final 帧发送前对全文本做 `replace(/\s*❄️\s*$/, "❄️")`）；③备份与重启流程（改前 cp .bak、改后 node --check、用 `python3 -m supervisor.supervisorctl restart openclaw-gateway` 重启）；④诚实边界（final 帧归一能否覆盖端侧显示取决于端侧是否重绘，仍应依赖执行自查托底）。
