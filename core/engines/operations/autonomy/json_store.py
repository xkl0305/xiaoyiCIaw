"""JsonStore (v7.0 split)
"""
import os, json, logging
import threading
from typing import Dict, List, Optional, Any
from enum import Enum

class JsonStore:
    """简单的 JSON 文件存储"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def read(self, default: Any = None) -> list:
        if not os.path.exists(self.path):
            return default or []
        try:
            with open(self.path) as f:
                return json.load(f)
        except Exception:
            logging.exception("[autonomy_cycle.py] suppressed")
            return default or []

    def write(self, data: list):
        with open(self.path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def append(self, item: dict):
        with self._lock:
            data = self.read()
            data.append(item)
            self.write(data)


# ================================================================
# 1. 枚举类型
# ================================================================

