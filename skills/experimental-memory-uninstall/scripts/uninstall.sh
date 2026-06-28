#!/bin/bash
# uninstall.sh — experimental-memory-uninstall skill entry. Delegates to the shared
# experimental-memory-install orchestrator with uninstall-* modes.
#
# 模式由 $GSPD_UNINSTALL_MODE 决定（disable | remove | purge），透传给
# 平台 hook（scripts/uninstall.sh in tarball）。
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[experimental-memory-uninstall] FATAL: python3 not found" >&2
    exit 99
fi

exec python3 "$SCRIPT_DIR/orchestrator.py" "$@"
