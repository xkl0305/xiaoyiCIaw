"""
Crusheart Agent OS — Identity Drift Guard v1.0
身份漂移检测引擎

解决的问题：
  SOUL.md / IDENTITY.md 通过 self_evolution 持续被修改，但没有任何机制检查
  「有没有把关键的安全红线、核心行为规则悄悄改掉了」。

  本引擎：
  1. 首次运行时，对 SOUL.md 生成一份「基线指纹」（关键规则的提取快照）
  2. 此后每次会话启动时，对比当前 SOUL.md 与基线，计算漂移分
  3. 漂移分超过阈值或检测到核心规则丢失，发出告警
  4. 只检测「安全规则是否削弱」，允许风格/措辞更新

调用方式：
  from core.engines.quality.identity_drift_guard import get_drift_guard
  guard = get_drift_guard()

  # 首次运行/重置基线
  guard.create_baseline()

  # 每次会话启动时检查
  result = guard.check_drift()
  if result["status"] != "safe":
      print(result["report"])
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
EXTRAS_DIR = os.path.join(WORKSPACE, ".state")
BASELINE_FILE = os.path.join(EXTRAS_DIR, "identity_baseline.json")
DRIFT_LOG_FILE = os.path.join(EXTRAS_DIR, "drift_log.jsonl")
SOUL_PATH = os.path.join(WORKSPACE, "SOUL.md")
IDENTITY_PATH = os.path.join(WORKSPACE, "IDENTITY.md")

os.makedirs(EXTRAS_DIR, exist_ok=True)


def _now_str() -> str:
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ================================================================
# 规则提取器
# ================================================================
class RuleExtractor:
    """
    从 SOUL.md 中提取关键规则的结构化表示。
    不做字节级比对，而是提取「规则语义标记」。
    """

    SAFETY_ANCHORS = [
        "请慎重",
        "个人隐私",
        "公司机密",
        "敏感数据",
        "保密协议",
        "安全红线",
        "禁止外传",
    ]

    BEHAVIOR_ANCHORS = [
        "直接帮",
        "有自己的判断",
        "先自己查",
        "能力赢得信任",
    ]

    DANGER_PATTERNS = [
        r"bypass.*safety",
        r"ignore.*rule",
        r"override.*security",
        r"disable.*validator",
        r"skip.*confirm",
        r"绕过.*安全",
        r"禁用.*校验",
        r"忽略.*规则",
    ]

    def extract(self, text: str) -> dict:
        section_hashes = self._extract_section_hashes(text)

        safety_hits = {
            anchor: bool(re.search(anchor, text, re.IGNORECASE))
            for anchor in self.SAFETY_ANCHORS
        }

        behavior_hits = {
            anchor: bool(re.search(anchor, text, re.IGNORECASE))
            for anchor in self.BEHAVIOR_ANCHORS
        }

        danger_hits = [
            pattern for pattern in self.DANGER_PATTERNS
            if re.search(pattern, text, re.IGNORECASE)
        ]

        headers = re.findall(r'^#{1,3}\s+.+', text, re.MULTILINE)
        prohibit_markers = len(re.findall(r'❌|禁止|绝对不|never|NEVER|不得|不能|严禁', text))
        rule_count = len(re.findall(r'^[-*]\s+\*\*|^\d+\.\s+\*\*', text, re.MULTILINE))

        return {
            "section_hashes": section_hashes,
            "safety_anchor_hits": safety_hits,
            "safety_anchor_total": sum(1 for v in safety_hits.values() if v),
            "behavior_anchor_hits": behavior_hits,
            "behavior_anchor_total": sum(1 for v in behavior_hits.values() if v),
            "danger_patterns_found": danger_hits,
            "header_count": len(headers),
            "prohibit_marker_count": prohibit_markers,
            "rule_count": rule_count,
            "char_count": len(text),
            "word_count": len(text.split()),
        }

    def _extract_section_hashes(self, text: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        current_section = "header"
        current_content = []

        for line in text.splitlines():
            if line.startswith("## ") or line.startswith("# "):
                if current_content:
                    content = "\n".join(current_content)
                    sections[current_section] = hashlib.md5(content.encode()).hexdigest()[:8]
                current_section = line[3:].strip()[:40]
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = hashlib.md5(
                "\n".join(current_content).encode()
            ).hexdigest()[:8]

        return sections


# ================================================================
# 漂移计算器
# ================================================================
class DriftCalculator:
    """
    计算基线和当前状态之间的漂移分（0.0~1.0）。
    0.0 = 完全一致，1.0 = 完全不同
    """

    def calculate(self, baseline: dict, current: dict) -> Tuple[float, List[str]]:
        issues = []
        scores = []

        # 1. 安全锚点（高权重）
        baseline_safety = baseline.get("safety_anchor_total", 0)
        current_safety = current.get("safety_anchor_total", 0)
        if current_safety < baseline_safety:
            missing = baseline_safety - current_safety
            issues.append(f"🔴 安全锚点减少了 {missing} 个（基线:{baseline_safety} → 当前:{current_safety}）")
            scores.append(0.4 * (missing / max(baseline_safety, 1)))
        else:
            scores.append(0.0)

        # 2. 危险模式
        danger_found = current.get("danger_patterns_found", [])
        if danger_found:
            issues.append(f"🚨 检测到危险模式: {danger_found}")
            scores.append(0.5)
        else:
            scores.append(0.0)

        # 3. 禁止标记数量
        baseline_prohibit = baseline.get("prohibit_marker_count", 0)
        current_prohibit = current.get("prohibit_marker_count", 0)
        if baseline_prohibit > 0 and current_prohibit < baseline_prohibit * 0.7:
            issues.append(f"⚠️ 禁止/❌标记大幅减少（基线:{baseline_prohibit} → 当前:{current_prohibit}）")
            scores.append(0.2)
        else:
            scores.append(0.0)

        # 4. 文档结构变化
        baseline_sections = baseline.get("section_hashes", {})
        current_sections = current.get("section_hashes", {})
        changed_sections = []
        for section, h in baseline_sections.items():
            if section in current_sections and current_sections[section] != h:
                changed_sections.append(section)
            elif section not in current_sections:
                changed_sections.append(f"{section}（已删除）")
        if changed_sections:
            issues.append(f"📝 章节内容变化: {', '.join(changed_sections[:5])}")
            scores.append(min(0.15, len(changed_sections) * 0.03))
        else:
            scores.append(0.0)

        # 5. 文档长度
        baseline_chars = baseline.get("char_count", 0)
        current_chars = current.get("char_count", 0)
        if baseline_chars > 100 and current_chars < baseline_chars * 0.6:
            issues.append(f"⚠️ 文档大幅缩短（基线:{baseline_chars}字 → 当前:{current_chars}字）")
            scores.append(0.15)
        else:
            scores.append(0.0)

        total_drift = min(1.0, sum(scores))
        return round(total_drift, 3), issues


# ================================================================
# IdentityDriftGuard — 主引擎
# ================================================================
class IdentityDriftGuard:
    WARN_THRESHOLD = 0.15
    ALERT_THRESHOLD = 0.35
    BLOCK_THRESHOLD = 0.60

    def __init__(self):
        self.extractor = RuleExtractor()
        self.calculator = DriftCalculator()

    def create_baseline(self, force: bool = False) -> dict:
        if os.path.exists(BASELINE_FILE) and not force:
            with open(BASELINE_FILE, encoding="utf-8") as f:
                existing = json.load(f)
            print(f"✅ 基线已存在（建立于 {existing.get('created_at', '未知')}），使用 force=True 覆盖")
            return existing

        soul_text = self._read_soul()
        if not soul_text:
            print("⚠️ SOUL.md 不存在，无法建立基线")
            return {}

        fingerprint = self.extractor.extract(soul_text)
        baseline = {
            "schema": "baseline_v1",
            "created_at": _now_str(),
            "soul_path": SOUL_PATH,
            "fingerprint": fingerprint,
        }

        with open(BASELINE_FILE, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)

        print(f"✅ 身份基线已建立（{_now_str()}）")
        print(f"   安全锚点命中: {fingerprint['safety_anchor_total']}/{len(RuleExtractor.SAFETY_ANCHORS)}")
        print(f"   禁止标记数: {fingerprint['prohibit_marker_count']}")
        print(f"   文档规模: {fingerprint['char_count']} 字符")
        return baseline

    def check_drift(self) -> dict:
        if not os.path.exists(BASELINE_FILE):
            self.create_baseline()
            return {
                "status": "baseline_created",
                "drift_score": 0.0,
                "issues": [],
                "report": "✅ 首次运行，已自动建立身份基线，下次会话将开始检测漂移。",
            }

        with open(BASELINE_FILE, encoding="utf-8") as f:
            baseline_data = json.load(f)
        baseline_fp = baseline_data.get("fingerprint", {})

        soul_text = self._read_soul()
        if not soul_text:
            return {"status": "error", "drift_score": 0.0, "issues": ["SOUL.md 读取失败"], "report": "⚠️ SOUL.md 读取失败"}

        current_fp = self.extractor.extract(soul_text)
        drift_score, issues = self.calculator.calculate(baseline_fp, current_fp)

        if drift_score >= self.BLOCK_THRESHOLD:
            status = "critical"
            icon = "🚨"
        elif drift_score >= self.ALERT_THRESHOLD:
            status = "alert"
            icon = "🔴"
        elif drift_score >= self.WARN_THRESHOLD:
            status = "warn"
            icon = "⚠️"
        else:
            status = "safe"
            icon = "✅"

        report_lines = [
            f"{icon} 身份漂移检测 [{_now_str()}]",
            f"   漂移分: {drift_score:.3f}（阈值: warn={self.WARN_THRESHOLD} / alert={self.ALERT_THRESHOLD} / critical={self.BLOCK_THRESHOLD}）",
        ]
        if issues:
            report_lines.append("   检测到的问题:")
            for issue in issues:
                report_lines.append(f"     {issue}")
        else:
            report_lines.append("   无异常，身份规则完整。")

        if status == "critical":
            report_lines.append("\n   ⚠️ 建议立即执行 guard.create_baseline(force=True) 确认变更，或恢复 SOUL.md。")
        elif status in ("alert", "warn"):
            report_lines.append("\n   建议检查最近的 self_evolution 修改记录。")

        report = "\n".join(report_lines)
        self._log_drift(status, drift_score, issues)

        return {
            "status": status,
            "drift_score": drift_score,
            "issues": issues,
            "baseline_created_at": baseline_data.get("created_at", ""),
            "report": report,
        }

    def update_baseline(self) -> dict:
        return self.create_baseline(force=True)

    def get_baseline_summary(self) -> dict:
        if not os.path.exists(BASELINE_FILE):
            return {"status": "no_baseline", "message": "尚未建立基线"}
        with open(BASELINE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        fp = data.get("fingerprint", {})
        return {
            "status": "exists",
            "created_at": data.get("created_at", ""),
            "safety_anchors": f"{fp.get('safety_anchor_total', 0)}/{len(RuleExtractor.SAFETY_ANCHORS)}",
            "prohibit_markers": fp.get("prohibit_marker_count", 0),
            "char_count": fp.get("char_count", 0),
            "sections": list(fp.get("section_hashes", {}).keys()),
        }

    def get_drift_history(self, limit: int = 10) -> List[dict]:
        if not os.path.exists(DRIFT_LOG_FILE):
            return []
        records = []
        with open(DRIFT_LOG_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except Exception:
                    continue
        return records[-limit:]

    def _read_soul(self) -> str:
        content_parts = []
        if os.path.exists(SOUL_PATH):
            try:
                with open(SOUL_PATH, encoding="utf-8") as f:
                    content_parts.append("=== SOUL.md ===")
                    content_parts.append(f.read())
            except Exception:
                pass
        if os.path.exists(IDENTITY_PATH):
            try:
                with open(IDENTITY_PATH, encoding="utf-8") as f:
                    content_parts.append("\n=== IDENTITY.md ===")
                    content_parts.append(f.read())
            except Exception:
                pass
        return "\n".join(content_parts) if content_parts else ""

    def _log_drift(self, status: str, score: float, issues: List[str]):
        record = {
            "ts": _now_str(),
            "status": status,
            "drift_score": score,
            "issue_count": len(issues),
            "issues_brief": [i[:60] for i in issues[:3]],
        }
        with open(DRIFT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ================================================================
# #45: 统一单例 — 委托到 SingletonRegistry
# ================================================================


def get_drift_guard() -> IdentityDriftGuard:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(IdentityDriftGuard)


def init() -> IdentityDriftGuard:
    guard = get_drift_guard()
    if not os.path.exists(BASELINE_FILE):
        guard.create_baseline()
    return guard


def check_on_startup() -> dict:
    guard = get_drift_guard()
    result = guard.check_drift()
    if result["status"] not in ("safe", "baseline_created"):
        print(result["report"])
    return result
