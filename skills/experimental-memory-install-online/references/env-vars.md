# experimental-memory-install-online — environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CELIA_CONFIG_DIR` | `/home/sandbox/.openclaw` | Docker sandbox OpenClaw config root. |
| `CELIA_INSTALL_ROOT` | `$CELIA_CONFIG_DIR/extensions/celia_memory` | Install root containing `package/`, `_artifacts-online-mirror/`, `.online-install.lock`, and `install/<version>/`. |
| `CELIA_TARBALL_DIR` | `$CELIA_INSTALL_ROOT/package` | Download cache for remote tarballs. |
| `CELIA_LOG_DIR` | `$CELIA_CONFIG_DIR/logs/celia_memory` | Installer logs. |
| `CELIA_ARTIFACTS_REPO_URL` | `https://gitcode.com/CayleyVanguard/GaussPD_Artifacts.git` | Remote artifacts repository cloned sparsely for latest pointers and manifests. |
| `CELIA_AGENTS_MD_SRC` | release `celiaclaw/config/AGENTS.md` | Optional AGENTS.md source path. Equivalent to `--agents-md`. |
| `CELIA_NPM_REGISTRY` | `https://registry.npmmirror.com` | npm registry used for runtime dependency installation. |
| `CELIA_SKIP_GATEWAY_RESTART` | `0` | Set to `1` to skip post-install gateway restart scheduling. |
| `CELIA_RESTART_DELAY` | `5` | Delay in seconds before detached supervisor restart; invalid values fall back to 5 and values above 300 are capped. |
| `CELIA_GATEWAY_SERVICE` | `openclaw-gateway` | supervisor service name used for status and restart diagnostics. |
| `CELIA_SUPERVISORD_CONF` | `/home/sandbox/supervisord.conf` | celiaclaw supervisor config path used as part of the environment fingerprint. |
| `CELIA_SUPERVISORCTL_COMMAND` | unset | Optional supervisorctl-compatible command override. When unset, the installer tries `supervisorctl` in PATH, then `python3 -m supervisor.supervisorctl`. |
| `CELIA_ALLOW_NON_CELIACLAW` | `0` | Set to `1` only for controlled debugging outside the celiaclaw supervisor fingerprint. |
| `CELIA_OPENCLAW_HEALTHCHECK_URL` | unset | Optional URL checked by the background restart diagnostic script after restart. |
| `CELIA_ARTIFACTS_CACHE_TTL` | `300` | Seconds before refreshing the sparse GaussPD_Artifacts mirror. |

The installer writes DFX artifacts under
`$CELIA_LOG_DIR/diagnostics/<timestamp>/`, including environment snapshots,
supervisor controller resolution, supervisor status before/after restart,
restart logs, `restart-skip.json` when auto restart is not scheduled, and
`post-install.json`.
