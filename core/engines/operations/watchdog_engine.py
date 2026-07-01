"""
Crusheart Agent OS — WatchdogEngine 看门狗引擎 v1.0
===================================================

功能：
  1. Pipeline 进度检测 — 主会话各阶段插桩 tick(stage_name)，看门狗独立线程监听
  2. 分级响应 — 超时后逐级升级：
     - LEVEL1: 记录告警日志，尝试重试当前阶段（1次）
     - LEVEL2: 跳过卡死阶段，继续执行后续阶段（降级运行）
     - LEVEL3: 紧急重启主 pipeline（硬恢复）
     - LEVEL4: 上报致命异常，标记系统不可用
  3. 可配置超时窗口 — 不同阶段配置不同容忍度
  4. 与 circuit_breaker + degradation_chain 互补不冲突

集成点：
  - pipeline/engines.py → 每个 check_xxx 调用 tick() 
  - pipeline/orchestrator.py → run_pipeline 开始/结束 tick()
  - 所有耗时工具调用 → tick()
"""

import os
import sys
import json
import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any

# ── 路径 ──
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

BEIJING_TZ = timezone(timedelta(hours=8))
STATE_FILE = os.path.join(WORKSPACE, ".state", "watchdog_state.json")

logger = logging.getLogger("watchdog")

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

# 各阶段的默认超时（秒）
DEFAULT_STAGE_TIMEOUTS = {
    "pipeline": 30.0,          # 整个 pipeline 总超时
    "stage0_engines": 10.0,    # 引擎状态检测
    "stage1_dual_mode": 5.0,   # 双模式分类
    "stage2_skill_match": 8.0, # 技能匹配
    "stage3_anti_fake": 5.0,   # 防幻觉
    "stage4_engine_route": 5.0,
    "stage5_session_state": 5.0,
    "stage6_memory_align": 5.0,
    "stage7_self_reflection": 5.0,
    "hook_pre": 8.0,           # 前置钩子
    "memory_retrieval": 5.0,   # 记忆检索
    "anti_fake_validation": 10.0,
    "tool_execution": 30.0,    # 工具执行
    "evolution_eval": 10.0,
    "background_task": 60.0,   # 后台子任务监控
}

# 看门狗线程心跳间隔（秒）
WATCHDOG_HEARTBEAT = 1.0

# 等级定义
LEVEL_NONE = 0
LEVEL_LOG = 1        # 记录日志
LEVEL_RETRY = 2      # 重试一次
LEVEL_SKIP = 3       # 跳过阶段
LEVEL_RESTART = 4    # 重启 pipeline
LEVEL_FATAL = 5      # 致命，标记不可用

LEVEL_NAMES = {
    LEVEL_NONE: "正常",
    LEVEL_LOG: "日志告警",
    LEVEL_RETRY: "重试",
    LEVEL_SKIP: "跳过阶段",
    LEVEL_RESTART: "重启 Pipeline",
    LEVEL_FATAL: "致命异常",
}

# ═══════════════════════════════════════════════════════════
# WatchdogEngine
# ═══════════════════════════════════════════════════════════

