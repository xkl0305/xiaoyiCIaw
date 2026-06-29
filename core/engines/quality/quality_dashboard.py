"""
Crusheart Performance AutoBrain v4.3.2 — Quality Score Dashboard 引擎质量看板
功能：量化各引擎决策质量，提供命中/误判/漏判评分、健康趋势、异常告警
"""

import os, json
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
SCORE_PATH = os.path.join(WORKSPACE, ".quality_scores.json")

# 引擎评分维度
SCORE_DIMENSIONS = ["hit", "miss", "false_positive", "false_negative", "precision", "recall", "f1"]

# 各引擎的评分标准
ENGINE_METRICS = {
    "dual_mode": {
        "name": "双模式分类",
        "dimensions": ["切换准确率", "快速模式误切率", "Agent模式漏切率"],
        "weight": 0.20
    },
    "anti_fake": {
        "name": "防幻觉校验",
        "dimensions": ["幻觉拦截率", "误报率", "漏报率"],
        "weight": 0.25
    },
    "memory_layer": {
        "name": "记忆分层引擎",
        "dimensions": ["检索命中率", "衰减准确率", "锚点召回率"],
        "weight": 0.15
    },
    "self_evolution": {
        "name": "自进化引擎",
        "dimensions": ["经验质量分", "沉淀准确率", "复用率"],
        "weight": 0.10
    },
    "auto_tuning": {
        "name": "参数自调优",
        "dimensions": ["调优采纳率", "参数有效改善率", "回滚率"],
        "weight": 0.10
    },
    "signal_scorer": {
        "name": "实时信号评分",
        "dimensions": ["评分保存准确率", "误评率", "锚点命中率"],
        "weight": 0.10
    },
    "lazy_load": {
        "name": "懒加载约束",
        "dimensions": ["缓存命中率", "搜索配额使用率", "限流准确率"],
        "weight": 0.10
    },
    "mutex": {
        "name": "互斥锁引擎",
        "dimensions": ["死锁检测率", "超时处理率", "任务成功率"],
        "weight": 0.05
    },
    "task_template": {
        "name": "任务模板库",
        "dimensions": ["模板匹配准确率", "模板使用率", "用户采纳率"],
        "weight": 0.05
    }
}


