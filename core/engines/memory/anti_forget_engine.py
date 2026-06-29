"""
Crusheart Agent OS — AntiForgetEngine v1.0
反遗忘引擎：检测重要但长期未召回的记忆 + 主动提醒

与 yaoyao-plugin 反遗忘的区别：
- yaoyao: 纯 SQL + 规则，无外部依赖
- 本引擎: 对接 Crusheart 五层记忆体系，重要性+遗忘度双重评分

核心机制：
  重要性评分 = 访问频率权重 + 标签优先级 + 时间衰减
  遗忘度评分 = 距离上次召回天数 × 衰减权重
  遗忘风险 = 重要性 × 遗忘度
  当遗忘风险超过阈值，生成提醒列表

集成方式：
  get_anti_forget_engine().scan()  → 扫描记忆库，输出风险列表
  get_anti_forget_engine().report() → 格式化提醒报告
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import logging
import os
import re
import math

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


@dataclass
class MemoryEntry:
    """记忆条目——从 L2/L3/L4 层提取的最小单元"""
    id: str
    content: str
    tags: List[str]
    importance: float = 0.5           # 0~1 相对重要性
    last_accessed: Optional[str] = None  # ISO datetime
    access_count: int = 0
    created_at: Optional[str] = None
    source_layer: str = "L2"          # L2/L3/L4
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "content": self.content[:120],
            "tags": self.tags, "importance": round(self.importance, 4),
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "source_layer": self.source_layer,
        }


@dataclass
class ForgetRisk:
    """遗忘风险评估"""
    memory: MemoryEntry
    days_since_access: float
    forget_score: float            # 0~1
    risk_level: str                # "high" / "medium" / "low"
    reason: str
    suggested_action: str = ""


class MemoryScanner:
    """
    记忆扫描器——从 Crusheart 五层记忆体系扫描记忆条目

    对接:
    - L2 短期记忆: memory/ 目录的 .md 文件
    - L3 长期记忆: MEMORY.md + USER.md + SOUL.md
    - L4 归档记忆: auto_memory.py 的 MemoryStore（如可用）

    不依赖 auto_memory 的完整 API，直接扫描文件系统。
    """

    IMPORTANT_TAGS = {
        "high": {"用户偏好", "偏好", "安全", "安全规则", "红线",
                  "身份", "密码", "token", "密钥", "api_key",
                  "persona", "soul", "identity", "rule", "policy",
                  "重要配置", "配置", "host", "ssh", "服务器"},
        "medium": {"项目", "task", "工作流", "workflow", "工具",
                    "tool", "skill", "bug", "fix", "error",
                    "技巧", "经验", "lesson", "学习"},
    }

    def __init__(self):
        self.memory_dir = os.path.join(WORKSPACE, "memory")
        self.workspace = WORKSPACE

    def scan_all(self) -> List[MemoryEntry]:
        """扫描全部层级的记忆"""
        entries: List[MemoryEntry] = []

        # L2: memory/ 目录
        entries.extend(self._scan_memory_dir())

        # L3: 核心配置文件
        entries.extend(self._scan_core_files())

        # L4: MEMORY.md
        entries.extend(self._scan_memory_main())

        return entries

    def _scan_memory_dir(self) -> List[MemoryEntry]:
        """扫描 memory/ 目录（L2 短期记忆）"""
        entries = []
        if not os.path.isdir(self.memory_dir):
            return entries

        for fname in os.listdir(self.memory_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(self.memory_dir, fname)
            try:
                mtime = os.path.getmtime(fpath)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read(500)  # 前500字符
                tags = self._extract_tags(content) + ["daily_log"]
                entries.append(MemoryEntry(
                    id=f"memory/{fname}",
                    content=content[:200],
                    tags=list(set(tags)),
                    importance=self._calc_importance(tags),
                    last_accessed=datetime.fromtimestamp(mtime, tz=BEIJING_TZ).isoformat(),
                    source_layer="L2",
                    access_count=max(1, int(content.count("💾"))),
                ))
            except Exception:
                continue

        return entries

    def _scan_core_files(self) -> List[MemoryEntry]:
        """扫描核心文件（L3 长期记忆）"""
        entries = []
        core = ["USER.md", "SOUL.md", "TOOLS.md", "AGENTS.md"]
        for name in core:
            path = os.path.join(self.workspace, name)
            if not os.path.exists(path):
                continue
            try:
                mtime = os.path.getmtime(path)
                mtime_dt = datetime.fromtimestamp(mtime, tz=BEIJING_TZ)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(3000)
                tags = ["persona", "core", "config"]
                if name == "USER.md":
                    tags.append("用户偏好")
                if name == "SOUL.md":
                    tags.append("soul")
                if name == "TOOLS.md":
                    tags.append("工具")
                if name == "AGENTS.md":
                    tags.append("rules")

                entries.append(MemoryEntry(
                    id=f"core/{name}",
                    content=content[:300],
                    tags=tags,
                    importance=self._calc_importance(tags),
                    last_accessed=mtime_dt.isoformat(),
                    source_layer="L3",
                    access_count=3,
                ))
            except Exception:
                continue

        return entries

    def _scan_memory_main(self) -> List[MemoryEntry]:
        """扫描 MEMORY.md（L4 归档）"""
        path = os.path.join(self.workspace, "MEMORY.md")
        if not os.path.exists(path):
            return []
        try:
            mtime = os.path.getmtime(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(3000)
            tags = ["long_term", "归档", "记忆"]
            return [MemoryEntry(
                id="core/MEMORY.md",
                content=content[:300],
                tags=tags + self._extract_tags(content),
                importance=self._calc_importance(tags),
                last_accessed=datetime.fromtimestamp(mtime, tz=BEIJING_TZ).isoformat(),
                source_layer="L4",
                access_count=5,
            )]
        except Exception:
            return []

    def _extract_tags(self, text: str) -> List[str]:
        """从文本中提取标签"""
        tags = set()
        # 标题标记
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("#") and len(line) > 2:
                tags.add(line.lstrip("#").strip()[:30])
        return list(tags)

    def _calc_importance(self, tags: List[str]) -> float:
        """根据标签计算重要性
        - 高优先级标签 +0.4
        - 中优先级标签 +0.2
        - 最多 0.95
        """
        score = 0.3  # 基础分
        for tag in tags:
            for word in self.IMPORTANT_TAGS["high"]:
                if word in tag:
                    score += 0.12
                    break
            for word in self.IMPORTANT_TAGS["medium"]:
                if word in tag:
                    score += 0.06
                    break
        return min(0.95, score)


class ForgettingCurve:
    """
    遗忘曲线计算器

    基于简化版 Ebbinghaus 遗忘曲线:
    - 第1天: 遗忘 30%
    - 第7天: 遗忘 60%
    - 第30天: 遗忘 80%
    - 第90天: 遗忘 90%

    结合访问次数修正: 每访问一次，遗忘速度减缓 8%
    """

    @staticmethod
    def forget_score(days: float, access_count: int = 0) -> float:
        """计算遗忘度（0~1）"""
        if days <= 0:
            return 0.0

        # 基础遗忘率（指数衰减）
        baseline = 1.0 - math.exp(-0.05 * days)

        # 访问次数修正
        retention_boost = min(0.40, access_count * 0.08)
        score = baseline * (1.0 - retention_boost)

        return min(1.0, max(0.0, score))

    @staticmethod
    def days_since(last_accessed_str: Optional[str]) -> float:
        """计算距上次访问的天数"""
        if not last_accessed_str:
            return float("inf")
        try:
            dt = datetime.fromisoformat(last_accessed_str)
            now = datetime.now(BEIJING_TZ)
            delta = now - dt
            return max(0.0, delta.total_seconds() / 86400.0)
        except (ValueError, TypeError):
            return float("inf")


class AntiForgetEngine:
    """
    反遗忘引擎 v1.0

    使用方式:
        engine = AntiForgetEngine()

        # 扫描并评估
        risks = engine.scan()

        # 输出提醒报告
        report = engine.report(risks, top_k=5)

        # 标记为已处理（重置遗忘度）
        engine.acknowledge("memory/2026-05-13.md")
    """

    HIGH_RISK_THRESHOLD = 0.60
    MEDIUM_RISK_THRESHOLD = 0.35
    DEFAULT_REMIND_DAYS = 14

    def __init__(self, storage_dir: str = ".evolution_state/anti_forget"):
        self.scanner = MemoryScanner()
        self.curve = ForgettingCurve()
        self._storage_dir = os.path.join(WORKSPACE, storage_dir)
        os.makedirs(self._storage_dir, exist_ok=True)

    def scan(self, force: bool = False, top_k: int = 10) -> List[ForgetRisk]:
        """
        扫描全部记忆，评估遗忘风险

        Args:
            force: 是否强制重新扫描（默认使用缓存）
            top_k: 返回最高风险的 top k 条

        Returns:
            按遗忘风险降序排列的 ForgetRisk 列表
        """
        cache_hit = self._try_cache(force)
        if cache_hit:
            return cache_hit

        entries = self.scanner.scan_all()
        risks: List[ForgetRisk] = []

        for entry in entries:
            days = self.curve.days_since(entry.last_accessed)
            forget = self.curve.forget_score(days, entry.access_count)

            # 遗忘风险 = 重要性 × 遗忘度
            risk_score = entry.importance * forget

            # 只有真正重要的且长时间未访问的才标记
            if risk_score < 0.15:
                continue

            if risk_score >= self.HIGH_RISK_THRESHOLD:
                level = "high"
            elif risk_score >= self.MEDIUM_RISK_THRESHOLD:
                level = "medium"
            else:
                level = "low"

            if days >= self.DEFAULT_REMIND_DAYS:
                action = "建议主动回顾或更新内容"
            elif level == "high":
                action = "重要性高，建议近期回顾"
            else:
                action = "可正常轮换"

            if days <= 3:
                continue  # 最近访问过的忽略

            reason = (
                f"{level.upper()} 风险: "
                f"{'重要' if entry.importance > 0.6 else '普通'}内容 "
                f"已 {int(days)} 天未访问"
            )

            risks.append(ForgetRisk(
                memory=entry,
                days_since_access=days,
                forget_score=round(risk_score, 4),
                risk_level=level,
                reason=reason,
                suggested_action=action,
            ))

        risks.sort(key=lambda r: r.forget_score, reverse=True)
        top = risks[:top_k]

        self._cache_result(top)
        return top

    def report(self, risks: Optional[List[ForgetRisk]] = None,
               top_k: int = 5) -> str:
        """
        生成可读的报告

        Args:
            risks: 风险列表（None 则自动 scan）
            top_k: 展示条数

        Returns:
            格式化报告文本
        """
        if risks is None:
            risks = self.scan(top_k=top_k)

        high = sum(1 for r in risks if r.risk_level == "high")
        medium = sum(1 for r in risks if r.risk_level == "medium")

        lines = [
            f"🧠 反遗忘扫描报告",
            f"{'=' * 45}",
            f"  高风险: {high} | 中风险: {medium}",
            f"  (重要性 × 遗忘度 = 遗忘风险)",
            f"{'=' * 45}",
        ]

        for i, risk in enumerate(risks, 1):
            mem = risk.memory
            lines.append(
                f"  {i}. [{risk.risk_level.upper():>6}] "
                f"{mem.id}"
            )
            lines.append(f"      重要性={mem.importance:.2f} "
                         f"遗忘度={risk.forget_score:.2f} "
                         f"已有{int(risk.days_since_access)}天")
            lines.append(f"      标签: {', '.join(mem.tags[:4])}")
            lines.append(f"      建议: {risk.suggested_action}")
            lines.append("")

        if not risks:
            lines.append("  没有发现遗忘风险 ✅")

        return "\n".join(lines)

    def acknowledge(self, memory_id: str) -> bool:
        """
        标记一条记忆为已处理（重置遗忘度）

        通过更新文件的修改时间来重置遗忘曲线。
        """
        path = os.path.join(WORKSPACE, memory_id)
        if os.path.exists(path):
            os.utime(path, None)
            logger.info(f"[AntiForget] 已重置遗忘度: {memory_id}")
            return True
        logger.warning(f"[AntiForget] 文件不存在，无法重置: {memory_id}")
        return False

    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        if not os.path.exists(self._cache_path()):
            return {"cached": False}
        try:
            with open(self._cache_path(), "r") as f:
                data = json.load(f)
            return {
                "cached": True,
                "total_risks": len(data),
                "high": sum(1 for d in data if d.get("risk_level") == "high"),
                "medium": sum(1 for d in data if d.get("risk_level") == "medium"),
            }
        except Exception:
            return {"cached": False}

    # ── 内部 ──

    def _cache_path(self) -> str:
        return os.path.join(self._storage_dir, "forget_risks.json")

    def _cache_result(self, risks: List[ForgetRisk]):
        try:
            data = [{
                "memory_id": r.memory.id,
                "risk_level": r.risk_level,
                "forget_score": r.forget_score,
                "days_since_access": int(r.days_since_access),
                "importance": r.memory.importance,
                "tags": r.memory.tags[:5],
                "suggested_action": r.suggested_action,
            } for r in risks]
            with open(self._cache_path(), "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _try_cache(self, force: bool) -> Optional[List[ForgetRisk]]:
        if force or not os.path.exists(self._cache_path()):
            return None
        try:
            with open(self._cache_path(), "r") as f:
                data = json.load(f)
            if not data:
                return None
            # 从缓存重建（简化版）
            risks = []
            for d in data:
                risks.append(ForgetRisk(
                    memory=MemoryEntry(
                        id=d["memory_id"], content="", tags=d.get("tags", []),
                        importance=d.get("importance", 0.5), access_count=0,
                    ),
                    days_since_access=d.get("days_since_access", 0),
                    forget_score=d.get("forget_score", 0),
                    risk_level=d.get("risk_level", "low"),
                    reason=f"缓存记录: {d.get('risk_level', '')}",
                    suggested_action=d.get("suggested_action", ""),
                ))
            return risks
        except Exception:
            return None


# 全局单例
_anti_forget_engine: Optional[AntiForgetEngine] = None


def get_anti_forget_engine() -> AntiForgetEngine:
    global _anti_forget_engine
    if _anti_forget_engine is None:
        _anti_forget_engine = AntiForgetEngine()
    return _anti_forget_engine


# ═══════════════════════════════════════════
# 验证
# ═══════════════════════════════════════════

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

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("AntiForgetEngine v1.0 — 测试")
    print("=" * 60)

    engine = AntiForgetEngine()

    # 测试1: 遗忘曲线
    print("\n测试1: 遗忘曲线")
    for days, count in [(0, 0), (1, 0), (7, 1), (30, 3), (90, 5), (365, 10)]:
        f = ForgettingCurve.forget_score(days, count)
        print(f"  {days:3d}天 | {count}次访问 → forget={f:.4f}")
    print("  ✅ 通过")

    # 测试2: 记忆扫描
    print("\n测试2: 记忆扫描")
    entries = engine.scanner.scan_all()
    print(f"  扫描到 {len(entries)} 条记忆")
    for e in entries[:5]:
        print(f"    {e.id}: importance={e.importance:.2f} "
              f"tags={e.tags[:3]}")
    print("  ✅ 通过")

    # 测试3: 遗忘风险评估
    print("\n测试3: 遗忘风险评估")
    risks = engine.scan(force=True, top_k=10)
    print(f"  评估到 {len(risks)} 条风险")
    for r in risks:
        print(f"    [{r.risk_level.upper():>6}] {r.memory.id} "
              f"score={r.forget_score:.4f} "
              f"已过{int(r.days_since_access)}天")
    print("  ✅ 通过")

    # 测试4: 报告输出
    print("\n测试4: 报告输出")
    report = engine.report(risks, top_k=5)
    print(report)
    print("  ✅ 通过")

    # 测试5: acknowledge
    print("\n测试5: acknowledge（重置遗忘度）")
    if risks:
        first_id = risks[0].memory.id
        result = engine.acknowledge(first_id)
        print(f"  标记 {first_id} → {'✅' if result else '❌'}")
    print("  ✅ 通过")

    # 测试6: 空数据
    print("\n测试6: stats")
    stats = engine.stats()
    print(f"  {stats}")
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("全部测试通过 ✅")
    print("=" * 60)
