#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-workspace_clean_source_v111_37.tar.gz}"
tar \
  --exclude='.git' \
  --exclude='repo' \
  --exclude='_venv_python' \
  --exclude='venv' \
  --exclude='.venv' \
  --exclude='.dlx_runtime' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.pytest_cache' \
  --exclude='*.jsonl' \
  --exclude='.openclaw/hook_state' \
  --exclude='generated-images' \
  --exclude='reports/vintage' \
  --exclude='scripts/vintage' \
  --exclude='scripts/legacy' \
  -czf "$OUT" .
echo "$OUT"
