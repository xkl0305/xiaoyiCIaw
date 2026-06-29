# experimental-memory-install-online — exit codes

| Code | Meaning | Recovery hint |
|---|---|---|
| `0` | Success | — |
| `10` | Argument or precondition error | Check mutually exclusive flags, `openclaw.json`, AGENTS.md path, or celiaclaw supervisor fingerprint. Use `--skip-gateway-restart` outside celiaclaw; if only restart control is unavailable, check `restart-skip.json` and `CELIA_SUPERVISORCTL_COMMAND`. |
| `20` | Remote metadata or download failure | Check access to GitCode and `CELIA_ARTIFACTS_REPO_URL`. |
| `30` | SHA256 mismatch | Re-run after clearing the tarball cache. |
| `40` | Extract failure | Remove the partial `<version>-tmp` directory and retry. |
| `50` | Install step failure | See `$CELIA_LOG_DIR/install-online-<ts>.log`. |
| `60` | Unsupported tarball contract | Upgrade the skill bundle or use a newer GaussPD_Memory release. |
| `70` | Lock contention or disk-space refusal | Wait for the current install or free disk under `CELIA_INSTALL_ROOT`. |
| `99` | Internal error | Capture stderr and installer log. |
