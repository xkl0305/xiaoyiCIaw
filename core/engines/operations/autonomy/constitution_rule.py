"""ConstitutionRule (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class ConstitutionRule:
    id: str
    name: str
    pattern: str
    severity: RuleSeverity
    reason: str
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
