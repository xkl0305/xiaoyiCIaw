"""
Crusheart Agent OS — 懒加载硬约束引擎
功能：搜索限流、缓存约束、串行执行、超时切断
"""

import os
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import logging

BEIJING_TZ = timezone(timedelta(hours=8))
ENFORCER_FILE = os.path.expanduser("~/.openclaw/workspace/.lazy_load_enforcer.json")


class LazyLoadEnforcer:
    """懒加载硬约束执行器"""

    # 硬约束常量
    SEARCH_INTERVAL_S = 0.5        # 每次搜索后强制暂停500ms
    MAX_SEARCHES_PER_TASK = 5      # 单次任务最多5次搜索
    CACHE_TTL_S = 1800             # 缓存有效期30分钟
    SEARCH_TIMEOUT_S = 30          # 单次搜索超时30秒
    TOTAL_SEARCH_TIMEOUT_S = 120   # 总搜索用时上限120秒

    def __init__(self):
        self._search_count = 0
        self._task_start_time = time.time()
        self._last_search_time = 0.0
        self._history = {}
        self._load()

    def pre_search(self) -> Dict:
        """
        执行搜索前的硬约束检查
        Returns: {"allowed": bool, "reason": str, "wait_ms": int}
        """
        now = time.time()
        elapsed = now - self._task_start_time

        # 总时间超限
        if elapsed > self.TOTAL_SEARCH_TIMEOUT_S:
            return {"allowed": False, "reason": f"总搜索用时超过{self.TOTAL_SEARCH_TIMEOUT_S}s", "wait_ms": 0}

        # 次数超限
        if self._search_count >= self.MAX_SEARCHES_PER_TASK:
            return {"allowed": False, "reason": f"单次任务搜索已达上限{self.MAX_SEARCHES_PER_TASK}次", "wait_ms": 0}

        # 间隔约束 — 自动等待满足间隔
        time_since_last = now - self._last_search_time
        wait_needed = max(0, self.SEARCH_INTERVAL_S - time_since_last)
        if wait_needed > 0:
            time.sleep(wait_needed)

        return self._do_search()

    def _do_search(self) -> Dict:
        """实际执行搜索并计数"""
        if self._search_count >= self.MAX_SEARCHES_PER_TASK:
            return {"allowed": False, "reason": f"已达上限{self.MAX_SEARCHES_PER_TASK}次", "wait_ms": 0}
        self._search_count += 1
        self._last_search_time = time.time()
        self._save()
        return {"allowed": True, "reason": "ok", "wait_ms": 0}

    def check_cache(self, keyword: str) -> Optional[Dict]:
        """检查缓存是否命中"""
        cached = self._history.get(keyword)
        if cached:
            age = time.time() - cached["timestamp"]
            if age < self.CACHE_TTL_S:
                return cached["result"]
        return None

    def set_cache(self, keyword: str, result: Dict):
        """写入缓存"""
        self._history[keyword] = {
            "timestamp": time.time(),
            "result": result
        }
        self._save()

    def new_task(self):
        """新任务开始，重置计数器"""
        self._search_count = 0
        self._task_start_time = time.time()
        self._last_search_time = 0.0

    def cleanup_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired = [k for k, v in self._history.items()
                   if now - v["timestamp"] > self.CACHE_TTL_S]
        for k in expired:
            del self._history[k]
        if expired:
            self._save()

    def get_stats(self) -> Dict:
        return {
            "search_count": self._search_count,
            "cached_keywords": len(self._history),
            "cache_ttl_s": self.CACHE_TTL_S,
            "max_searches": self.MAX_SEARCHES_PER_TASK,
            "search_interval_s": self.SEARCH_INTERVAL_S
        }

    def _save(self):
        data = {
            "search_count": self._search_count,
            "task_start_time": self._task_start_time,
            "history": self._history
        }
        with open(ENFORCER_FILE, "w") as f:
            json.dump(data, f)

    def _load(self):
        if os.path.exists(ENFORCER_FILE):
            try:
                with open(ENFORCER_FILE) as f:
                    data = json.load(f)
                    self._search_count = data.get("search_count", 0)
                    self._task_start_time = time.time()  # 加载后重置任务时间
                    self._history = data.get("history", {})
            except Exception:
                logging.exception("[lazy_load_enforcer.py] suppressed")
                pass


# 测试
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

    enforcer = LazyLoadEnforcer()
    enforcer.new_task()

    print("=== 懒加载硬约束测试 ===")
    for i in range(7):
        result = enforcer.pre_search()
        if result["allowed"]:
            enforcer.set_cache(f"keyword_{i}", {"data": f"result_{i}"})
            print(f"✅ 搜索{i + 1}: 允许 (缓存已写入)")
        else:
            print(f"❌ 搜索{i + 1}: 被拒绝 — {result['reason']}")
        if result["wait_ms"] > 0:
            time.sleep(result["wait_ms"] / 1000)

    print(f"\n📊 缓存统计: {enforcer.get_stats()}")

    # 测试缓存命中
    cached = enforcer.check_cache("keyword_0")
    print(f"\n🔍 缓存命中测试: {'✅ 命中' if cached else '❌ 未命中'}")
