"""
auto_engines.py — 引擎自动加载&管理（转发层）
职责仅保留：扫描技能、引擎懒加载、技能注册
SkillRouter、SkillInvoker、TaskScheduler 已拆分至独立文件。
"""

import os, sys, json, importlib
from typing import Optional

# 模块级导入用 try/except 包裹，避免引擎未部署时阻止 __init__.py 加载
try:
    from core.engines.init.skill_engine import SkillRouter, SkillInvoker
except ImportError:
    SkillRouter = None
    SkillInvoker = None

try:
    from core.engines.init.task_scheduler import TaskScheduler
except ImportError:
    TaskScheduler = None

# 重新导出（保持向后兼容）
__all__ = ['SkillRouter', 'SkillInvoker', 'TaskScheduler', 'get_pipeline']

_pipeline_engines = None


def get_pipeline():
    global _pipeline_engines
    if _pipeline_engines is None:
        from core.pipeline.engines import PipelineEngines
        _pipeline_engines = PipelineEngines()
    return _pipeline_engines


def main():
    """CLI 入口: 技能扫描 / 引擎状态 / 调度器 / 全流测试"""
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "scan":
        if SkillRouter is None:
            print("❌ SkillRouter 不可用，请先部署引擎")
            return
        router = SkillRouter()
        count = router.scan()
        cats = router.get_category_summary()
        print(f"扫描 {count} 个技能")
        for cat, cnt in sorted(cats.items(), key=lambda x: x[1], reverse=True)[:6]:
            print(f"  {cat}: {cnt}个")
    elif cmd == "router-status":
        from core.engines.workflow.engine_orchestrator import Orchestrator
        print("Router:", Orchestrator().status())
    elif cmd == "test":
        if SkillRouter is None or SkillInvoker is None:
            print("❌ 引擎组件不可用，请先部署引擎")
            return
        r = SkillRouter()
        r.scan()
        print(f"技能数: {r.get_skill_count()}")
        print(f"分类数: {len(r.get_category_summary())}")
        i = SkillInvoker()
        res = i.invoke("test", "test")
        print(f"自动调用: {res}")
        s = get_pipeline()
        print(f"Pipeline: {type(s).__name__}")
    elif cmd == "scheduler":
        if TaskScheduler is None:
            print("❌ TaskScheduler 不可用，请先部署引擎")
            return
        s = TaskScheduler()
        print("Scheduler:", s.get_queue_status())
    else:
        print("用法: python3 auto_engines.py [scan|router-status|test|scheduler]")


if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    main()
