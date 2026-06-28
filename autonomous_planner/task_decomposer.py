
from __future__ import annotations
import importlib
from typing import Any, Dict
_CANDIDATE_MODULES = ['infrastructure.task_manager','orchestration.task_orchestrator','execution.task_runtime.task_manager']
def _call(action: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    for mod_name in _CANDIDATE_MODULES:
        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, action, None)
            if callable(fn): return fn(*args, **kwargs)
        except Exception: continue
    return {'status':'dry_run_stub','action':action,'reason':'legacy autonomous_planner shim; no concrete task manager implementation found','args':list(args),'kwargs':kwargs}
def pause_task(*args: Any, **kwargs: Any) -> Dict[str, Any]: return _call('pause_task', *args, **kwargs)
def cancel_task(*args: Any, **kwargs: Any) -> Dict[str, Any]: return _call('cancel_task', *args, **kwargs)
def retry_task(*args: Any, **kwargs: Any) -> Dict[str, Any]: return _call('retry_task', *args, **kwargs)
def resume_task(*args: Any, **kwargs: Any) -> Dict[str, Any]: return _call('resume_task', *args, **kwargs)
def schedule_task(*args: Any, **kwargs: Any) -> Dict[str, Any]: return _call('schedule_task', *args, **kwargs)
