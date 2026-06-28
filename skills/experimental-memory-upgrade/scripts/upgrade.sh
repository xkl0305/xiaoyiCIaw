#!/bin/bash
# upgrade.sh — experimental-memory-upgrade skill entry. Delegates to the shared
# experimental-memory-install orchestrator with upgrade-* modes.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[experimental-memory-upgrade] FATAL: python3 not found" >&2
    exit 99
fi

# 用户 SKILL.md 里写明 --mode=upgrade-plan / upgrade-execute / reboot
exec python3 "$SCRIPT_DIR/orchestrator.py" "$@"
