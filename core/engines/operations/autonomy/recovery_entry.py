"""RecoveryEntry (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class RecoveryEntry:
    id: str
    run_id: str
    action: str
    checkpoint: Dict
    rollback_plan: str = ""
    reversible: bool = True
    created_at: float = 0.0


