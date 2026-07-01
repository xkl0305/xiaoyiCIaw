"""
Crusheart Agent OS — Pipeline 管线分析器
功能：收集 pipeline 各阶段耗时，输出 ASCII 可视化图表

集成点：
  - orchestrator.py: 每个 stage 执行前后打点
  - quality_dashboard.py: 通过 report_pipeline_profile() 输出看板

输出示例：
  ┌─ Message Pipeline ───────────────────────────────────────┐
  │ stage 0: engines     ████████░░ 8/10 ready  (80%)       │
  │ stage 1: dual_mode   ██████████ fast_path (120ms)       │
  │ stage 2: skill_match ██████████ match:weather (8ms)     │
  │ stage 3: anti_fake   ██████████ level:LOW skip  (2ms)   │
  │ stage 4: route       ██████████ engine:default (5ms)    │
  │ stage 5: session     ██████████ loaded (15ms)           │
  │ stage 6: memory      ██████████ 12 hits (45ms)          │
  │ stage 7: evolution   ████████░░ skip:noop (0ms)         │
  │ stage 8: reflect     ██████████ PASS (25ms)             │
  │ stage 9: anti_fake   ██████████ PASS (18ms)             │
  │ TOTAL: 243ms                                            │
  └──────────────────────────────────────────────────────────┘
"""

import time
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
PROFILE_LOG_DIR = os.path.join(WORKSPACE, ".engine_logs")
PROFILE_LOG_PATH = os.path.join(PROFILE_LOG_DIR, "pipeline_profiles.jsonl")


# ── Pipeline 阶段定义 ──
# stage 名称 → 显示标签, 数据字段路径
PIPELINE_STAGES = [
    ("engines",         "engines",      "引擎状态检测"),
    ("dual_mode",       "dual_mode",    "双模式分类"),
    ("skill_match",     "skill_match",  "技能匹配"),
    ("anti_fake",       "risk_check",   "防幻觉风险提示"),
    ("engine_route",    "engine_route", "引擎路由预分析"),
    ("session_state",   "session_state","热RAM层"),
    ("memory_align",    "memory_alignment", "记忆对齐"),
    ("evolution_ctx",   "evolution_context", "自进化上下文"),
    ("self_reflect",    "self_reflection",  "自进化复盘"),
    ("anti_forget",     "anti_forget_risks","反遗忘扫描"),
]


class PipelineTimer:
    """
    Pipeline 计时上下文管理器。
    
    用法：
        timer = PipelineTimer()
        with timer.measure("engines"):
            run_stage0(...)
        profile = timer.get_profile()  # {"engines": 123.4, ...}
    """
    
    def __init__(self):
        self._timings: Dict[str, float] = {}
    
    def measure(self, stage_name: str) -> "_MeasureContext":
        return _MeasureContext(self, stage_name)
    
    def get_profile(self) -> Dict[str, float]:
        return dict(self._timings)
    
    def get_elapsed(self, stage_name: str) -> Optional[float]:
        return self._timings.get(stage_name)
    
    def to_result_profile(self, result: dict) -> dict:
        """将 timing 注入 result['_profile']"""
        result["_profile"] = self.get_profile()
        return result


class _MeasureContext:
    def __init__(self, timer: PipelineTimer, stage_name: str):
        self._timer = timer
        self._stage_name = stage_name
        self._start = 0.0
    
    def __enter__(self):
        self._start = time.monotonic()
        return self
    
    def __exit__(self, *args):
        elapsed = time.monotonic() - self._start
        self._timer._timings[self._stage_name] = round(elapsed * 1000, 1)


def build_profile_visualization(profile: Dict[str, float],
                                 result: dict = None,
                                 max_bar_chars: int = 12) -> str:
    """
    构建 ASCII 管线可视化图表
    
    Args:
        profile: stage_name → elapsed_ms 字典
        result: 可选的完整 pipeline 结果（用于提取额外信息）
        max_bar_chars: 进度条最大字符数
    
    Returns:
        多行 ASCII 表格字符串
    """
    if not profile:
        return "  (pipeline profile 为空)"
    
    max_ms = max(profile.values()) if profile else 1
    if max_ms == 0:
        max_ms = 1
    
    lines = ["┌─ Message Pipeline ─────────────────────────────────────────────────────┐"]
    
    total_ms = 0
    for stage_key, data_key, label in PIPELINE_STAGES:
        elapsed = profile.get(stage_key, 0)
        total_ms += elapsed
        
        # 提取 stage 摘要信息
        summary = _extract_stage_summary(stage_key, data_key, result)
        
        # 进度条
        bar_len = int((elapsed / max_ms) * max_bar_chars) if max_ms > 0 else 0
        bar_len = min(bar_len, max_bar_chars)
        bar = "█" * bar_len + "░" * (max_bar_chars - bar_len)
        
        # 行格式
        stage_pad = stage_key.ljust(12)
        elapsed_str = f"{elapsed:.0f}ms" if elapsed < 1000 else f"{elapsed/1000:.1f}s"
        line = f"│ {stage_pad} {bar} {summary}{' ' * (20 - len(summary))} ({elapsed_str}) │"
        lines.append(line)
    
    # 总计行
    total_str = f"{total_ms:.0f}ms" if total_ms < 1000 else f"{total_ms/1000:.1f}s"
    total_bar_len = int((total_ms / (max_ms * len(profile) * 0.8)) * max_bar_chars) if max_ms > 0 else 0
    total_bar_len = min(total_bar_len, max_bar_chars)
    total_bar = "█" * total_bar_len + "░" * (max_bar_chars - total_bar_len)
    
    lines.append(f"├{'─' * 68}┤")
    lines.append(f"│ TOTAL: {' ' * 10}{total_bar}{' ' * (18 - len(total_str))}{total_str}         │")
    lines.append(f"└{'─' * 68}┘")
    
    return "\n".join(lines)


