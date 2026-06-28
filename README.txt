V111.52.7_CLEAN_METADATA_HARDENING_FINAL

用途：在 V111.52.6 强收口基础上做最后清洁和元数据一致性修复。

修复内容：
1. apply 后自动删除 overlay_payload*，避免覆盖载荷残留到正式工作区。
2. release_manifest / hooks manifest / version.json / openclaw.json 统一到 V111.52.7。
3. 统一严格本地/私网语义：ONLINE_MODE=false，ALLOW_NETWORK=false，NO_EXTERNAL_API=true。
4. 将 connected runtime 明确为 local_private_runtime_always_connected_no_external_egress，不再和“外部在线”混淆。
5. 修正 profiles/always_connected_enterprise.toml 的 profile_name。
6. 新增 verify_v111_52_7_clean_metadata_hardening.py，强制 package_clean_check 全量干净。

应用：
python3 scripts/apply_v111_52_7_clean_metadata_hardening.py

验收：
export PERSONAL_OS_SIDE_EFFECT_PROOF_DEFAULT_SECRET=local_test_side_effect_secret
export MAINCHAIN_PROOF_KEY=local_test_mainchain_secret
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_7_clean_metadata_hardening.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_6_enterprise_hardening_full_close.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S scripts/security/verify_no_network_egress_profile.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S scripts/security/verify_no_runtime_secret_packaged.py
