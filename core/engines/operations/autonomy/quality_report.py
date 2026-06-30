"""QualityReport (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

@dataclass
class QualityReport:
    id: str
    run_id: str
    goal: str
    completeness: float
    safety: float
    usefulness: float
    efficiency: float
    final_score: float
    passed: bool
    issues: List[str]


