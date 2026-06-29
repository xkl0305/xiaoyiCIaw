"""
startup_health_check.py — #50: 启动自检 & 健康度仪表盘

轻量包装：组合 session_bootstrap 的启动检查 + health_check 的健康评分，
输出结构化 JSON 报告。

用法：
  python3 -m core.engines.init.startup_health_check           # 完整自检
  python3 -m core.engines.init.startup_health_check --brief   # 仅概要
  python3 -m core.engines.init.startup_health_check --json    # JSON 输出
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


def run_startup_health_check() -> Dict[str, Any]:
    """
    完整启动自检，返回结构化报告

    检查项：
      1. 引擎状态 (session_bootstrap.check_state 的精简版)
      2. 核心 import 可用性
      3. 健康评分 (health_check.get_health_score)
      4. 系统组件完整性
    """
    start = time.time()
    report: Dict[str, Any] = {
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        "workspace": WORKSPACE,
        "status": "pass",
        "checks": {},
    }

    if WORKSPACE not in sys.path:
        sys.path.insert(0, WORKSPACE)

    # ── 1. 引擎状态检查 ──
    state_check = {"name": "engine_state", "status": "skip"}
    try:
        ENGINE_STATE = os.path.join(WORKSPACE, ".state", ".engine_state.json")
        if os.path.exists(ENGINE_STATE):
            with open(ENGINE_STATE, encoding="utf-8") as f:
                state = json.load(f)
            state_ready = state.get("status") == "ready"
            state_check = {
                "name": "engine_state",
                "status": "pass" if state_ready else "fail",
                "total": state.get("total", 0),
                "ready": state.get("success", 0) if state_ready else 0,
                "detail": "ready" if state_ready else f"status={state.get('status')}",
            }
        else:
            state_check = {"name": "engine_state", "status": "warn", "detail": "未找到引擎状态文件，可能首次启动"}
    except Exception as e:
        state_check = {"name": "engine_state", "status": "fail", "detail": str(e)[:80]}

    report["checks"]["engine_state"] = state_check

    # ── 2. 核心模块 import 检查 ──
    core_modules = [
        "core.engines.init.config_loader",
        "core.engines.init.engine_factory",
        "core.engines.quality.judge_engine",
        "core.engines.quality.circuit_breaker",
        "core.engines.memory.auto_memory",
        "core.engines.tools.mutex_engine",
        "core.engines.hooks.self_evolution_engine",
        "core.engines.workflow.workflow_engine",
        "core.engines.operations.health_check",
        "core.engines.init.session_bootstrap",
        "core.engines.hooks.hook_engine",
        "core.engines.quality.anti_fake_validator",
        "core.engines.init.lazy_load_enforcer",
    ]

    import_results = []
    import_ok = True
    for mod_path in core_modules:
        try:
            __import__(mod_path)
            import_results.append({"module": mod_path, "status": "pass"})
        except Exception as e:
            import_results.append({"module": mod_path, "status": "fail", "detail": str(e)[:80]})
            import_ok = False

    report["checks"]["imports"] = {
        "name": "core_imports",
        "status": "pass" if import_ok else "fail",
        "total": len(core_modules),
        "pass": sum(1 for r in import_results if r["status"] == "pass"),
        "fail": sum(1 for r in import_results if r["status"] == "fail"),
        "modules": import_results,
    }

    # ── 3. 健康评分 (health_check) ──
    health_report: Dict[str, Any] = {"name": "health_score", "status": "skip"}
    try:
        from core.engines.operations.health_check import get_health_score, get_health_score_report

        score = get_health_score()
        if isinstance(score, dict):
            problems = score.get("problems", [])
            health_score_pct = score.get("health_score", 0.0)

            health_report = {
                "name": "health_score",
                "status": "pass" if health_score_pct >= 0.8 else ("warn" if health_score_pct >= 0.5 else "fail"),
                "health_score": round(health_score_pct, 3),
                "problem_count": len(problems),
                "problems": [
                    {"message": p.get("message", str(p)[:80]) if isinstance(p, dict) else str(p)[:80],
                     "severity": p.get("severity", "unknown") if isinstance(p, dict) else "unknown"}
                    for p in problems[:10]
                ],
            }
        else:
            health_report = {"name": "health_score", "status": "pass", "score": str(score)}
    except ImportError:
        health_report = {"name": "health_score", "status": "warn", "detail": "health_check 模块未安装"}
    except Exception as e:
        health_report = {"name": "health_score", "status": "fail", "detail": str(e)[:80]}

    report["checks"]["health_score"] = health_report

    # ── 4. 系统组件完整性 ──
    component_check = {"name": "system_integrity", "status": "pass"}
    try:
        core_dirs = [
            "core/engines/init",
            "core/engines/memory",
            "core/engines/quality",
            "core/engines/operations",
            "core/engines/workflow",
            "core/engines/hooks",
            "core/engines/tools",
            "core/engines/compat",
        ]
        missing = []
        for d in core_dirs:
            path = os.path.join(WORKSPACE, d)
            if not os.path.isdir(path):
                missing.append(d)

        component_check = {
            "name": "system_integrity",
            "status": "pass" if not missing else "fail",
            "total_dirs": len(core_dirs),
            "missing_dirs": missing,
        }
    except Exception as e:
        component_check = {"name": "system_integrity", "status": "fail", "detail": str(e)[:80]}

    report["checks"]["system_integrity"] = component_check

    # ── 汇总 ──
    elapsed = time.time() - start
    statuses = [c.get("status", "skip") for c in report["checks"].values()]
    if any(s == "fail" for s in statuses):
        report["status"] = "fail"
    elif any(s == "warn" for s in statuses):
        report["status"] = "degraded"
    else:
        report["status"] = "pass"

    report["summary"] = {
        "total_checks": len(report["checks"]),
        "pass": sum(1 for s in statuses if s == "pass"),
        "warn": sum(1 for s in statuses if s == "warn"),
        "fail": sum(1 for s in statuses if s == "fail"),
        "elapsed_ms": round(elapsed * 1000, 1),
    }

    return report


def print_report(report: Dict[str, Any], brief: bool = False):
    """打印可读的健康报告"""
    status_icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}
    icon = status_icons.get(report["status"], "❓")
    header = f"{'=' * 50}"
    print(f"\n{header}")
    print(f"  {icon} 系统健康度: {report['status'].upper()}")
    print(f"  🕐 {report['timestamp']}")
    print(f"  📁 {report['workspace']}")
    print(f"{header}")

    for name, check in sorted(report["checks"].items()):
        if brief and check.get("status") == "pass":
            continue
        ci = status_icons.get(check.get("status", "skip"), "❓")
        detail = ""
        if check.get("detail"):
            detail = f" — {check['detail']}"
        elif "health_score" in check:
            detail = f" — score={check.get('health_score', 0):.1%}"
            if check.get("problem_count", 0) > 0:
                detail += f", problems={check['problem_count']}"
        elif check.get("pass") is not None and check.get("total"):
            detail = f" — {check['pass']}/{check['total']}"
            if check.get("fail", 0) > 0:
                detail += f" ({check['fail']} failed)"

        print(f"  {ci} {check.get('name', name)}{detail}")

        # Show failure details
        if check.get("modules") and check["status"] != "pass":
            for m in check.get("modules", []):
                if m["status"] == "fail":
                    print(f"       ❌ {m['module']}: {m.get('detail', '')}")
        if check.get("problems"):
            for p in check["problems"][:3]:
                sev = p.get("severity", "?")
                print(f"       ⚠️ [{sev}] {p['message'][:80]}")

    print(f"{header}")
    s = report.get("summary", {})
    print(f"  总计: {s.get('total_checks', '?')} | "
          f"✅ {s.get('pass', 0)} | "
          f"⚠️ {s.get('warn', 0)} | "
          f"❌ {s.get('fail', 0)} | "
          f"⏱ {s.get('elapsed_ms', '?')}ms")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="启动自检 & 健康度仪表盘")
    parser.add_argument("--brief", action="store_true", help="仅显示异常项")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    report = run_startup_health_check()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print_report(report, brief=args.brief)

    return 0 if report["status"] == "pass" else (1 if report["status"] == "fail" else 0)


if __name__ == "__main__":
    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=[("run health check", lambda: run_startup_health_check())],
            verbose=True))

    sys.exit(main())
