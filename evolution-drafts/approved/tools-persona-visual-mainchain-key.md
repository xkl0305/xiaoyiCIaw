# Evolution Proposal: 人格视角出图需注入 MAINCHAIN_PROOF_KEY

- Created-At: 2026-09-30 21:30
- Target-File: TOOLS.md

## Why This Matters

跑人格视角出图 CLI 真出图时会因环境缺 `MAINCHAIN_PROOF_KEY` 而 fail-closed（`RuntimeError: missing_runtime_secret`），易被误判为"系统坏了/没在运行"，实际是环境没带证明密钥。

## Evidence

- 用户原话：「人格视角出图系统」「2（启用来出一张图）」「记住固化进化一下」
- 工具踩坑：`python3 -m xiaoyi_persona_visual.helpers.cli_generate --text "..." --no-dry-run` 无 MAINCHAIN_PROOF_KEY 时在签发 mainchain proof 处抛 `missing_runtime_secret`；默认 dry_run=True 只到 proof 前构建、不触发生图
- 该密钥为 local 默认值 `local_test_mainchain_secret`，存于工作区 `.env`（`MAINCHAIN_PROOF_KEY=local_test_mainchain_secret`），部署脚本 `deploy/load_secrets.sh` 从 runtime.yaml 读 `mainchain_proof_key` 注入；仅用于本地 proof 签 HMAC、不参与 AI 生图、无敏感泄漏

## Conflict Points

- TOOLS.md 已有「人格视角出图系统·衣柜统一口径」「Seedream 双通道体检」等条目，均聚焦通道/衣柜/配置，未收录 MAINCHAIN_PROOF_KEY 这条 fail-closed 出图坑点 → 本次为同主题新增补充，不构成冲突。

## Plan

在 TOOLS.md「人格视角出图系统」相关段落追加一条运维坑点：

1. 出图命令：`MAINCHAIN_PROOF_KEY=local_test_mainchain_secret python3 -m xiaoyi_persona_visual.helpers.cli_generate --text "<描述>" --mood <情绪> --scene <场景> --no-dry-run`
2. 关键点：默认 dry_run=True 只到 proof 前构建；`--no-dry-run` 才真出图；缺 `MAINCHAIN_PROOF_KEY`/`PERSONA_VISUAL_MAINCHAIN_SECRET` 会 fail-closed（`RuntimeError: missing_runtime_secret`）
3. 密钥来源：`.env` 的 `local_test_mainchain_secret`（local 证明密钥，仅签 HMAC，不参与 AI 生图）；无 ARK 直连环境时自动 fallback SSE 代理（seedream 5.0）
4. 出图落到 `workspace/.persona_visual/generated/`；给用户回传用 `send_file_to_user`
