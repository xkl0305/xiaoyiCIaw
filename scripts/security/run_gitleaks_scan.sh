#!/usr/bin/env bash
set -euo pipefail
if ! command -v gitleaks >/dev/null 2>&1; then
  echo '{"overall":"skipped","reason":"gitleaks_not_installed"}'
  exit 0
fi
gitleaks detect --no-git --redact --source .
