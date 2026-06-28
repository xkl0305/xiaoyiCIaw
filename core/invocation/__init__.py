"""Invocation Status Explainer - 调用状态解释器 (shim)"""

from typing import Dict, Any, Optional


def explain_status(invocation_id: str | None = None) -> Dict[str, Any]:
    """解释调用状态
    
    Args:
        invocation_id: 调用ID
        
    Returns:
        状态解释
    """
    return {
        "status": "dry_run",
        "message": "explain_status is planned feature",
        "invocation_id": invocation_id,
        "side_effects": False
    }


def confirm_invocation(*args, **kwargs):
    """确认调用 (shim)
    
    先尝试从 execution.capabilities 加载真实实现，
    不可用时回退到 dry_run 模式。
    """
    try:
        from execution.capabilities.confirm_invocation import confirm_invocation as _impl
        return _impl(*args, **kwargs)
    except ImportError:
        pass
    try:
        from infrastructure.platform_adapter.invocation_ledger import confirm_invocation as _impl
        return _impl(*args, **kwargs)
    except ImportError:
        pass
    return {
        'status': 'confirmation_required',
        'action': 'confirm_invocation',
        'real_execution_allowed': False,
        'args': list(args),
        'kwargs': kwargs
    }
