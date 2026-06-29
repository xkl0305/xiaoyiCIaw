"""AutonomyCycleResult (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class AutonomyCycleResult:
    run_id: str
    goal: str
    status: str
    constitution_decision: Dict
    capability_gap: Dict
    quality_score: float
    trace_events: int
    next_action: str
    recovery_entries: int
    strategy_updates: int
    details: Dict


