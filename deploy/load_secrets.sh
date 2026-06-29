#!/usr/bin/env bash
set -euo pipefail
enc_file="${1:-secrets/runtime.enc.yaml}"
if ! command -v sops >/dev/null 2>&1; then
  echo "sops_not_installed" >&2
  exit 2
fi
if ! command -v yq >/dev/null 2>&1; then
  echo "yq_not_installed" >&2
  exit 2
fi
tmpdir="$(mktemp -d /dev/shm/xiaoyi-secrets.XXXXXX)"
chmod 700 "$tmpdir"
cleanup(){ rm -rf "$tmpdir"; }
trap cleanup EXIT
sops decrypt --output "$tmpdir/runtime.yaml" "$enc_file"
export MAINCHAIN_PROOF_KEY="$(yq '.mainchain_proof_key' "$tmpdir/runtime.yaml")"
export PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET="$(yq '.side_effect_proof_key' "$tmpdir/runtime.yaml")"
export LOCAL_PROVIDER_AUTH="$(yq '.local_provider_auth' "$tmpdir/runtime.yaml")"
shift || true
exec "$@"
