"""Change Review - 变更审查 (shim)"""

from typing import Dict, Any


def change_review(change_id: str | None = None) -> Dict[str, Any]:
    """变更审查
    
    Args:
        change_id: 变更ID
        
    Returns:
        审查结果
    """
    return {
        "status": "dry_run",
        "message": "change_review is planned feature",
        "change_id": change_id,
        "approved": False,
        "side_effects": False
    }


# ---- V111.35 compatibility route shims ----
def preview_side_effect(*args, **kwargs):
    try:
        from execution.capabilities.preview_side_effect import preview_side_effect as _impl
        return _impl(*args, **kwargs)
    except Exception:
        return {'status':'preview_only','action':'preview_side_effect','allowed':False,'requires_approval':True,'args':list(args),'kwargs':kwargs}


def approve_action(*args, **kwargs):
    try:
        from execution.capabilities.approve_action import approve_action as _impl
        return _impl(*args, **kwargs)
    except Exception:
        return {'status':'approval_recorded_as_dry_run','action':'approve_action','args':list(args),'kwargs':kwargs}
