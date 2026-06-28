# experimental-memory-install — exit codes / 退出码

| Code | English | 中文 | Recovery hint |
|---|---|---|---|
| `0` | success | 成功 | — |
| `10` | argument / precondition error (mutually exclusive flags, missing local tarball, bad mode, remote flag on offline skill) | 参数或前置条件错误（互斥标志、本地包缺失、未知 mode、离线 skill 收到远端标志） | For `/experimental-memory-install`, pre-stage a matching tarball in `$GSPD_TARBALL_DIR`. If the user agrees to use the network, switch to `/experimental-memory-install-online`; do not pass remote flags to the offline skill. |
| `20` | network failure (artifact mirror clone, asset download) | 网络失败（镜像 clone 或资产下载） | Check connectivity to `gitcode.com`. The mirror cache lives at `~/.openclaw/extensions/gspd_memory/_artifacts-mirror/`; `rm -rf` it to force a re-clone. |
| `30` | SHA256 mismatch on downloaded tarball | 下载的 tarball SHA256 不匹配 | Re-run; if it persists, check `GaussPD_Artifacts/index/<v>/.../manifest.toml` for the canonical hash and inspect the asset URL by hand. |
| `40` | tarball extract failure (corrupt archive, path traversal guard) | 解压失败（损坏 / 路径越界） | Re-download. The orchestrator extracts to `<v>-tmp/` first then renames; a leftover `<v>-tmp/` directory means the extraction stopped midway — safe to `rm -rf`. |
| `50` | platform install hook (`scripts/install.sh`) returned non-zero | 平台 install hook 失败 | See the audit log printed by the orchestrator. The platform hook is the celiaclaw / openclaw / celiapro `scripts/install.sh` shipped *inside the tarball*. |
| `60` | contract refused | 契约拒绝 | Either: tarball is missing `scripts/contract.toml` (pre-contract artifact, no longer supported — request a re-build of the GaussPD_Memory release pipeline); or tarball's `contract_version` isn't in this skill bundle's `supported_contract_versions` (run `cd $skills_dir && git pull` to upgrade the bundle). |
| `70` | lock contention (concurrent install) or insufficient disk | 锁竞争或磁盘空间不足 | Concurrent install: wait or check `~/.openclaw/extensions/gspd_memory/.lock` for stale processes. Disk: free up the partition holding `~/.openclaw/extensions/gspd_memory/` (need ~3× tarball size). |
| `99` | internal error (unhandled Python exception) | 内部错误（未处理的 Python 异常） | Capture stderr and file an issue. |

Exit codes 10–70 are **safe** — the orchestrator either failed early (no
state changed) or rolled back its work. Code 99 means something unexpected
happened; check `~/.openclaw/logs/gspd_memory/` and the partial state under
`~/.openclaw/extensions/gspd_memory/install/<v>-tmp/` (if present) to assess.
