"""StrategyRule (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

@dataclass
class StrategyRule:
    id: str
    name: str
    condition: str
    action: str
    weight: float = 1.0
    enabled: bool = True
    updated_at: float = 0.0


