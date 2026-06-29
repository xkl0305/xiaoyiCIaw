"""Autonomy shared (v7.0 split)
"""
"""
Crusheart Agent OS — 自治周期引擎 v1.0
Crusheart Agent OS — 自治周期引擎
集成 5 个模块：
  1. AutonomyOrchestrator — 7阶段自治周期编排（memory→world→gap→approval→quality→strategy→continuous）
  2. ConstitutionKernel — 动态规则引擎（allow/block/approval，正则匹配，规则热添加）
  3. RecoveryLedger — 检查点+回滚计划交易账本
  4. StrategyEvolver — 质量驱动策略自动演进
  5. ContinuousTaskRunner — 持久化任务注册表
集成点：Orchestrator 升级为 CycleRouter（7阶段自治周期编排）
"""

import os, re, json, threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from hashlib import sha256
import logging

from core.engines.memory.exec_logger import log_execution
BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_DIR = os.path.join(WORKSPACE, ".autonomy_state")
os.makedirs(STATE_DIR, exist_ok=True)


# ================================================================
# 工具函数
# ================================================================

def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{sha256(os.urandom(8)).hexdigest()[:16]}"


def now_ts() -> float:
    return datetime.now(BEIJING_TZ).timestamp()


def _ts_to_str(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=BEIJING_TZ).isoformat()


