"""
Crusheart Agent OS — 统一后台任务执行器（薄封装）
委托给 background_executor 的实际实现，保持向后兼容。
"""

from .background_executor import (
    UnifiedBackgroundExecutor,
    get_executor as _get_executor,
    init_executor as _init_executor,
)

# 导出别名，保持 unified_executor 原有调用签名
def get_executor():
    return _get_executor()


def init():
    return _init_executor()
