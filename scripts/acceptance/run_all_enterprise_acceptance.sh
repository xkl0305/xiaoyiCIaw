#!/usr/bin/env bash
set -euo pipefail
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export OFFLINE_MODE=true
export NO_EXTERNAL_API=true
export ALLOW_NETWORK=false
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.
: "${PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET:=local_test_side_effect_secret}"
: "${MAINCHAIN_PROOF_KEY:=local_test_mainchain_secret}"
export PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET MAINCHAIN_PROOF_KEY
python3 scripts/acceptance/enterprise_acceptance_runner.py
