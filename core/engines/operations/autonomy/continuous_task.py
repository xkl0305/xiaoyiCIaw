"""ContinuousTask (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class ContinuousTask:
    id: str
    title: str
    goal: str
    cadence: str
    status: str = "created"
    last_run_at: Optional[float] = None
    next_run_hint: str = ""
    metadata: Dict = field(default_factory=dict)


