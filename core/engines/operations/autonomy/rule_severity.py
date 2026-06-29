"""RuleSeverity (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class RuleSeverity(str, Enum):
    ALLOW = "allow"
    APPROVAL_REQUIRED = "approval_required"
    BLOCK = "block"
    INFO = "info"


# ================================================================
# 2. ConstitutionKernel — 规则引擎
# ================================================================

@dataclass
