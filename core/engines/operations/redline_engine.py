"""
Crusheart Agent OS — Redline Engine 红线引擎 v1.0
=================================================

功能：
  1. 红线规则注册 — 从 SOUL.md 和各技能解析"红线"规则
  2. 预检阻断 — 在 pipeline stage 2.5 做预检，检测红线违反则硬阻断
  3. 模糊边界检测 — 检测到有红线但缺失兜底的规则，记录到审计日志
  4. UnifiedScorer 写入 — 每次阻断/告警写入统一评分通道

设计原则：
  - 红线规则优先级高于一切，命中必须硬阻断
  - 红线规则可以外部注册（SOUL.md 中定义），也可以代码注册
  - 引擎层不做规则改写，只做检测+阻断+记录

架构定位：
  - pipeline stage 2.5（skill_match 之后，anti_fake 之前）
  - 所有引擎/工具通过 RedlineEngine.check() 做预检
  - 阻断信息写入 UnifiedScorer
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
REDLINE_LOG = os.path.join(WORKSPACE, ".redline_engine", "breaches.jsonl")
FUZZY_LOG = os.path.join(WORKSPACE, ".redline_engine", "rules_without_fallback.jsonl")
STATE_FILE = os.path.join(WORKSPACE, ".redline_engine", "state.json")

# ── UnifiedScorer 统一评分通道 ──
try:
    from core.engines.quality.unified_scorer import get_scorer as _rl_get_scorer
except ImportError:
    _rl_get_scorer = None

class RedlineViolation(Exception):
    """红线违反异常 — 阻断执行"""
    def __init__(self, rule_name: str, reason: str, detail: str = ""):
        self.rule_name = rule_name
        self.reason = reason
        self.detail = detail
        super().__init__(f"[REDLINE] {rule_name}: {reason}")

class RedlineRule:
    """一条红线规则"""

    def __init__(self, name: str, description: str, patterns: List[str],
                 fallback: Optional[str] = None,
                 check_fn: Optional[Callable] = None,
                     source: str = "redline_engine",
                     severity: str = "hard_block"):  # hard_block | soft_block | warn
        self.name = name
        self.description = description
        self.patterns = patterns  # 触发关键词/正则列表
        self.fallback = fallback  # 兜底方案描述
        self.check_fn = check_fn  # 自定义检测函数
        self.source = source
        self.severity = severity  # hard_block:硬阻断, soft_block:重定向, warn:仅告警

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "pattern_count": len(self.patterns),
            "has_fallback": bool(self.fallback),
            "has_check_fn": self.check_fn is not None,
            "source": self.source,
            "severity": self.severity,
        }

class RedlineEngine:
    """
    红线引擎 — 管理所有红线规则+预检阻断
    """

    def __init__(self):
        self._rules: Dict[str, RedlineRule] = {}
        self._init_default_rules()
        os.makedirs(os.path.dirname(REDLINE_LOG), exist_ok=True)

    # ── 默认红线规则注册 ──────────────────────────

    def _init_default_rules(self):
        """注册默认红线规则（与 SOUL.md 保持一致）"""
        self.register_rule(RedlineRule(
            name="论文禁止compact",
            description="禁止压缩阅读学术/论文/资料文章，必须逐段完整阅读",
            patterns=[
                r"(?:论文|资料|文献|文章|arxiv|paper|学术).*(?:太长|太长不看|跳过|精简|概括)",
                r"(?:compact|压缩|浓缩).*(?:阅读|读|看|总结)",
            ],
            fallback="超上下文窗口：分批读取，每批完整读完再读下一批；超处理能力：告知用户从最关键部分开始完整阅读",
            severity="hard_block",
        ))
        self.register_rule(RedlineRule(
            name="禁止凭印象回答",
            description="凡涉及事实必须先查证，禁止凭印象回答",
            patterns=[
                r"我记得.*是",
                r"(?:应该|可能|大概|估计).*就是",
                r"不用查.*肯定",
            ],
            fallback="立即查询相关来源（文件/数据库/对话历史），查不到则告知用户",
            severity="hard_block",
        ))
        self.register_rule(RedlineRule(
            name="禁止绕过提案直接修改系统文件",
            description="系统文件修改必须经过提案+确认流程",
            patterns=[
                r"直接改.*(?:引擎|核心|系统|配置)",
                r"不用确认.*(?:改|写|更)",
                r"先改再说",
            ],
            fallback="先输出完整方案（改什么、怎么改、风险、回滚），等用户确认后执行",
            severity="hard_block",
        ))
        self.register_rule(RedlineRule(
            name="删除必须列清单确认",
            description="删除操作必须先列清单+用户确认",
            patterns=[
                r"把.*全删了",
                r"清空.*目录",
                r"删除.*所有",
            ],
            fallback="整理完整删除清单（含路径和原因）发给用户确认后才执行",
            severity="hard_block",
        ))
        self.register_rule(RedlineRule(
            name="禁止不查就重启",
            description="排查问题要先深挖根本原因再决定方案",
            patterns=[
                r"报错说重启.*那就重启",
                r"先重启试试",
                r"重启.*再说",
            ],
            fallback="先排查 Chrome 进程、锁文件、权限、版本兼容性，确认根因后再决定方案",
            severity="soft_block",
        ))

    # ── 规则管理 ──────────────────────────────

    def register_rule(self, rule: RedlineRule) -> str:
        """注册一条红线规则"""
        self._rules[rule.name] = rule
        return rule.name

    def unregister_rule(self, name: str) -> bool:
        """移除一条红线规则"""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def get_rule(self, name: str) -> Optional[RedlineRule]:
        return self._rules.get(name)

    def list_rules(self) -> List[dict]:
        return [r.to_dict() for r in self._rules.values()]

    def has_fallback(self) -> List[str]:
        """检查所有注册规则中哪些有兜底、哪些没有"""
        with_fallback = []
        without_fallback = []
        for name, rule in self._rules.items():
            if rule.fallback:
                with_fallback.append(name)
            else:
                without_fallback.append(name)
        return {"with_fallback": with_fallback, "without_fallback": without_fallback}

    # ── 预检阻断 ──────────────────────────────

    def check(self, text: str, context: Optional[dict] = None) -> Optional[dict]:
        """
        对输入文本做红线预检。

        Args:
            text: 用户消息或系统建议文本
            context: 可选上下文（包含 intent, recommended_skills, session_id 等）

        Returns:
            None 表示未触发红线
            dict 表示触发红线，包含：
                - violated: True
                - rule: 触发的规则名
                - severity: hard_block|soft_block|warn
                - reason: 触发原因
                - suggested_action: 推荐操作

        Raises:
            RedlineViolation: 仅当 severity=hard_block 且 context 中 raise_exception=True
        """
        if not text:
            return None

        matched_patterns = []
        for name, rule in self._rules.items():
            for pattern in rule.patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_patterns.append({
                        "rule": name,
                        "description": rule.description,
                        "pattern": pattern,
                        "severity": rule.severity,
                        "fallback": rule.fallback,
                    })
                    break  # 一条规则只触发一次

            # 自定义检测函数
            if rule.check_fn and not any(m["rule"] == name for m in matched_patterns):
                try:
                    if rule.check_fn(text, context):
                        matched_patterns.append({
                            "rule": name,
                            "description": rule.description,
                            "pattern": "(check_fn)",
                            "severity": rule.severity,
                            "fallback": rule.fallback,
                        })
                except Exception:
                    pass

        if not matched_patterns:
            return None

        # 按严重程度排序
        severity_order = {"hard_block": 0, "soft_block": 1, "warn": 2}
        matched_patterns.sort(key=lambda x: severity_order.get(x["severity"], 9))

        worst = matched_patterns[0]

        # 写入日志
        self._log_breach(text, worst, context or {})

        # 写入 UnifiedScorer
        self._record_to_unified(worst, context or {})

        # 检查是否有规则触发了但没有兜底
        for m in matched_patterns:
            if not m.get("fallback"):
                self._log_fuzzy(m)

        return {
            "violated": True,
            "rules": matched_patterns,
            "worst": worst,
            "suggested_action": worst.get("fallback", "请检查是否违反红线规则"),
        }

    # ── 内部日志 ──────────────────────────────

    def _log_breach(self, text: str, violation: dict, context: dict):
        """记录红线违反事件到 JSONL"""
        entry = {
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "ts_unix": int(time.time()),
            "text": text[:200],
            "rule": violation.get("rule", ""),
            "severity": violation.get("severity", "hard_block"),
            "session_id": context.get("session_id", ""),
            "context": str(context)[:200],
        }
        try:
            with open(REDLINE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _log_fuzzy(self, violation: dict):
        """记录缺少兜底的规则"""
        entry = {
            "ts": datetime.now(BEIJING_TZ).isoformat(),
            "rule": violation.get("rule", ""),
            "description": violation.get("description", ""),
            "severity": violation.get("severity", "hard_block"),
        }
        try:
            with open(FUZZY_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _record_to_unified(self, violation: dict, context: dict):
        """写入 UnifiedScorer"""
        if _rl_get_scorer is None:
            return
        try:
            scorer = _rl_get_scorer()
            severity_scores = {"hard_block": 1.0, "soft_block": 0.6, "warn": 0.3}
            score = severity_scores.get(violation.get("severity", "warn"), 0.5)
            scorer.record(
                source="redline_engine",
                dimension="risk_level",
                score=score,
                context=f"Redline breached: {violation.get('rule', '')}",
                tags=["redline", violation.get("severity", "warn"), violation.get("rule", "")],
            )
        except Exception:
            pass

    # ── 审计与状态 ────────────────────────────

    def get_stats(self) -> dict:
        """获取红线引擎统计"""
        breach_count = 0
        fuzzy_count = 0
        # 统计 breache
        if os.path.exists(REDLINE_LOG):
            try:
                with open(REDLINE_LOG, "r") as f:
                    for line in f:
                        if line.strip():
                            breach_count += 1
            except Exception:
                pass
        # 统计 fuzzy
        if os.path.exists(FUZZY_LOG):
            try:
                with open(FUZZY_LOG, "r") as f:
                    for line in f:
                        if line.strip():
                            fuzzy_count += 1
            except Exception:
                pass

        fallback_check = self.has_fallback()

        return {
            "total_rules": len(self._rules),
            "rules_with_fallback": len(fallback_check["with_fallback"]),
            "rules_without_fallback": len(fallback_check["without_fallback"]),
            "rules_without_fallback_list": fallback_check["without_fallback"],
            "total_breaches": breach_count,
            "rules_without_fallback_count": fuzzy_count,
        }

# ── 单例 ─────────────────────────────────────────────

def get_redline_engine() -> RedlineEngine:
    global _instance
    if _instance is None:
        _instance = RedlineEngine()
    return _instance

def init():
    """引擎初始化入口"""
    engine = get_redline_engine()
    stats = engine.get_stats()
    print(f"  🚨 RedlineEngine: {stats['total_rules']} 条红线规则, "
          f"{stats['rules_with_fallback']} 条有兜底, "
          f"{stats['rules_without_fallback']} 条缺兜底")
    return {
        "status": "ready",
        "stats": stats,
        "initialized_at": datetime.now(BEIJING_TZ).isoformat(),
    }

# ── Pipeline 阶段 2.5 ────────────────────────────────

def run_stage_redline(result: dict, user_message: str, context: dict = None) -> dict:
    """
    Pipeline stage 2.5: 红线预检
    在 skill_match 后、anti_fake 前执行。
    """
    try:
        engine = get_redline_engine()
        check_result = engine.check(user_message, context or {})
        if check_result:
            result["redline"] = check_result
        else:
            result["redline"] = {"violated": False}
    except Exception as e:
        result["redline"] = {"violated": False, "error": str(e)[:80]}
    return result

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

    import sys

    engine = get_redline_engine()

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        result = engine.check(text)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("✅ 未触发红线")
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = engine.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "rules":
        rules = engine.list_rules()
        print(json.dumps(rules, ensure_ascii=False, indent=2))
    else:
        result = init()
        print(json.dumps(result, ensure_ascii=False, indent=2))
