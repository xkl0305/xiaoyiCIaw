#!/usr/bin/env bash
set -euo pipefail
command -v podman >/dev/null 2>&1 && echo runtime=podman && exit 0
command -v docker >/dev/null 2>&1 && echo runtime=docker && exit 0
echo "No podman/docker runtime found. Install rootless Podman preferred." >&2
exit 2