class WatchdogEngine:
    """
    看门狗引擎。
    
    工作方式：
    - 外部在 pipeline 每个阶段结束时调 tick(stage_name)
    - 看门狗独立线程每秒检查所有活跃阶段的最后 tick 时间
    - 超时后按级别升级响应
    """

    def __init__(self, custom_timeouts: Optional[Dict[str, float]] = None):
        self._timeouts: Dict[str, float] = {**DEFAULT_STAGE_TIMEOUTS, **(custom_timeouts or {})}
        
        # {stage_name: {"last_tick": float, "level": int, "retried": bool, "skipped": bool}}
        self._tick_log: Dict[str, dict] = {}
        self._started_stages: set = set()  # 已启动的阶段
        self._lock = threading.Lock()
        
        # 守护线程
        self._running = False
        self._watchdog_thread: Optional[threading.Thread] = None
        
        # 回调 — 外部注册
        self._on_level: Dict[int, List[Callable]] = {
            LEVEL_LOG: [],
            LEVEL_RETRY: [],
            LEVEL_SKIP: [],
            LEVEL_RESTART: [],
            LEVEL_FATAL: [],
        }
        
        # 历史记录
        self._history: List[dict] = []
        self._max_history = 100
        
        # 全局中断标记
        self._pipeline_blocked = False
        self._fatal_error: Optional[str] = None

    # ── 生命周期 ──

    def start(self):
        if self._running:
            return False
        self._running = True
        self._watchdog_thread = threading.Thread(
            target=self._loop, daemon=True,
            name="crusheart-watchdog"
        )
        self._watchdog_thread.start()
        return True

    def stop(self):
        self._running = False
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=3)
            self._watchdog_thread = None

    # ── 核心 API ──

    def tick(self, stage_name: str):
        """
        标记阶段进度。每次调用刷新该阶段的超时计时。
        stages 可按阶段名打点，也可按 {阶段名}.{子阶段} 层级打点。
        """
        now = time.monotonic()
        with self._lock:
            if stage_name not in self._tick_log:
                self._tick_log[stage_name] = {
                    "first_tick": now,
                    "last_tick": now,
                    "tick_count": 1,
                    "level": LEVEL_NONE,
                    "retried": False,
                    "skipped": False,
                    "total_elapsed": 0.0,
                }
                self._started_stages.add(stage_name)
            else:
                entry = self._tick_log[stage_name]
                elapsed = now - entry["last_tick"]
                entry["last_tick"] = now
                entry["tick_count"] += 1
                entry["total_elapsed"] += elapsed

    def mark_complete(self, stage_name: str):
        """标记阶段正常完成，并自动完成所有子阶段"""
        with self._lock:
            prefix = stage_name + "."
            # 如果是 pipeline 完成，标记所有未完成阶段
            if stage_name == "pipeline":
                for entry in self._tick_log.values():
                    entry["level"] = LEVEL_NONE
                    entry["completed"] = True
                    entry["completed_at"] = time.monotonic()
                return
            # 标记该阶段及其所有子阶段
            for name, entry in list(self._tick_log.items()):
                if name == stage_name or name.startswith(prefix):
                    entry["level"] = LEVEL_NONE
                    entry["completed"] = True
                    entry["completed_at"] = time.monotonic()

    def mark_skipped(self, stage_name: str, reason: str = ""):
        """标记阶段被跳过"""
        with self._lock:
            entry = self._tick_log.get(stage_name)
            if entry:
                entry["skipped"] = True
                entry["skip_reason"] = reason
                entry["level"] = LEVEL_NONE

    def is_blocked(self) -> bool:
        """pipeline 是否被看门狗标记为阻断"""
        return self._pipeline_blocked

    def get_fatal_error(self) -> Optional[str]:
        return self._fatal_error

    def reset(self):
        """重置所有看门狗状态（新 pipeline 开始前）"""
        with self._lock:
            self._tick_log.clear()
            self._started_stages.clear()
            self._pipeline_blocked = False
            self._fatal_error = None

    # ── 注册回调 ──

    def on_level(self, level: int, callback: Callable[[str, int], Any]):
        """注册某级别的回调。callback(stage_name, current_level)"""
        if level in self._on_level:
            self._on_level[level].append(callback)

    def register_level_handler(self, level: int, callback: Callable):
        """同 on_level，别名"""
        self.on_level(level, callback)

    def remove_handler(self, level: int, callback: Callable):
        if level in self._on_level and callback in self._on_level[level]:
            self._on_level[level].remove(callback)

    # ── 状态查询 ──

    def get_status(self) -> dict:
        with self._lock:
            stages = {}
            for name, entry in self._tick_log.items():
                age = time.monotonic() - entry["last_tick"]
                stages[name] = {
                    "age_s": round(age, 1),
                    "level": entry["level"],
                    "level_name": LEVEL_NAMES.get(entry["level"], "未知"),
                    "tick_count": entry["tick_count"],
                    "retried": entry.get("retried", False),
                    "skipped": entry.get("skipped", False),
                    "completed": entry.get("completed", False),
                }
            return {
                "running": self._running,
                "pipeline_blocked": self._pipeline_blocked,
                "fatal_error": self._fatal_error,
                "active_stages": len([s for s in stages.values() if not s.get("completed")]),
                "stages": stages,
                "history_count": len(self._history),
            }

    def get_stage_info(self, stage_name: str) -> Optional[dict]:
        with self._lock:
            entry = self._tick_log.get(stage_name)
            if not entry:
                return None
            age = time.monotonic() - entry["last_tick"]
            return {
                "stage": stage_name,
                "age_s": round(age, 1),
                "level": entry["level"],
                "level_name": LEVEL_NAMES.get(entry["level"], "未知"),
                "tick_count": entry["tick_count"],
                "retried": entry.get("retried", False),
                "skipped": entry.get("skipped", False),
                "completed": entry.get("completed", False),
            }

    def get_history(self, limit: int = 10) -> List[dict]:
        return self._history[-limit:]

    # ── 内部 ──

    def _loop(self):
        """看门狗守护线程主循环"""
        while self._running:
            time.sleep(WATCHDOG_HEARTBEAT)
            try:
                self._check_all()
            except Exception:
                logger.exception("[watchdog] 看门狗检查异常")

    def _check_all(self):
        """遍历所有活跃阶段，检查超时"""
        now = time.monotonic()
        actions_taken = []

        with self._lock:
            for stage_name, entry in list(self._tick_log.items()):
                if entry.get("completed") or entry.get("level", 0) >= LEVEL_FATAL:
                    continue  # 已完成或已触发致命，不再检查

                timeout = self._timeouts.get(stage_name, 15.0)
                age = now - entry["last_tick"]
                current_level = entry.get("level", LEVEL_NONE)

                if age < timeout:
                    # 未超时，重置级别
                    if current_level != LEVEL_NONE and current_level < LEVEL_RETRY:
                        entry["level"] = LEVEL_NONE
                    continue

                # ── 超时，按当前级别升级 ──
                if current_level == LEVEL_NONE:
                    # 首次超时 → LEVEL1 日志告警
                    new_level = LEVEL_LOG
                elif current_level == LEVEL_LOG:
                    # 仍超时 → LEVEL2 尝试重试
                    new_level = LEVEL_RETRY if not entry.get("retried") else LEVEL_SKIP
                elif current_level == LEVEL_RETRY:
                    new_level = LEVEL_SKIP if not entry.get("skipped") else LEVEL_RESTART
                elif current_level == LEVEL_SKIP:
                    new_level = LEVEL_RESTART
                elif current_level == LEVEL_RESTART:
                    new_level = LEVEL_FATAL
                else:
                    new_level = LEVEL_FATAL

                entry["level"] = new_level
                if new_level == LEVEL_RETRY:
                    entry["retried"] = True
                if new_level == LEVEL_SKIP:
                    entry["skipped"] = True

                actions_taken.append((stage_name, new_level, round(age, 1)))

        # 在锁外触发回调（避免死锁）
        for stage_name, new_level, age in actions_taken:
            self._dispatch_level(stage_name, new_level, age)

    def _dispatch_level(self, stage_name: str, level: int, age: float):
        """触发级别回调 + 记录历史"""
        callbacks = list(self._on_level.get(level, []))
        for cb in callbacks:
            try:
                cb(stage_name, level)
            except Exception:
                logger.exception(f"[watchdog] 回调异常: stage={stage_name} level={level}")

        # 记录历史
        record = {
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "stage": stage_name,
            "level": level,
            "level_name": LEVEL_NAMES.get(level, "未知"),
            "age_s": age,
        }
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 状态升级
        if level >= LEVEL_RESTART:
            self._pipeline_blocked = True
            logger.warning(f"[watchdog] ⛔ Pipeline 阻断: {stage_name} 升级到 {LEVEL_NAMES[level]}")
        if level >= LEVEL_FATAL:
            self._fatal_error = f"看门狗触发致命级别: {stage_name} (age={age}s)"

    # ── 持久化 ──

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            data = {
                "pipeline_blocked": self._pipeline_blocked,
                "fatal_error": self._fatal_error,
                "history": self._history[-20:],
            }
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            self._pipeline_blocked = data.get("pipeline_blocked", False)
            self._fatal_error = data.get("fatal_error")
            self._history = data.get("history", [])
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
# Pipeline 集成助手
# ═══════════════════════════════════════════════════════════

