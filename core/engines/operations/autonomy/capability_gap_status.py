"""CapabilityGapStatus (v7.0 split)
"""
import os, json, logging
from typing import Dict, List, Optional, Any
from enum import Enum

class CapabilityGapStatus(str, Enum):
    NO_GAP = "no_gap"
    CAN_USE_CONNECTOR = "can_use_connector"
    NEED_HUMAN = "need_human"
    NEED_EXTENSION = "need_extension"