def _extract_stage_summary(stage_key: str, data_key: str, result: dict) -> str:
    """从 result 中提取 stage 的文本摘要"""
    if not result:
        return ""
    
    data = result.get(data_key, {})
    if not data:
        return ""
    
    summaries = {
        "engines": lambda d: _fmt_engines(d),
        "dual_mode": lambda d: f"mode:{d.get('mode', '?')}",
        "skill_match": lambda d: f"match:{d.get('matched_count', 0)}",
        "risk_check": lambda d: f"level:{d.get('level', 'LOW')}",
        "engine_route": lambda d: f"route:{d.get('pre_process', '?')}",
        "session_state": lambda d: f"loaded" if d.get("status") == "ready" else "skip",
        "memory_alignment": lambda d: f"{d.get('similar_found', 0)} hits",
        "evolution_context": lambda d: f"ready" if d.get("status") == "ready" else "skip",
        "self_reflection": lambda d: f"{d.get('action', 'PASS')}",
        "anti_forget_risks": lambda d: f"{len(d) if isinstance(d, list) else 0} risks",
    }
    
    fn = summaries.get(stage_key)
    if fn:
        try:
            return fn(data)
        except Exception:
            pass
    
    if isinstance(data, dict) and "status" in data:
        return data.get("status", "")
    if isinstance(data, str):
        return data[:20]
    
    return ""


def _fmt_engines(data: dict) -> str:
    """引擎状态摘要"""
    ready = sum(1 for v in data.values() if isinstance(v, dict) and v.get("status") == "ready")
    total = len(data) if isinstance(data, dict) else 0
    return f"{ready}/{total} ready  ({ready/max(total,1)*100:.0f}%)"


def format_profile_csv(profile: Dict[str, float]) -> str:
    """输出 CSV 格式（用于日志记录）"""
    lines = ["stage,elapsed_ms"]
    for k, v in sorted(profile.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{k},{v}")
    lines.append(f"TOTAL,{sum(profile.values())}")
    return "\n".join(lines)


def log_profile_to_jsonl(profile: Dict[str, float], result: dict = None):
    """将 pipeline profile 写入 JSONL 供 quality_dashboard 消费

    每条记录包含：时间戳、各阶段耗时(ms)、总耗时、各阶段摘要
    """
    if not profile:
        return
    try:
        os.makedirs(PROFILE_LOG_DIR, exist_ok=True)
        total_ms = sum(profile.values())

        # 构造结构化摘要
        stage_summaries = {}
        if result:
            for stage_key, data_key, _ in PIPELINE_STAGES:
                summary = _extract_stage_summary(stage_key, data_key, result)
                if summary:
                    stage_summaries[stage_key] = summary

        entry = {
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "ts_unix": int(time.time()),
            "type": "pipeline_profile",
            "total_ms": round(total_ms, 1),
            "stages": {k: round(v, 1) for k, v in profile.items()},
            "stage_summaries": stage_summaries,
        }
        with open(PROFILE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def profile_to_dashboard(profile: Dict[str, float]) -> dict:
    """将 profile 格式化为 quality_dashboard 可消费的结构化指标

    Returns:
        {
            "pipeline_profile": {
                "total_ms": 243,
                "stages": {..., ...},
                "slowest_stage": "memory_align",
                "slowest_ms": 150,
            }
        }
    """
    if not profile:
        return {"pipeline_profile": {"status": "empty"}}
    total_ms = sum(profile.values())
    max_stage = max(profile, key=profile.get) if profile else None
    return {
        "pipeline_profile": {
            "total_ms": round(total_ms, 1),
            "stages": {k: round(v, 1) for k, v in profile.items()},
            "slowest_stage": max_stage,
            "slowest_ms": round(profile[max_stage], 1) if max_stage else 0,
        }
    }


# ── 快速验证 ──
if __name__ == "__main__":
    # 模拟 profile 数据
    sim_profile = {
        "engines": 80,
        "dual_mode": 120,
        "skill_match": 8,
        "anti_fake": 2,
        "engine_route": 5,
        "session_state": 15,
        "memory_align": 45,
        "evolution_ctx": 0,
        "self_reflect": 25,
        "anti_forget": 18,
    }
    
    sim_result = {
        "engines": {
            "memory": {"status": "ready"},
            "anti_fake": {"status": "ready"},
            "dual_mode": {"status": "ready"},
        },
        "dual_mode": {"mode": "fast"},
        "skill_match": {"matched_count": 1},
        "risk_check": {"level": "LOW"},
        "engine_route": {"pre_process": "fast"},
        "session_state": {"status": "ready"},
        "memory_alignment": {"similar_found": 12},
        "evolution_context": {"status": "ready"},
        "self_reflection": {"action": "PASS"},
        "anti_forget_risks": [1, 2, 3],
    }
    
    print("Pipeline 可视化输出测试：\n")
    print(build_profile_visualization(sim_profile, sim_result))
    print("\n✅ 管线分析器自检通过")
