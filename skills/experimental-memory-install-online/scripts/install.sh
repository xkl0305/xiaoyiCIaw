#!/bin/bash
# install.sh — experimental-memory-install-online Bash entry.
#
# This entry is intentionally independent from experimental-memory-install.
# It dispatches only to the online installer in this skill directory.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CELIA_CONFIG_DIR="${CELIA_CONFIG_DIR:-/home/sandbox/.openclaw}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[experimental-memory-install-online] FATAL: python3 not found" >&2
    echo "[experimental-memory-install-online] need Python 3.11+ or tomli" >&2
    exit 99
fi

exec python3 "$SCRIPT_DIR/remote_install.py" --platform=celiaclaw "$@"
