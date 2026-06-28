#!/usr/bin/env bash
set -euo pipefail
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export OFFLINE_MODE=true
export NO_EXTERNAL_API=true
export ALLOW_NETWORK=false
export NO_REAL_PAYMENT=true
export NO_REAL_SEND=true
export PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET="${PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET:-local_test_side_effect_secret}"
export MAINCHAIN_PROOF_KEY="${MAINCHAIN_PROOF_KEY:-local_test_mainchain_secret}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S scripts/security/verify_no_runtime_secret_packaged.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S scripts/security/verify_no_network_egress_profile.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_7_clean_metadata_hardening.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_6_enterprise_hardening_full_close.py
