#!/bin/bash
# status.sh — experimental-memory-status skill entry. Delegates to the shared
# experimental-memory-install orchestrator with --mode=status. Read-only.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[experimental-memory-status] FATAL: python3 not found" >&2
    exit 99
fi

exec python3 "$SCRIPT_DIR/orchestrator.py" --mode=status "$@"
