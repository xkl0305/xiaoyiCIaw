"""
self_check.py — #48: __main__ 测试规范化共享工具

用法（在任意引擎 __main__ 中使用）：
  if __name__ == "__main__":
      import sys
      from core.engines.init.self_check import run_self_check
      run_self_check(__name__, __file__,
          imports=["os", "json"],
          constants=[("WORKSPACE", lambda: os.path.isdir),
                     ("BEIJING_TZ", lambda: hasattr(_, "tzname"))],
      )

或通过 CLI 批量执行：
  python3 -m core.engines.init.self_check --all
  python3 -m core.engines.init.self_check core/engines/init/config_loader.py
"""

import argparse
import importlib
import inspect
import logging
import os
import sys
import traceback
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 共享自检函数
# ═══════════════════════════════════════════════════════════════

def run_self_check(
    module_name: str,
    module_file: str,
    imports: List[str] = None,
    constants: List[Tuple[str, Callable]] = None,
    custom_checks: List[Tuple[str, Callable]] = None,
    verbose: bool = False,
) -> int:
    """
    通用自检入口，返回 exit code（0=全部通过, 1=有失败）

    Args:
        module_name: __name__ (调用时传 __name__)
        module_file: __file__ (调用时传 __file__)
        imports: 要验证的关键模块列表，如 ["os", "json"]
        constants: 要验证的常量列表，如 [("WORKSPACE", lambda: os.path.isdir)]
        custom_checks: 自定义检查列表，如 [("can init", lambda: MyClass())]
        verbose: 是否详细输出

    Returns:
        exit code
    """
    checks: List[Tuple[str, Callable[[], bool]]] = []
    all_pass = True
    sep = "=" * 56
    short_name = os.path.splitext(os.path.basename(module_file))[0]

    print(sep)
    print(f"  🔍 Self-Check: {short_name} ({module_file})")
    print(sep)

    # ── 1. import 检查 ──
    if imports:
        for imp_name in imports:
            try:
                importlib.import_module(imp_name)
                if verbose:
                    print(f"  ✅ import {imp_name}")
            except Exception as e:
                print(f"  ❌ import {imp_name}: {e}")
                all_pass = False

    # ── 2. 常量检查 ──
    if constants:
        # 加载模块
        mod = sys.modules.get(module_name)
        if mod is None:
            try:
                mod = importlib.import_module(module_name)
            except Exception as e:
                print(f"  ❌ 模块加载失败 {module_name}: {e}")
                return 1

        for const_name, validate_fn in constants:
            value = getattr(mod, const_name, None)
            if value is None:
                print(f"  ❌ 常量 {const_name}: 未定义或为空")
                all_pass = False
            else:
                try:
                    valid = validate_fn(value)
                    if verbose or not valid:
                        status = "✅" if valid else "❌"
                        print(f"  {status} 常量 {const_name}: {repr(value)[:60]}")
                    if not valid:
                        all_pass = False
                except Exception as e:
                    print(f"  ❌ 常量 {const_name} 验证失败: {e}")
                    all_pass = False

    # ── 3. 自定义检查 ──
    if custom_checks:
        for check_name, fn in custom_checks:
            try:
                fn()
                if verbose:
                    print(f"  ✅ {check_name}")
            except Exception as e:
                print(f"  ❌ {check_name}: {e}")
                if verbose:
                    traceback.print_exc()
                all_pass = False

    print(sep)
    print(f"  结果: {'✅ 全部通过' if all_pass else '❌ 有失败'}")
    print(sep)
    return 0 if all_pass else 1


# ═══════════════════════════════════════════════════════════════
# 批量自检模式：扫描所有引擎目录
# ═══════════════════════════════════════════════════════════════

def scan_all_engines() -> Dict[str, dict]:
    """扫描 core/engines/ 下所有 __main__ 入口文件，批量执行基础检查"""
    WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
    engine_dir = os.path.join(WORKSPACE, "core", "engines")
    results = {}

    for root, dirs, files in os.walk(engine_dir):
        for fn in files:
            if not fn.endswith(".py") or "__pycache__" in root:
                continue
            fpath = os.path.join(root, fn)
            relpath = os.path.relpath(fpath, WORKSPACE)
            mod_name = relpath.replace("/", ".").replace(".py", "")

            # 检查是否有 __main__
            with open(fpath, encoding="utf-8", errors="replace") as f:
                content = f.read()
            if "__main__" not in content:
                continue

            # 基础检查
            checks = []
            all_pass = True

            # import 检查
            try:
                importlib.import_module(mod_name)
                checks.append({"name": "import", "status": "pass"})
            except Exception as e:
                checks.append({"name": "import", "status": "fail", "reason": str(e)[:100]})
                all_pass = False

            results[relpath] = {"status": "pass" if all_pass else "fail", "checks": checks}

    return results


def main():
    parser = argparse.ArgumentParser(description="Self-Check: 引擎自检工具")
    parser.add_argument("--all", action="store_true", help="扫描所有引擎文件")
    parser.add_argument("--module", type=str, help="指定模块路径，如 core.engines.init.config_loader")
    parser.add_argument("files", nargs="*", help="要检查的文件路径")
    args = parser.parse_args()

    if args.all:
        results = scan_all_engines()
        total = len(results)
        passed = sum(1 for r in results.values() if r["status"] == "pass")
        failed = total - passed

        print(f"\n{'=' * 60}")
        print(f"  📊 引擎健康度扫描结果 ({total} 个文件)")
        print(f"{'=' * 60}")
        for fpath, result in sorted(results.items()):
            icon = "✅" if result["status"] == "pass" else "❌"
            print(f"  {icon} {fpath}")
            for check in result["checks"]:
                if check["status"] != "pass":
                    print(f"       ❌ {check['name']}: {check.get('reason', '')}")
        print(f"\n  总计: {total} | ✅ {passed} | ❌ {failed}")
        return 0 if failed == 0 else 1

    elif args.module:
        try:
            mod = importlib.import_module(args.module)
            print(f"✅ 模块 {args.module} 导入成功")
            return 0
        except Exception as e:
            print(f"❌ 模块 {args.module} 导入失败: {e}")
            return 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