def watchdog_tick(stage_name: str):
    """快捷方式：获取全局看门狗并打点"""
    engine = get_watchdog()
    engine.tick(stage_name)

def watchdog_mark(stage_name: str, completed: bool = True, skipped: bool = False, reason: str = ""):
    """快捷方式：标记阶段完成或跳过"""
    engine = get_watchdog()
    if completed:
        engine.mark_complete(stage_name)
    elif skipped:
        engine.mark_skipped(stage_name, reason)

def watchdog_status() -> dict:
    """快捷方式：获取全局看门狗状态"""
    return get_watchdog().get_status()

# ═══════════════════════════════════════════════════════════
# 单例
# ═══════════════════════════════════════════════════════════

_instance = None


def get_watchdog() -> WatchdogEngine:
    global _instance
    if _instance is None:
        _instance = WatchdogEngine()
        _instance._load_state()
        _instance.start()
    return _instance

def init():
    """引擎初始化入口（供 init_engines.py 调用）"""
    wd = get_watchdog()
    print(f"  🐶 看门狗引擎: 已启动 (心跳 {WATCHDOG_HEARTBEAT}s, {len(DEFAULT_STAGE_TIMEOUTS)} 阶段监控)")
    return {"status": "ok", "stages_monitored": list(DEFAULT_STAGE_TIMEOUTS.keys())}

if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    # 快速测试
    wd = WatchdogEngine()
    wd.start()
    
    # 模拟 pipeline 执行
    wd.tick("pipeline")
    wd.tick("stage0_engines")
    time.sleep(0.5)
    wd.tick("stage0_engines")
    wd.mark_complete("stage0_engines")
    
    print("状态:", json.dumps(wd.get_status(), ensure_ascii=False, indent=2))
    
    # 模拟卡死：不 tick 了
    print("\n等待看门狗触发...")
    time.sleep(12)  # stage1 超时 5s，足够触发
    
    print("超时后状态:", json.dumps(wd.get_status(), ensure_ascii=False, indent=2))
    print("\n历史记录:", json.dumps(wd.get_history(), ensure_ascii=False, indent=2))
    
    wd.stop()
    print("\n✅ 看门狗自测完成")
