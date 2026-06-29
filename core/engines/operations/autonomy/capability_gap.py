"""CapabilityGap (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class CapabilityGap:
    id: str
    requested_goal: str
    required_capabilities: List[str]
    missing_capabilities: List[str]
    status: CapabilityGapStatus
    explanation: str


