"""
DecisionCore — 分类路由 + 决策存档 合并引擎
功能：
  1. 分类路由：信息→事实/规则/经验/系统→路由到对应存储目标
  2. 决策存档：重要决策保存推理链，支持搜索回放
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ARCHIVE_DIR = os.path.join(WORKSPACE, ".decision_archive")
ARCHIVE_INDEX_FILE = os.path.join(ARCHIVE_DIR, "index.json")
MAX_ARCHIVE_SIZE = 500

# ======================== 分类路由 ========================

class ClassificationResult:
    def __init__(self, category: str, target: str, confidence: float,
                 reasoning: str, sub_type: Optional[str] = None,
                 cross_refs: Optional[list] = None):
        self.category = category
        self.target = target
        self.confidence = confidence
        self.reasoning = reasoning
        self.sub_type = sub_type
        self.cross_refs = cross_refs or []
        self.timestamp = datetime.now(BEIJING_TZ).isoformat()

    def to_dict(self):
        return {
            "category": self.category, "target": self.target,
            "confidence": self.confidence, "reasoning": self.reasoning,
            "sub_type": self.sub_type, "cross_refs": self.cross_refs,
            "timestamp": self.timestamp,
        }

    def __repr__(self):
        return f"[{self.category}] → {self.target} (信心: {self.confidence:.0%})"

class Classifier:
    """分类路由：判断一条信息属于哪类，路由到哪"""

    CATEGORIES = {
        "fact":       {"name": "事实类",   "targets": ["USER.md", "memory_layer"]},
        "rule":       {"name": "规则类",   "targets": ["SOUL.md"]},
        "experience": {"name": "经验类",   "targets": ["self_evolution_skill"]},
        "system":     {"name": "系统类",   "targets": ["code", "config", "plugin"]},
    }

    # 关键词规则
    KEYWORD_RULES = {
        "fact": [
            r"(?:住|在|位于|来自)\s*[^\s，。]{2,}(?:区|市|省|县)",
            r"(?:姓名|称呼|叫|名字)\s*[:：]?\s*\S+",
            r"(?:专业|学校|大学|年级|班级)", r"(?:生日|出生|年龄|岁)",
            r"(?:联系|电话|手机|邮箱|微信|QQ)", r"(?:喜欢|爱好|兴趣|习惯)",
            r"(?:过敏|忌口|不吃|不能吃)", r"地点|位置|坐标",
        ],
        "rule": [
            r"(?:必须|禁止|不得|不允许|绝对|永远)", r"(?:规则|铁律|原则|红线|底线)",
            r"(?:删.*前|确认|审核|批准)", r"(?:安全|保密|隐私|权限)",
        ],
        "experience": [
            r"(?:排查|排错|调试|诊断|定位).*(?:路径|步骤|方法|技巧|经验)",
            r"(?:踩坑|翻车|教训|血泪|吃过亏)",
            r"(?:下次|以后).*(?:注意|记住|避免|不要)",
            r"(?:工具|脚本|命令).*(?:用法|姿势|技巧|参数)",
            r"(?:流程|步骤|顺序).*(?:优化|改进|简化)",
        ],
        "system": [
            r"(?:代码|模块|引擎|插件|skill)", r"(?:配置|config|设置)",
            r"(?:架构|重构|优化|重写)", r"(?:安装|卸载|升级|降级|迁移)",
        ],
    }

    def classify(self, text: str, context: Optional[dict] = None) -> ClassificationResult:
        text = text.strip()
        if not text:
            return ClassificationResult("unknown", "", 0.0, "空文本无法分类")

        scores, reasonings = {}, {}

        # 关键词初筛
        for cat, patterns in self.KEYWORD_RULES.items():
            matches = sum(1 for p in patterns if re.search(p, text))
            if matches > 0:
                scores[cat] = min(0.3 + matches * 0.1, 0.5)
                reasonings[cat] = f"关键词匹配到 {matches} 个 {cat} 类模式"

        # 语义规则
        semantic = self._semantic_judge(text, context)
        for cat, r in semantic.items():
            if r["score"] > scores.get(cat, 0):
                scores[cat] = r["score"]
                reasonings[cat] = r["reasoning"]

        if not scores:
            return ClassificationResult("unknown", "", 0.0, "未匹配任何分类规则")

        best_cat = max(scores, key=scores.get)
        target = self._resolve_target(best_cat, text, context)
        cross_refs = self._check_cross_refs(best_cat, scores)

        return ClassificationResult(
            category=best_cat, target=target,
            confidence=scores[best_cat], reasoning=reasonings.get(best_cat, ""),
            sub_type=self._sub_type(best_cat, text), cross_refs=cross_refs,
        )

    def _semantic_judge(self, text: str, _ctx=None) -> dict:
        results = {}
        checks = {
            "fact": [
                (r"(?:我|笔者).*(?:住|在|用|是|学)", 1),
                (r"(?:年龄|生日|出生|来自)", 2),
                (r"(?:喜欢|讨厌|偏好|习惯)", 1),
                (r"(?:联系方式|电话|地址|邮箱)", 2),
            ],
            "rule": [
                (r"(?:以后|之后|每次|任何时候).*(?:要|必须|需要)", 2),
                (r"(?:绝对不能|永远不要|禁止)", 3),
                (r"(?:记住|记住这条|形成规范)", 2),
                (r"(?:安全|保密|隐私)", 1),
            ],
            "experience": [
                (r"(?:排查|排错|调试)", 2),
                (r"(?:踩坑|翻车|教训)", 2),
                (r"(?:下次|以后|建议).*(?:先|试着|可以)", 1),
                (r"(?:工具|技巧|姿势|方法)", 1),
            ],
            "system": [
                (r"(?:需要|建议|应该).*(?:改|加|添|创建|删除|修)", 1),
                (r"(?:引擎|模块|插件|skill)", 1),
                (r"(?:配置|config|架构)", 1),
                (r"(?:代码|脚本|文件).*(?:修改|添加|删除|创建)", 2),
            ],
        }
        for cat, patterns in checks.items():
            total = sum(weight for pat, weight in patterns if re.search(pat, text))
            if total >= 2:
                results[cat] = {
                    "score": min(0.5 + total * 0.1, 0.9 if cat == "rule" else 0.85),
                    "reasoning": f"语义匹配到 {total} 个 {cat} 类指示器",
                }
        return results

    def _resolve_target(self, cat: str, text: str, _ctx=None) -> str:
        if cat == "fact":
            return "USER.md" if re.search(r"(?:住|地址|位置|坐标|学校|专业|生日)", text) else "memory_layer"
        if cat == "rule":   return "SOUL.md"
        if cat == "experience": return "self_evolution_skill"
        if cat == "system":
            if re.search(r"(?:插件|skill|安装)", text): return "plugin"
            if re.search(r"(?:配置|config|json|yaml|toml)", text): return "config"
            return "code"
        return ""

    def _check_cross_refs(self, best: str, scores: dict) -> list:
        return [{"category": c, "score": s} for c, s in scores.items()
                if c != best and s >= 0.4]

    @staticmethod
    def _sub_type(cat: str, text: str) -> Optional[str]:
        mapping = {
            "fact":       {"user_profile": "姓名|称呼|年龄|生日|专业|学校", "environment": "坐标|位置|地址|设备|系统",
                           "preference": "喜欢|爱好|偏好|讨厌|习惯"},
            "rule":       {"safety": "安全|保密|隐私|红线", "operation": "删|改|创.*前|后|时", "ethics": "诚实|原则|底线|价值观"},
            "experience": {"debug": "排查|排错|调试|定位", "tool": "工具|脚本|命令|用法", "workflow": "流程|步骤|顺序|优化"},
            "system":     {"code_change": "代码|模块|引擎|文件", "config_change": "配置|config", "architecture": "架构|重构|设计|方案"},
        }
        for sub, pat in mapping.get(cat, {}).items():
            if re.search(pat, text): return sub
        return None

# ======================== 决策存档 ========================

class DecisionRecord:
    def __init__(self, record_id: str = None):
        self.id = record_id or uuid.uuid4().hex[:12]
        self.timestamp = datetime.now(BEIJING_TZ).isoformat()
        self.context = ""
        self.trigger = ""
        self.options = []
        self.reasoning = ""
        self.decision = ""
        self.alternatives_discarded = []
        self.tags = []
        self.category = ""
        self.outcome = None
        self.related_files = []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        r = cls(d.get("id"))
        for k, v in d.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r

class DecisionArchiver:
    """决策存档 + 分类路由入口"""

    def __init__(self):
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        self._classifier = Classifier()
        self._index = self._load_index()

    # ---- 外部入口 ----

    def process(self, text: str, context: Optional[dict] = None) -> dict:
        """
        全流程：分类 → 判断是否需要存档 → 返回结果
        """
        # 1. 先分类
        classification = self._classifier.classify(text, context)

        # 2. 判断是否值得存档
        if classification.category == "unknown":
            return {"classified": classification.to_dict(), "archived": False, "reason": "未分类，不存档"}

        should_archive = self._should_archive(text, classification)
        if not should_archive:
            return {"classified": classification.to_dict(), "archived": False, "reason": "无需存档"}

        # 3. 自动构建存档记录
        record = self._build_record(text, classification, context)
        record_id = self._save(record)

        return {
            "classified": classification.to_dict(),
            "archived": True,
            "record_id": record_id,
            "category": classification.category,
            "target": classification.target,
        }

    def classify(self, text: str, context: Optional[dict] = None) -> ClassificationResult:
        """仅分类，不存档"""
        return self._classifier.classify(text, context)

    def archive_decision(self, record: DecisionRecord) -> str:
        """直接存档一条预制决策"""
        return self._save(record)

    def get(self, record_id: str) -> Optional[DecisionRecord]:
        fp = os.path.join(ARCHIVE_DIR, f"{record_id}.json")
        if not os.path.exists(fp):
            return None
        with open(fp, encoding="utf-8") as f:
            return DecisionRecord.from_dict(json.load(f))

    def search(self, query: str, limit: int = 10) -> List[dict]:
        q = query.lower()
        results = []
        for e in self._index.values():
            if (q in e.get("context", "").lower() or q in e.get("decision", "").lower()
                    or q in " ".join(e.get("tags", [])).lower()):
                results.append(e)
                if len(results) >= limit:
                    break
        return results

    def replay(self, record_id: str) -> Optional[str]:
        rec = self.get(record_id)
        if not rec:
            return None
        lines = [
            f"【决策回放】{rec.context}",
            f"时间: {rec.timestamp}",
            f"分类: {rec.category}",
            f"触发: {rec.trigger}",
            "", "备选方案:",
        ]
        for i, o in enumerate(rec.options, 1):
            lines.append(f"  {i}. {o}")
        lines.extend(["", f"推理过程: {rec.reasoning}", "", f"最终决定: {rec.decision}"])
        if rec.alternatives_discarded:
            lines.extend(["", "已排除的方案:"])
            for a in rec.alternatives_discarded:
                lines.append(f"  ❌ {a}")
        if rec.outcome:
            lines.extend(["", f"效果追踪: {rec.outcome}"])
        return "\n".join(lines)

    def update_outcome(self, record_id: str, outcome: str):
        rec = self.get(record_id)
        if rec:
            rec.outcome = outcome
            self._save(rec)

    def stats(self) -> dict:
        total = len(self._index)
        by_cat = {}
        for e in self._index.values():
            c = e.get("category", "unknown")
            by_cat[c] = by_cat.get(c, 0) + 1
        return {
            "total": total,
            "by_category": by_cat,
            "with_outcome": sum(1 for e in self._index.values() if e.get("outcome")),
        }

    # ---- 内部 ----

    def _should_archive(self, text: str, classification: ClassificationResult) -> bool:
        """判断是否值得存档"""
        # 规则/经验/系统类且置信度>=0.5 → 自动存档
        if classification.category in ("rule", "experience", "system") and classification.confidence >= 0.5:
            return True
        # 事实类用户档案 → 存档
        if classification.category == "fact" and classification.target == "USER.md":
            return True
        # 含决策信号的
        signals = [
            r"(?:确认|就这样|按这个来|就这个方案|可以了|就这么办)",
            r"(?:选了|选择|决定|采用|使用)",
            r"(?:因为.*所以|由于.*因此)",
        ]
        if any(re.search(p, text) for p in signals):
            return True
        return False

    def _build_record(self, text: str, classification: ClassificationResult,
                      context: Optional[dict] = None) -> DecisionRecord:
        rec = DecisionRecord()
        rec.context = text[:100]
        rec.category = classification.category
        rec.tags = [classification.category, classification.sub_type or ""]
        rec.tags = [t for t in rec.tags if t]
        if context:
            rec.trigger = context.get("trigger", "")
        return rec

    def _save(self, record: DecisionRecord) -> str:
        fp = os.path.join(ARCHIVE_DIR, f"{record.id}.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        self._index[record.id] = {
            "id": record.id, "timestamp": record.timestamp,
            "context": record.context[:60], "decision": record.decision[:40],
            "category": record.category, "tags": record.tags,
            "outcome": record.outcome,
        }
        self._save_index()
        self._enforce_capacity()
        return record.id

    def _load_index(self) -> dict:
        if os.path.exists(ARCHIVE_INDEX_FILE):
            with open(ARCHIVE_INDEX_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_index(self):
        with open(ARCHIVE_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _enforce_capacity(self):
        if len(self._index) <= MAX_ARCHIVE_SIZE:
            return
        sorted_ids = sorted(self._index, key=lambda x: self._index[x].get("timestamp", ""))
        for rid in sorted_ids[:len(self._index) - MAX_ARCHIVE_SIZE]:
            fp = os.path.join(ARCHIVE_DIR, f"{rid}.json")
            if os.path.exists(fp):
                os.remove(fp)
            del self._index[rid]
        self._save_index()

# 单例

def get_archiver():
    global _instance
    if _instance is None:
        _instance = DecisionArchiver()
    return _instance

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

    arc = get_archiver()
    print("=== 分类路由测试 ===")
    tests = [
        "用户示例区域，某专业大一",
        "删文件前必须列清单给用户确认",
        "排查Chrome先看锁文件，不要直接重启gateway",
        "需要给workflow引擎加一个并发控制模块",
        "今天天气不错",
        "必须禁止自动执行删除操作，要用户确认后才能删",
        "我生日3月7日，2006年的",
        "下次排查网络问题先ping再traceroute",
    ]
    for t in tests:
        r = arc.classify(t)
        print(f"  {t[:38]:<40}{r}")

    print("\n=== 全流程测试 (分类+存档) ===")
    text = "排查Chrome先看锁文件，不要直接重启gateway"
    result = arc.process(text, {"trigger": "用户问Chrome问题"})
    print(f"  入参: {text}")
    print(f"  classified: [{result['classified']['category']}] → {result['classified']['target']}")
    print(f"  archived: {result['archived']} (id: {result.get('record_id', 'N/A')})")

    # 直接存一个决策
    print("\n=== 决策存档测试 ===")
    rec = DecisionRecord()
    rec.context = "示例决策场景"
    rec.trigger = "用户选择方案"
    rec.options = ["方案A", "方案B"]
    rec.reasoning = "方案B更优"
    rec.decision = "方案B"
    rec.tags = ["决策", "示例"]
    rec.decision = "方案B"
    rec.tags = ["session设计", "跨渠道", "架构"]
    rec.category = "system"
    rid = arc.archive_decision(rec)
    print(f"  存档ID: {rid}")

    results = arc.search("session")
    print(f"  搜索'session': {len(results)} 条")

    replay = arc.replay(rid)
    print(f"  回放: {len(replay)} 字符 ✓")

    stats = arc.stats()
    print(f"  统计: 共{stats['total']}条, 含outcome: {stats['with_outcome']}条")
    print(f"  分类分布: {stats['by_category']}")
