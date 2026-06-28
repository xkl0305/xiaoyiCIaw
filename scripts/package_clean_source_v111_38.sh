#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-workspace_v11138_final_clean.tar.gz}"
rm -rf repo _venv_python venv .venv .dlx_runtime .pytest_cache .mypy_cache .ruff_cache .hypothesis .openclaw/hook_state generated-images .v111_*_backup_* || true
find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find . \( -name '*.pyc' -o -name '*.pyo' -o -name '*.jsonl' \) -delete 2>/dev/null || true
rm -f README_V111_35.txt README_V111_36.txt 大龙虾_V111_35_零外接主架构收口命令.txt 大龙虾_V111_36_本地优先零外接加固命令.txt || true
rm -f scripts/apply_v111_36_local_first_hardening.py scripts/package_clean_source_v111_35.sh scripts/audit_v111_35_zero_external.py scripts/apply_v111_35_zero_external_overlay.py scripts/package_clean_source_v111_36.sh scripts/audit_v111_36_local_first_hardening.py || true
rm -f reports/V111_35* reports/V111_36* openclaw_v111_35* openclaw_v111_36* openclaw_zero_external_overlay.json || true
tar --exclude='./.git' --exclude='.git' --exclude='./repo' --exclude='repo' --exclude='./_venv_python' --exclude='_venv_python' --exclude='./venv' --exclude='venv' --exclude='./.venv' --exclude='.venv' --exclude='./.dlx_runtime' --exclude='.dlx_runtime' --exclude='./node_modules' --exclude='node_modules' --exclude='*/__pycache__' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' --exclude='./.pytest_cache' --exclude='.pytest_cache' --exclude='./.mypy_cache' --exclude='.mypy_cache' --exclude='./.ruff_cache' --exclude='.ruff_cache' --exclude='./.hypothesis' --exclude='.hypothesis' --exclude='*.jsonl' --exclude='./.openclaw/hook_state' --exclude='.openclaw/hook_state' --exclude='./generated-images' --exclude='generated-images' --exclude='./.v111_*_backup_*' --exclude='.v111_*_backup_*' --exclude='*V111_35*' --exclude='*V111_36*' --exclude='*v111_35*' --exclude='*v111_36*' -czf "$OUT" .
BAD="$(tar -tzf "$OUT" | grep -E '(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.hypothesis)(/|$)|\.(pyc|pyo|jsonl)$|(^|/)(repo|_venv_python|venv|\.venv|\.dlx_runtime)(/|$)|(^|/)\.v111_.*_backup_|README_V111_3[56]|V111_3[56]|v111_3[56]' || true)"
if [ -n "$BAD" ]; then echo "❌ V111.38 package verify failed; banned entries found:" >&2; echo "$BAD" | head -120 >&2; exit 3; fi
echo "$OUT"; echo "✅ V111.38 package verify passed: no repo/venv/pycache/old V111.35-36 residue"
