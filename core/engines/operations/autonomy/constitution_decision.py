"""ConstitutionDecision (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

@dataclass
class ConstitutionDecision:
    status: str  # allow / approval_required / block
    matched_rules: List[str]
    reason: str
    risk_level: str = "L1"


