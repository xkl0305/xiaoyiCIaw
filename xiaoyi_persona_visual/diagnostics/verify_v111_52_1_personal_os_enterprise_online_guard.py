from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TARGETS = [
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "__init__.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "runtime_profile.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "offline_profile.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "runtime_secret_provider.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "side_effect_proof.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "side_effect_registry.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "action_guard.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "observability_event_bus.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "local_capability_registry.py",
    PROJECT_ROOT / "core" / "personal_os_enterprise" / "acceptance_matrix_runner.py",
    PROJECT_ROOT / "infrastructure" / "packaging" / "source_runtime_boundary.py",
]


def main() -> int:
    checks = {}
    missing = [str(p.relative_to(PROJECT_ROOT)) for p in TARGETS if not p.exists()]
    checks["files_present"] = not missing
    checks["missing_files"] = missing

    compile_errors = []
    for p in TARGETS:
        if p.exists():
            try:
                py_compile.compile(str(p), doraise=True)
            except Exception as exc:
                compile_errors.append(f"{p.relative_to(PROJECT_ROOT)}: {exc}")
    checks["py_compile_ok"] = not compile_errors
    checks["compile_errors"] = compile_errors

    try:
        from core.personal_os_enterprise.acceptance_matrix_runner import run_acceptance_matrix
        result = run_acceptance_matrix(root=PROJECT_ROOT)
        checks["acceptance_matrix"] = result
        checks["acceptance_matrix_passed"] = result.get("overall") == "passed"
    except Exception as exc:
        checks["acceptance_matrix"] = {"overall": "failed", "error": repr(exc)}
        checks["acceptance_matrix_passed"] = False

    try:
        openclaw = json.loads((PROJECT_ROOT / "openclaw.json").read_text(encoding="utf-8")) if (PROJECT_ROOT / "openclaw.json").exists() else {}
        runtime = openclaw.get("runtime", {}) if isinstance(openclaw, dict) else {}
        poe = openclaw.get("personalOSEnterprise", {}) if isinstance(openclaw, dict) else {}
        checks["openclaw_online_mode"] = runtime.get("ONLINE_MODE") is True and runtime.get("ALLOW_NETWORK") is True and runtime.get("OFFLINE_MODE") is False
        checks["openclaw_enterprise_version"] = poe.get("version") == "V111.52.1_PERSONAL_OS_ENTERPRISE_ONLINE_GUARD"
    except Exception as exc:
        checks["openclaw_online_mode"] = False
        checks["openclaw_enterprise_version"] = False
        checks["openclaw_error"] = repr(exc)

    overall = bool(checks.get("files_present") and checks.get("py_compile_ok") and checks.get("acceptance_matrix_passed") and checks.get("openclaw_online_mode") and checks.get("openclaw_enterprise_version"))
    output = {"overall": "passed" if overall else "failed", "version": "V111.52.1_PERSONAL_OS_ENTERPRISE_ONLINE_GUARD", "checks": checks}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
