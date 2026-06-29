"""
Crusheart Agent OS — 原子写工具（write-to-temp-then-rename）
防止进程崩溃导致 JSON 状态文件写半截损坏
"""

import os
import json
import tempfile

def atomic_write_json(path: str, data: dict, mode: int = 0o644):
    """原子写入 JSON 文件：写入临时文件 → 重命名覆盖"""
    tmp = None
    try:
        dirname = os.path.dirname(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        
        # 写入临时文件
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 设置权限
        os.chmod(tmp, mode)
        
        # 原子重命名（POSIX 保证 rename 是原子的）
        os.replace(tmp, path)
        return True
    except Exception:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise

def atomic_write_text(path: str, text: str, mode: int = 0o644):
    """原子写入文本文件"""
    tmp = None
    try:
        dirname = os.path.dirname(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        
        fd, tmp = tempfile.mkstemp(dir=dirname, suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        return True
    except Exception:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise
