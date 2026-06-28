# V111.10 Vintage Script Exclusion Result

**Timestamp:** 2026-05-05T15:47:20.722356

## Summary
2 broken smoke test scripts with dead imports moved to archive/vintage_broken_smoke_tests/

## Files Moved
| Original Path | Issue | Archive Path |
|--------------|-------|-------------|
| scripts/vintage/v56_0_to_v65_0_all_smoke.py | Imported agent_kernel.v56_to_v65_operating_agent (no longer exists) | archive/vintage_broken_smoke_tests/v56_0_to_v65_0_all_smoke.py |
| scripts/vintage/v14_0_to_v23_0_all_smoke.py | Imported agent_kernel.* modules that have been migrated/removed | archive/vintage_broken_smoke_tests/v14_0_to_v23_0_all_smoke.py |

## Decision
- decision="vintage_excluded_from_active_validation"
- These files are no longer importable by any active validation/scan
- Remaining scripts/vintage/*.py are clean (no broken imports confirmed)

## Verification
- Remaining vintage scripts checked for broken shims: 15 files verified clean
- No MIGRATION_PLACEHOLDER found in anything that is actively imported
