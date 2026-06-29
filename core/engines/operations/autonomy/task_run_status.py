"""TaskRunStatus (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class TaskRunStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    SKIPPED = "skipped"