class QualityScoreDashboard:
    """引擎质量看板"""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        """加载历史评分数据"""
        if os.path.exists(SCORE_PATH):
            try:
                with open(SCORE_PATH) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "engines": {},
            "history": [],
            "alerts": [],
            "scores": {},
            "overall_score": 0.0,
            "last_updated": None
        }


    def trim_old_records(self, max_age_hours: int = 48):
        """清理超过指定小时的旧记录，默认48h"""
        if "scores" not in self._data or not self._data["scores"]:
            return 0
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        trimmed = 0
        for dimension in list(self._data.get("scores", {}).keys()):
            records = self._data["scores"][dimension]
            before = len(records)
            self._data["scores"][dimension] = [
                r for r in records if r.get("timestamp", "") >= cutoff
            ]
            trimmed += before - len(self._data["scores"][dimension])
        # 清理旧 alerts
        alerts = self._data.get("alerts", [])
        before = len(alerts)
        self._data["alerts"] = [a for a in alerts if a.get("timestamp", "") >= cutoff]
        trimmed += before - len(self._data["alerts"])
        # 清理旧 history
        history = self._data.get("history", [])
        before = len(history)
        self._data["history"] = [h for h in history if h.get("timestamp", "") >= cutoff]
        trimmed += before - len(self._data["history"])
        self._save()
        return {"trimmed": trimmed, "max_age_hours": max_age_hours}

    def _save(self):
        """持久化评分数据"""
        self._data["last_updated"] = datetime.now(BEIJING_TZ).isoformat()
        os.makedirs(os.path.dirname(SCORE_PATH), exist_ok=True)
        with open(SCORE_PATH, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def record_score(self, engine: str, dimension: str, score: float, detail: str = ""):
        """记录一次引擎评分"""
        if engine not in self._data["engines"]:
            self._data["engines"][engine] = {
                "scores": {},
                "total_records": 0,
                "avg_score": 0.0,
                "trend": "stable",
                "last_score": None,
                "consecutive_failures": 0
            }

        engine_data = self._data["engines"][engine]
        if dimension not in engine_data["scores"]:
            engine_data["scores"][dimension] = []

        # 记录新评分
        record = {
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "score": score,
            "detail": detail
        }
        engine_data["scores"][dimension].append(record)
        engine_data["total_records"] += 1
        engine_data["last_score"] = score

        # 更新平均分
        all_scores = []
        for dim_records in engine_data["scores"].values():
            for r in dim_records:
                all_scores.append(r["score"])
        engine_data["avg_score"] = round(sum(all_scores) / max(len(all_scores), 1), 3)

        # 更新趋势
        if len(all_scores) >= 3:
            recent = all_scores[-3:]
            if recent[-1] > recent[0] * 1.05:
                engine_data["trend"] = "up"
            elif recent[-1] < recent[0] * 0.95:
                engine_data["trend"] = "down"
            else:
                engine_data["trend"] = "stable"

        # 连续失败检测
        if score < 0.3:
            engine_data["consecutive_failures"] += 1
            if engine_data["consecutive_failures"] >= 3:
                self._add_alert(engine, f"连续 {engine_data['consecutive_failures']} 次低分（<0.3），建议检查")
        else:
            engine_data["consecutive_failures"] = 0

        # 更新总体评分
        self._update_overall_score()

        # 记录历史摘要
        self._data["history"].append({
            "timestamp": record["timestamp"],
            "engine": engine,
            "dimension": dimension,
            "score": score,
            "detail": detail
        })
        if len(self._data["history"]) > 200:
            self._data["history"] = self._data["history"][-200:]

        # 新增实时告警推送
        if score < 0.2:
            self._add_alert(engine, f"⚠️ 引擎 {engine} 维度 {dimension} 评分极低 ({score:.2%})，需紧急关注")

        self._save()

    def _add_alert(self, engine: str, message: str):
        """添加告警"""
        self._data["alerts"].append({
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "engine": engine,
            "message": message,
            "severity": "warning" if "连续" in message else "critical"
        })
        # 只保留最近 20 条告警
        if len(self._data["alerts"]) > 20:
            self._data["alerts"] = self._data["alerts"][-20:]

    def _update_overall_score(self):
        """计算总体评分"""
        total_weight = 0
        weighted_sum = 0
        for engine, data in self._data["engines"].items():
            weight = ENGINE_METRICS.get(engine, {}).get("weight", 0.1)
            total_weight += weight
            weighted_sum += data["avg_score"] * weight

        self._data["overall_score"] = round(weighted_sum / max(total_weight, 0.01), 3)

    def get_engine_report(self, engine: str = None) -> dict:
        """获取引擎报告"""
        if engine:
            if engine in self._data["engines"]:
                ed = self._data["engines"][engine]
                metrics = ENGINE_METRICS.get(engine, {})
                return {
                    "engine": engine,
                    "name": metrics.get("name", engine),
                    "avg_score": ed["avg_score"],
                    "trend": ed["trend"],
                    "total_records": ed["total_records"],
                    "consecutive_failures": ed["consecutive_failures"],
                    "dimensions": list(ed["scores"].keys()),
                    "status": self._get_engine_status(ed["avg_score"], ed["consecutive_failures"])
                }
            return {"error": f"Engine '{engine}' not found"}

        # 全量报告
        reports = {}
        for eng_name in sorted(self._data["engines"].keys()):
            reports[eng_name] = self.get_engine_report(eng_name)
        return {
            "engines": reports,
            "overall_score": self._data["overall_score"],
            "alerts_count": len(self._data["alerts"]),
            "total_records": sum(
                ed["total_records"] for ed in self._data["engines"].values()
            ),
            "last_updated": self._data["last_updated"]
        }

    def _get_engine_status(self, avg_score: float, consecutive_failures: int) -> str:
        """根据评分判断引擎健康状态"""
        if consecutive_failures >= 3:
            return "CRITICAL"
        if avg_score >= 0.8:
            return "HEALTHY"
        if avg_score >= 0.5:
            return "DEGRADED"
        return "POOR"

    def get_overview(self) -> dict:
        """获取看板概览"""
        return {
            "overall_score": self._data["overall_score"],
            "total_engines": len(self._data["engines"]),
            "total_records": sum(
                ed["total_records"] for ed in self._data["engines"].values()
            ),
            "active_alerts": len([
                a for a in self._data["alerts"]
                if "resolved_at" not in a
            ]),
            "health_summary": self._health_summary(),
            "last_updated": self._data["last_updated"]
        }

    def _health_summary(self) -> dict:
        """健康状态汇总"""
        summary = Counter()
        for eng_name in self._data["engines"]:
            report = self.get_engine_report(eng_name)
            summary[report["status"]] += 1
        return dict(summary)

    def clear_history(self, before_days: int = 30):
        """清理旧历史记录"""
        cutoff = datetime.now(BEIJING_TZ) - timedelta(days=before_days)
        self._data["history"] = [
            h for h in self._data["history"]
            if datetime.fromisoformat(h["timestamp"]) > cutoff
        ]
        self._data["alerts"] = [
            a for a in self._data["alerts"]
            if "timestamp" not in a or datetime.fromisoformat(a["timestamp"]) > cutoff
        ]
        self._save()

    def get_ranking(self) -> list:
        """获取引擎评分排名"""
        rankings = []
        for eng_name, ed in self._data["engines"].items():
            metrics = ENGINE_METRICS.get(eng_name, {})
            rankings.append({
                "engine": eng_name,
                "name": metrics.get("name", eng_name),
                "avg_score": ed["avg_score"],
                "trend": ed["trend"],
                "total_records": ed["total_records"]
            })
        rankings.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, r in enumerate(rankings, 1):
            r["rank"] = i
        return rankings

    def get_score_trend(self, engine: str, dimension: str = None) -> list:
        """获取引擎评分趋势"""
        if engine not in self._data["engines"]:
            return []
        engine_data = self._data["engines"][engine]
        if dimension:
            records = engine_data["scores"].get(dimension, [])
        else:
            records = []
            for dim_records in engine_data["scores"].values():
                records.extend(dim_records)
            records.sort(key=lambda x: x["timestamp"])
        return records[-20:]  # 最近20条



    def read_pipeline_profiles(self, limit: int = 20) -> dict:
        """读取 pipeline_profiler JSONL 数据，计算近期性能趋势

        Args:
            limit: 读取最近多少条记录

        Returns:
            {
                "total_ms_avg": 243.5,
                "slowest_stage": "memory_align",
                "slowest_ms_avg": 150.2,
                "stage_avg_ms": {"engines": 80, "dual_mode": 120, ...},
                "samples": 20,
            }
        """
        path = os.path.join(WORKSPACE, ".engine_logs", "pipeline_profiles.jsonl")
        if not os.path.exists(path):
            return {"status": "no_data", "note": "pipeline_profiles.jsonl 不存在"}

        records = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return {"status": "error", "msg": "读取失败"}

        records = records[-limit:]
        if not records:
            return {"status": "empty"}

        # 统计总耗时均值
        total_ms_list = [r.get("total_ms", 0) for r in records]
        avg_total = sum(total_ms_list) / max(len(total_ms_list), 1)

        # 统计各阶段均值
        all_stages = {}
        for r in records:
            for stage_key, stage_ms in r.get("stages", {}).items():
                if stage_key not in all_stages:
                    all_stages[stage_key] = []
                all_stages[stage_key].append(stage_ms)

        stage_avg = {k: round(sum(v) / max(len(v), 1), 1) for k, v in all_stages.items()}

        # 找到最慢阶段
        slowest = max(stage_avg, key=stage_avg.get) if stage_avg else None
        slowest_avg = stage_avg.get(slowest, 0) if slowest else 0

        # 找到最慢的单个请求
        worst = max(records, key=lambda r: r.get("total_ms", 0))
        worst_time = worst.get("ts", "")

        return {
            "total_ms_avg": round(avg_total, 1),
            "slowest_stage": slowest,
            "slowest_ms_avg": slowest_avg,
            "stage_avg_ms": stage_avg,
            "worst_total_ms": worst.get("total_ms", 0),
            "worst_at": worst_time,
            "samples": len(records),
            "status": "ready",
        }

    def read_degradation_metrics(self, limit: int = 50) -> dict:
        """读取 degradation_chain.jsonl 降级数据，统计降级率

        Args:
            limit: 读取最近多少条记录

        Returns:
            {
                "total_degradations": 15,
                "resolved_rate": 0.87,
                "avg_latency_ms": 35.2,
                "by_resolve_level": {"0": 10, "1": 3, "2": 2},
                "top_tasks": [...],
                "samples": 50,
            }
        """
        path = os.path.join(WORKSPACE, ".engine_logs", "degradation_chain.jsonl")
        if not os.path.exists(path):
            return {"status": "no_data", "note": "degradation_chain.jsonl 不存在"}

        records = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return {"status": "error", "msg": "读取失败"}

        records = records[-limit:]
        if not records:
            return {"status": "empty"}

        total = len(records)
        degraded = [r for r in records if r.get("resolved_by") and r["resolved_by"] != "level_0"]
        total_degradations = len(degraded)
        resolved = sum(1 for r in degraded if r.get("resolved_at_level") is not None)

        # 按降级级别分组
        by_level = {}
        for r in degraded:
            lvl = r.get("resolved_at_level", -1)
            lvl_str = str(lvl)
            by_level[lvl_str] = by_level.get(lvl_str, 0) + 1

        # 按任务名统计
        task_counter = {}
        for r in degraded:
            task = r.get("task", "unknown")
            task_counter[task] = task_counter.get(task, 0) + 1
        top_tasks = sorted(task_counter.items(), key=lambda x: x[1], reverse=True)[:5]

        # 平均延迟
        latencies = [r.get("total_elapsed_ms", 0) for r in degraded if r.get("total_elapsed_ms")]
        avg_latency = sum(latencies) / max(len(latencies), 1)

        return {
            "total_records": total,
            "total_degradations": total_degradations,
            "resolved": resolved,
            "resolved_rate": round(resolved / max(total_degradations, 1), 3),
            "avg_latency_ms": round(avg_latency, 1),
            "by_resolve_level": by_level,
            "top_tasks": [{"task": t, "count": c} for t, c in top_tasks],
            "status": "ready",
        }

    def get_integrated_report(self) -> dict:
        """生成集成报告：quality_dashboard + pipeline_profiler + degradation_chain"""
        overview = self.get_overview()
        pipeline = self.read_pipeline_profiles()
        degradation = self.read_degradation_metrics()
        ranking = self.get_ranking()

        return {
            "overview": overview,
            "pipeline_performance": pipeline,
            "degradation_metrics": degradation,
            "engine_ranking": ranking,
            "generated_at": datetime.now(BEIJING_TZ).isoformat(),
        }


def init():
    """引擎初始化入口"""
    dashboard = QualityScoreDashboard()
    overview = dashboard.get_overview()
    overall = overview["overall_score"]
    health = overview["health_summary"]
    alerts = overview["active_alerts"]

    print(f"  📊 Quality Score Dashboard: 总体评分 {overall:.1%} | "
          f"{health.get('HEALTHY', 0)} 健康 | "
          f"{health.get('DEGRADED', 0)} 降级 | "
          f"{health.get('CRITICAL', 0)} 危急 | "
          f"{health.get('POOR', 0)} 差劲 | "
          f"告警 {alerts}")

    result = {
        "status": "ready",
        "overview": overview,
        "ranking": dashboard.get_ranking(),
        "initialized_at": datetime.now(BEIJING_TZ).isoformat()
    }
    return result


# ── CLI 入口已移至 cli.py（#46） ──

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

    from core.engines.quality.cli import main
    main()
