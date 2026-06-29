# experimental-memory-install — environment variables / 环境变量

All env vars below are read by the orchestrator (`scripts/orchestrator.py`).
Most have sensible defaults; override only when you need to.

| Variable | Default | Purpose |
|---|---|---|
| `CELIA_LANG` | `en` | UI language for `[PROMPT_*]` / `[PLAN]` strings (`zh` or `en`). The skill auto-detects from conversation locale, so end users rarely set this manually. |
| `CELIA_INSTALL_ROOT` | `$CELIA_CONFIG_DIR/extensions/celia_memory` (celiaclaw → `/home/sandbox/.openclaw/extensions/celia_memory`; openclaw → `~/.openclaw/extensions/celia_memory`) | Root for the Celia memory subsystem on this host. Layout under it: `package/` (tarball cache), `install/<version>/` + `install/current` + `install/previous` symlinks (extracted bundles, latest two kept), `.lock` (concurrent-install flock). |
| `CELIA_LOG_DIR` | `$CELIA_CONFIG_DIR/logs/celia_memory` | Audit log directory: `install-<ts>.log` and `reboot-<ts>.log` from the orchestrator; `celia_memory.log[.1/.2/.3]` runtime output from the platform hook. |
| `CELIA_TARBALL_DIR` | `$CELIA_INSTALL_ROOT/package` | Local source for `/experimental-memory-install`. Image-build pipelines pre-stage tarballs here. |
| `CELIA_PREBUILT_DIR` | (none) | Compatibility alias for `CELIA_TARBALL_DIR`; honored as a fallback so existing image-build scripts that set this don't break. New scripts should set `CELIA_TARBALL_DIR`. |
| `CELIA_PLUGIN_DIR` | `$CELIA_INSTALL_ROOT/install/current` (both platforms — i.e. `/home/sandbox/.openclaw/extensions/celia_memory/install/current` on celiaclaw; `~/.openclaw/extensions/celia_memory/install/current` on openclaw) | Where `scripts/install.sh` lays plugin runtime artifacts (`bin/celia_memory_mcp_server`, `memory-plugin/`, `shared/`, `celiaclaw/`). With the new layout this equals the version-pinned install root via the `current` symlink. |
| `CELIA_CONFIG_DIR` | `/home/sandbox/.openclaw` (celiaclaw) <br> `~/.openclaw` (openclaw) | Directory containing `openclaw.json`, `workspace/`, `memory/`. |
| `CELIA_SUPERVISORD_CONF` | `/home/sandbox/supervisord.conf` (celiaclaw only) | Path used by the celiaclaw install hook when injecting environment vars. |
| `CELIA_LOG_FILE_PATH` | `$CELIA_LOG_DIR/<verb>-<ts>.log` | Audit log destination for a single invocation. The orchestrator overrides per invocation; the platform hook honors the value the orchestrator passes. |
| `CELIA_LOG_FILE` | `$CELIA_LOG_DIR/celia_memory.log` | Runtime log file for `celia_memory_mcp_server` (read by `LogInitFile`). The celiaclaw install hook injects this into the `[program:openclaw-gateway]` `environment=` line so supervisord-spawned mcp_server inherits it. |
| `CELIA_LOG_MAX_BYTES` | `5242880` (5 MiB) | Rotation threshold in bytes. Read by `LogInitFile` via `UtlGetEnv`; on overflow the runtime log rotates `.log → .log.1 → .log.2 → ...`. Set to `0` to disable rotation. The supervisord injection writes the default `5242880` so production gets 5 MiB rolling out of the box. |
| `CELIA_LOG_BACKUPS` | `3` | Number of rotated backups kept. Read by `LogInitFile`; chain rename keeps `.log.1` … `.log.<N>`. Sanitized to `1` if `<=0`. Together with `CELIA_LOG_MAX_BYTES`, gives the celiaclaw production layout's `celia_memory.log[.1.2.3]` 5 MiB × 3 design. |
| `CELIA_DB_PATH` | `$CELIA_CONFIG_DIR/workspace/memory/celia_memory/celia_memory.db` | DB file path used by snapshot + status. Override if you keep memory DB elsewhere; legacy `workspace/memory/celia_memory.db` and `memory/celia_memory.db` are still probed as fallbacks. |
| `CELIA_ARTIFACTS_REPO_URL` | `https://gitcode.com/CayleyVanguard/GaussPD_Artifacts.git` | Git URL of the artifacts mirror that the orchestrator shallow-clones into `$CELIA_INSTALL_ROOT/_artifacts-mirror/` to read `latest-{stable,rc,dev}.txt` and `index/<v>/<plat>/<arch>/manifest.toml`. Set this when a fork publishes releases to a different mirror — e.g. when developing with `integration/celiaclaw/local_package.sh --direct-push` against a personal `GaussPD_Artifacts` fork — so the install pipeline pulls from there instead. The orchestrator detects URL changes against an existing cache and re-clones, so swapping the env var "just works" without manually wiping `_artifacts-mirror/`. |

