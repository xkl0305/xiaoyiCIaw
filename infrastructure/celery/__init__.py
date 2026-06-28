# infrastructure/celery/__init__.py
from infrastructure.offline_runtime_guard import activate as _openclaw_offline_guard_activate; _openclaw_offline_guard_activate()
"""
Celery 模块
"""

from .celery_app import app, execute_task, send_scheduled_message, scan_scheduled_tasks

__all__ = ["app", "execute_task", "send_scheduled_message", "scan_scheduled_tasks"]