## LLM credentials — `openclaw.json` is the single source of truth

The seed `openclaw.json` no longer ships any embed/rerank fields. `memory-plugin/index.ts` resolves embedding credentials at plugin load time using a **two-tier** priority chain (high → low):

1. **`plugins.entries.memory-celia.config.embed`** — explicit override (JSON literal or `${VAR}` placeholder). Most users won't set this; reserved for the case where Celia must point at a different embedding endpoint than OpenClaw's native memorySearch.
2. **`agents.defaults.memorySearch.{model, remote.{baseUrl, apiKey, headers["x-uid"]}}`** — auto-borrowed from OpenClaw's native memory search. **This is the recommended source.** Configure once in memorySearch (which OpenClaw also uses), Celia reuses it.

`process.env.OPENAI_EMBED_*` is **no longer** consulted for embed credentials — `OPENAI_EMBED_*` only appears as the internal IPC channel between the TS plugin and the C `celia_memory_mcp_server` subprocess (the plugin sets these env vars on the child process; users should not set them themselves).

The skill's `install.sh` no longer injects `OPENAI_EMBED_*` into supervisord `[program:openclaw-gateway] environment=` — the plugin reads `openclaw.json` directly at runtime instead. install.sh still scrubs any stale `OPENAI_EMBED_*` tokens left over from older installs (so removing them from the source doesn't leave residue in supervisord).

| Variable | Role | Effect when unset |
|---|---|---|
| `CELIA_CHAT_UID` | **TS→C IPC.** memory-plugin sets this from `agents.defaults.memorySearch.remote.headers["x-uid"]` (preferred) or `process.env.PERSONAL_UID` (fallback). C-side `mcp_main` reuses it as both `chatUid` and `embedUid`, triggering sandbox-mode header injection (`x-api-key` / `x-uid` / `x-request-from: openclaw`) for both chat and embed adapters. Required for xiaoyi gateway and similar private-header endpoints. | Bearer mode: plain `Authorization: Bearer <apiKey>`. Works for fireworks.ai, OpenAI, etc. — any standard OpenAI-compatible endpoint. |
| `OPENAI_RERANK_API_KEY` / `OPENAI_RERANK_BASE_URL` / `OPENAI_RERANK_MODEL` | Optional cross-encoder rerank endpoint. Set all three together to enable. | Rerank disabled — `celia_memory_mcp_server` runs noop adapter, search falls back to bi-encoder scores. |

## Internal — set by the orchestrator before calling the platform hook

| Variable | Purpose |
|---|---|
| `CELIA_EXTRACT_ROOT` | Where the orchestrator atomically extracted the tarball. Platform hooks treat this as their `INSTALL_DIR`. **Don't set yourself**; the orchestrator owns it. |
