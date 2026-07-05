"""
Crusheart Agent OS — Anti-Fake Pro 全链路防幻觉校验引擎 v4.0
v4.0 核心改进：逐句引用精确性校验，区分"通用引用"与"精确引用"
    - 新增：引用-声明距离校验（检测数据是否真的有就近引用）
    - 新增：段落引用分析（检测"通篇一个[1]"绕过）
    - 新增：统计声明精确引用校验
    - 新增：引用列表 vs 内联引用区分
"""

import re, os, json, time, hashlib, random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from collections import Counter
import logging

# 引用集成：八条铁律+樱花准则（行为前置检查）
# three_rules 负责"做得对"（回答前检查），本引擎负责"说得对"（内容真实性校验）
try:
    from core.engines.quality.iron_rules import validate_response_needed, get_rules_text, trigger_kind
    _THREE_RULES_AVAILABLE = True
except ImportError:
    _THREE_RULES_AVAILABLE = False

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
CREDIT_DB_PATH = os.path.join(WORKSPACE, ".hooks", "source_credit_db.json")
ALERT_LOG_PATH = os.path.join(WORKSPACE, ".hooks", "anti_fake_alerts.jsonl")
SOURCE_TRACE_PATH = os.path.join(WORKSPACE, ".hooks", "source_trace.jsonl")
os.makedirs(os.path.dirname(CREDIT_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(SOURCE_TRACE_PATH), exist_ok=True)

AUTHORITY_SCORES = {
    ".gov.cn": 100, ".gov": 95, ".edu.cn": 95, ".edu": 90,
    "stats.gov.cn": 100, "pbc.gov.cn": 100, "moe.gov.cn": 100,
    "who.int": 100, "worldbank.org": 100, "imf.org": 100,
    "un.org": 100, "oecd.org": 100,
    "wikipedia.org": 70, "baike.baidu.com": 70,
    ".org.cn": 60, ".ac.cn": 85, ".org": 50,
    "zhihu.com": 40, "douban.com": 30,
    ".com.cn": 40, ".com": 30, ".net": 25,
    "blog.csdn.net": 20,
}

UNCERTAINTY_PATTERNS = [
    r"可能", r"据说", r"传闻", r"大概", r"左右", r"约",
    r"maybe", r"perhaps", r"possibly", r"allegedly", r"approximately",
    r"might", r"could be", r"seems",
]

VAGUE_NUMBERS = [
    r"\d+%以上", r"\d+%左右", r"大量", r"许多", r"一些",
    r"some", r"many", r"most", r"a lot", r"numerous",
]

# ================================================================
# v4.0 新增：声明-引用分析模块
# ================================================================

# 事实声明模式（含具体数据的句子特征）
FACT_CLAIM_PATTERNS = [
    # 数字声明
    r'\d+[\.\d]*\s*(?:量子比特|美元|万|亿|%|毫秒|微秒|纳秒|毫开|毫开尔文|km|m|GB|TB|MHz|GHz)',
    r'\d+[\.\d]*\s*(?:qubit|dollar|million|billion|percent|ms|μs|ns|mK|km)',
    r'(?:约|约合|约在|约等于)\s*\d+',
    # 具体事件
    r'(?:20\d{2})年(?:1[0-2]|0?[1-9])月',
    r'(?:20\d{2})年',
    r'(?:IBM|Google|Microsoft|Intel|Quantinuum|Amazon|华为|百度|阿里)\w*[：:].*',
    # 数据范围
    r'\d+[\-~]\d+',
    # 机构声明
    r'(?:据|根据|按照|来自)\s*(?:IBM|Google|Nature|Science|MIT|Stanford)',
]

# 通用引用标记（可能不是精确引用）
CITATION_MARKER_GENERIC = re.compile(r'\[\d+(?:,\s*\d+)*\]')

# 精确引用标记（紧跟在声明后的引用）
CITATION_MARKER_EXACT = re.compile(r'(?:\.|。|\s)\[(\d+)\]')

# 段落尾引用检测（整段结束后统一标注的引用）
PARAGRAPH_END_CITATION = re.compile(r'[。\.][\s\n]*\[[\d,\s]+\]')


class CitationAnalyzer:
    """v4.0 新增：逐句引用精确性分析"""

    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """将文本分割为句子列表"""
        # 先按句号/句点分割，保留引号内、括号内的完整性
        raw = re.split(r'(?<=[。\.！？!?])\s+', text)
        sentences = []
        for r in raw:
            r = r.strip()
            if len(r) > 10:  # 过滤过短的片段
                sentences.append(r)
        return sentences

    @staticmethod
    def has_generic_citation(text: str) -> bool:
        """检查文本是否有通用引用标记 [1], [1,2,3]"""
        return bool(CITATION_MARKER_GENERIC.search(text))

    @staticmethod
    def has_exact_citation(sentence: str) -> bool:
        """检查单个句子是否有精确引用标记 """
        return bool(CITATION_MARKER_EXACT.search(sentence))

    @staticmethod
    def has_url_citation(text: str) -> bool:
        """检查是否有 URL 引用"""
        return bool(re.search(r'https?://[^\s,。，\)]+', text))

    @staticmethod
    def has_named_source(text: str) -> bool:
        """检查是否有具名来源引用（据XX、来源于XX等）"""
        named = [
            r'(?:据|根据|按照|来自|引自|来源|摘自|参考)\s*(?:[A-Za-z\u4e00-\u9fff]{2,})',
            r'(?:详见|参见|见)\s*(?:[A-Za-z\u4e00-\u9fff]{2,})',
        ]
        return any(re.search(p, text) for p in named)

    @classmethod
    def is_sentence_with_claim(cls, sentence: str) -> bool:
        """检查句子是否包含需要验证的事实声明"""
        return any(re.search(p, sentence) for p in FACT_CLAIM_PATTERNS)

    @classmethod
    def find_paragraph_refs(cls, text: str) -> List[Tuple[int, int]]:
        """找到段落尾引用的位置（段落后统一标注引用）"""
        refs = []
        for m in PARAGRAPH_END_CITATION.finditer(text):
            refs.append((m.start(), m.end()))
        return refs

    @classmethod
    def analyze_citation_precision(cls, text: str) -> Dict:
        """
        分析整篇文本的引用精确度。
        返回：
            - total_claims: 需要引用的事实声明数
            - claims_with_nearby_citation: 有就近引用的声明数
            - claims_without_citation: 无引用的声明数
            - citation_precision: 引用精确度比例
            - has_generic_padding: 是否有"通篇一个引用"问题
            - paragraph_end_only: 是否只在段落结尾标注引用
            - warning_messages: 警告信息列表
        """
        sentences = cls.split_into_sentences(text)
        total_claims = 0
        claims_with_citation = 0
        claims_without_citation = 0
        claim_details = []

        # 检测是否为"段落尾统一引用"
        para_ref_count = len(cls.find_paragraph_refs(text))
        has_para_end_citations = para_ref_count > 0

        # 检测是否有通用引用标记
        has_generic = cls.has_generic_citation(text)

        # 逐句分析
        for i, sent in enumerate(sentences):
            is_claim = cls.is_sentence_with_claim(sent)
            if is_claim:
                total_claims += 1
                has_exact = cls.has_exact_citation(sent)
                has_url = cls.has_url_citation(sent)
                has_named = cls.has_named_source(sent)
                has_any_citation = has_exact or has_url or has_named

                if has_any_citation:
                    claims_with_citation += 1
                else:
                    claims_without_citation += 1

                claim_details.append({
                    "sentence_index": i,
                    "preview": sent[:80],
                    "has_exact_citation": has_exact,
                    "has_url_citation": has_url,
                    "has_named_source": has_named,
                })

        # 计算精确度
        citation_precision = claims_with_citation / total_claims if total_claims > 0 else 1.0

        # 检测"通篇一个引用"问题：有引用标记但几乎所有声明都没有精确引用
        warnings = []
        if has_generic and citation_precision < 0.5 and total_claims >= 2:
            warnings.append("⚠️ 检测到通用引用标记但多数声明缺少精确引用——引用可能未与具体声明关联")
        if has_para_end_citations and citation_precision < 0.3:
            warnings.append("⚠️ 引用仅在段落末尾统一标注，未与具体声明配对——可能被'参考列表式引用'绕过")
        if total_claims >= 3 and claims_without_citation == total_claims and has_generic:
            warnings.append("⚠️ 所有事实声明均无就近引用，但文本末尾有通用引用标记——引用有效性待核实")
        if total_claims == 0 and cls.has_generic_citation(text):
            warnings.append("ℹ️ 文本有引用标记但未检测到需要引用的事实声明")

        return {
            "total_claims": total_claims,
            "claims_with_citation": claims_with_citation,
            "claims_without_citation": claims_without_citation,
            "citation_precision": round(citation_precision, 3),
            "has_generic_citation": has_generic,
            "has_paragraph_end_refs": has_para_end_citations,
            "paragraph_ref_count": para_ref_count,
            "warnings": warnings,
            "claim_details": claim_details[:20],  # 限制详请数量
        }


class SourceTracer:
    """信息溯源 — 记录每条陈述的来源，支持按文本/ID回溯"""
    
    def __init__(self):
        self.trace_file = SOURCE_TRACE_PATH
    
    def record(self, statement: str, source_url: str = "",
               source_type: str = "unknown",
               confidence: float = 0.5,
               metadata: dict = None) -> str:
        """记录一条溯源信息，返回 trace_id"""
        trace_id = hashlib.md5(f"{statement}{time.time()}{random.random()}".encode()).hexdigest()[:12]
        entry = {
            "trace_id": trace_id,
            "statement_prefix": statement[:120],
            "source_url": source_url,
            "source_type": source_type,
            "confidence": round(confidence, 3),
            "metadata": metadata or {},
            "ts": datetime.now(BEIJING_TZ).isoformat(),
        }
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return trace_id
    
    def trace(self, text_or_id: str, max_results: int = 5) -> List[dict]:
        """按语句或 trace_id 回溯来源"""
        if not os.path.exists(self.trace_file):
            return []
        results = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if text_or_id == entry.get("trace_id") or text_or_id[:60] in entry.get("statement_prefix", ""):
                    results.append(entry)
                    if len(results) >= max_results:
                        break
        return results
    
    def get_recent(self, limit: int = 10) -> List[dict]:
        """获取最近溯源记录"""
        if not os.path.exists(self.trace_file):
            return []
        lines = []
        with open(self.trace_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return lines[-limit:]


class AntiFakeValidator:
    """全链路防幻觉校验引擎 v4.0 — 新增逐句引用精确性分析"""

    def __init__(self):
        self.credit_db = self._load_credit_db()
        self.citation_analyzer = CitationAnalyzer()
        self.source_tracer = SourceTracer()

    def three_rules_check(self, text: str = "", task_type: str = "normal") -> Dict:
        """
        集成调用的铁律行为前置检查（来源: iron_rules.py）。
        每次 full_check() 前自动执行，返回铁律触发状态。
        """
        result = {
            "available": _THREE_RULES_AVAILABLE,
            "should_pre_check": False,
            "triggered_rules": [],
            "behavior_checklist": [],
        }
        if not _THREE_RULES_AVAILABLE:
            return result

        should_check, rules = validate_response_needed(task_type)
        result["should_pre_check"] = should_check
        result["triggered_rules"] = rules

        # 分析用户输入是否触发铁律
        if text:
            triggered, kind = trigger_kind(text)
            if triggered:
                result["triggered_rules"].append(kind)

        return result

    def _load_credit_db(self) -> Dict:
        if os.path.exists(CREDIT_DB_PATH):
            try:
                with open(CREDIT_DB_PATH) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, OSError):
                logging.exception("[anti_fake_validator.py] suppressed")
                pass
        return {
            "sources": {},  # {url: {total_queries, accurate_queries, last_accessed, avg_confidence}}
            "domains": {},  # {domain: {total, accurate}}
            "overall_health": "healthy",
            "version": 5.0,
        }

    def _save_credit_db(self):
        with open(CREDIT_DB_PATH, "w") as f:
            json.dump(self.credit_db, f, indent=2)

    def _update_source_credit(self, url: str, confidence: float):
        """更新来源信用数据库"""
        now = datetime.now(BEIJING_TZ).isoformat()
        if url not in self.credit_db["sources"]:
            self.credit_db["sources"][url] = {
                "total_queries": 0,
                "accurate_queries": 0,
                "last_accessed": now,
                "avg_confidence": 0.0,
            }
        src = self.credit_db["sources"][url]
        src["total_queries"] += 1
        src["last_accessed"] = now
        if confidence >= 0.7:
            src["accurate_queries"] += 1
        src["avg_confidence"] = round(
            (src["avg_confidence"] * (src["total_queries"] - 1) + confidence) / src["total_queries"], 3
        )
        # 更新域名聚合
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
            if domain not in self.credit_db["domains"]:
                self.credit_db["domains"][domain] = {"total": 0, "accurate": 0}
            d = self.credit_db["domains"][domain]
            d["total"] += 1
            if confidence >= 0.7:
                d["accurate"] += 1
        except (KeyError, ValueError, IOError):
            pass
        self._save_credit_db()

    def _log_alert(self, alert: Dict):
        alert["ts"] = datetime.now(BEIJING_TZ).isoformat()
        with open(ALERT_LOG_PATH, "a") as f:
            f.write(json.dumps(alert, ensure_ascii=False) + "\n")

    # ================================================================
    # 1. 检索链 — 来源权威性评分
    # ================================================================
    def evaluate_source_authority(self, url: str) -> int:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        for domain, score in sorted(AUTHORITY_SCORES.items(), key=lambda x: -x[1]):
            # 精确匹配域名或子域名，避免子串误判（如 .gov.cn 在 URL 参数中）
            if domain in netloc:
                return score
        return 10

    # ================================================================
    # 1.5 语句级置信度评分（v5.0 新增）
    # ================================================================
    def _score_statement_confidence(self, text: str, sources: List[str] = None) -> Dict:
        """
        语句级置信度评分。对文本逐句分析，每句给出 0-1 置信度。
        评分维度：精确引用(+0.3) / URL来源(+0.2) / 不确定性(-0.15) / 绝对化(-0.1) / 权威性因子
        """
        sources = sources or []
        sentences = self.citation_analyzer.split_into_sentences(text)
        results = []
        overall = 0.0

        for sent in sentences:
            score = 0.5  # 基础分
            # 精确引用
            if self.citation_analyzer.has_exact_citation(sent):
                score += 0.3
            # URL 引用
            if self.citation_analyzer.has_url_citation(sent):
                score += 0.2
            # 具名来源
            if self.citation_analyzer.has_named_source(sent):
                score += 0.15
            # 不确定性词汇
            for pat in UNCERTAINTY_PATTERNS:
                if re.search(pat, sent, re.IGNORECASE):
                    score -= 0.15
                    break
            # 绝对化表述
            absolutes = ["一定", "绝对", "肯定", "必然", "always", "never", "definitely", "absolutely"]
            for w in absolutes:
                if w in sent.lower():
                    score -= 0.1
                    break
            # 模糊数据
            for pat in VAGUE_NUMBERS:
                if re.search(pat, sent, re.IGNORECASE):
                    score -= 0.1
                    break
            # 有具体数字 → 置信度加成
            if re.search(r'\b\d+[\.\d]*\b', sent):
                score += 0.05
            # 来源权威性加成（取最高分）
            if sources:
                max_auth = max(self.evaluate_source_authority(s) for s in sources) / 100.0
                score += max_auth * 0.1

            score = max(0.0, min(1.0, score))
            results.append({
                "sentence_prefix": sent[:80],
                "confidence": round(score, 3),
            })
            overall += score

        overall = round(overall / len(sentences), 3) if sentences else 1.0
        low_confidence = [r for r in results if r["confidence"] < 0.5]

        return {
            "per_sentence": results,
            "overall": overall,
            "low_confidence_sentences": low_confidence,
            "low_confidence_count": len(low_confidence),
        }

    # ================================================================
    # 2. 虚构造假检测（v4.0 增强：集成引用精确性分析）
    # ================================================================
    def detect_hallucination_indicators(self, text: str) -> Tuple[bool, List[str], float]:
        """检测文本中的幻觉指标，v4.0 新增引用精确性检测"""
        indicators = []
        confidence = 1.0
        
        # 检测不确定性词汇
        for pat in UNCERTAINTY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                indicators.append(f"不确定性关键词: {pat}")
                confidence *= 0.85

        # 检测模糊数据
        for pat in VAGUE_NUMBERS:
            if re.search(pat, text, re.IGNORECASE):
                indicators.append(f"模糊数据表述: {pat}")
                confidence *= 0.80

        # 检测具体数字（有数据说明可验证性较好）
        specific_numbers = re.findall(r'\b\d+[\.\d]*\b', text)
        if len(specific_numbers) >= 2:
            confidence *= 1.15
        
        # 检测绝对化表述
        absolutes = ["一定", "绝对", "肯定", "必然", "always", "never", "definitely", "absolutely"]
        for w in absolutes:
            if w in text.lower():
                indicators.append(f"绝对化表述: {w}")
                confidence *= 0.90

        # v4.0：引用精确性分析（替换旧的 has_citation 浅层检测）
        citation_analysis = self.citation_analyzer.analyze_citation_precision(text)
        has_any_citation = citation_analysis["has_generic_citation"]
        citation_precision = citation_analysis["citation_precision"]
        total_claims = citation_analysis["total_claims"]

        if total_claims > 0:
            if citation_precision < 0.3:
                indicators.append(f"引用精确度极低({citation_precision})：{total_claims}个声明中仅{citation_analysis['claims_with_citation']}个有精确引用")
                confidence *= 0.50  # 大降分
            elif citation_precision < 0.6:
                indicators.append(f"引用精确度偏低({citation_precision})：{total_claims}个声明中{citation_analysis['claims_without_citation']}个缺少精确引用")
                confidence *= 0.70
            elif citation_precision < 1.0:
                confidence *= 0.90  # 大部分有引用，少量缺失
        elif has_any_citation and total_claims == 0:
            # 有引用标记但无声明——可能只是泛泛引用或参考文献列表
            pass  # 这不一定是问题，不扣分

        # 加入引用精确性分析警告
        indicators.extend(citation_analysis["warnings"])

        is_suspicious = confidence < 0.6 or len([i for i in indicators if "⚠️" in i]) >= 1
        return is_suspicious, indicators, min(confidence, 1.0)

    # ================================================================
    # 3. 时效性验证
    # ================================================================
    def check_timeliness(self, text: str, source_date: Optional[str] = None) -> Dict:
        result = {"status": "unknown", "message": "", "decay_days": 0}
        now = datetime.now(BEIJING_TZ)

        years = re.findall(r'(?<!\d)(20[0-9]{2})(?!\d)\s*年?', text)
        if years:
            latest_year = max(int(y) for y in years)
            current_year = now.year
            diff_years = current_year - latest_year
            result["decay_days"] = diff_years * 365
            if diff_years > 5:
                result["status"] = "stale"
                result["message"] = f"数据参考年份{latest_year}，已超过5年，建议核实更新"
            elif diff_years > 2:
                result["status"] = "aged"
                result["message"] = f"数据参考年份{latest_year}，已超过2年，部分信息可能已过时"
            else:
                result["status"] = "fresh"
                result["message"] = f"数据参考年份{latest_year}，时效性良好"

        if source_date:
            try:
                src_dt = datetime.fromisoformat(source_date)
                days_diff = (now - src_dt).days
                result["decay_days"] = max(result["decay_days"], days_diff)
                if days_diff > 365:
                    result["status"] = "stale"
                    result["message"] = f"来源日期距今{days_diff}天，信息可能已过时"
                elif days_diff > 90:
                    result["status"] = "aged"
                    result["message"] = f"来源日期距今{days_diff}天，建议核实"
                else:
                    result["status"] = "fresh"
                    result["message"] = "来源时效性良好"
            except (ValueError, IOError, OSError):
                logging.exception("[anti_fake_validator.py] suppressed")
                pass

        return result

    # ================================================================
    # 4. 交叉验证（多源比对启发式）
    # ================================================================
    def cross_validate(self, claims: List[str], sources: List[str]) -> Dict:
        result = {"conflicts": [], "consensus": True, "score": 1.0}
        if len(sources) < 2:
            result["consensus"] = False
            result["score"] = 0.5
            result["conflicts"].append("单一来源，无法交叉验证")
            return result

        scores = [self.evaluate_source_authority(s) for s in sources]
        avg_score = sum(scores) / len(scores)
        result["score"] = avg_score / 100.0

        min_score, max_score = min(scores), max(scores)
        if max_score - min_score >= 40:
            result["conflicts"].append(f"来源权威性差异大（{min_score}-{max_score}），以高分来源为准")
            result["consensus"] = False

        return result

    # ================================================================
    # 5. 全链路校验（v4.0 新增 citation_analysis 输出）
    # ================================================================
    def _split_by_chunks(self, text: str, max_chunk_chars: int = 3000) -> List[str]:
        """按段落边界语义分块，每块不超过 max_chunk_chars"""
        # 先按双换行（段落边界）切
        paragraphs = text.split("\n\n")
        chunks = []
        current = []
        current_len = 0
        for para in paragraphs:
            para_stripped = para.strip()
            if not para_stripped:
                continue
            para_len = len(para_stripped)
            if current_len + para_len > max_chunk_chars and current:
                chunks.append("\n\n".join(current))
                current = [para_stripped]
                current_len = para_len
            else:
                current.append(para_stripped)
                current_len += para_len
        if current:
            chunks.append("\n\n".join(current))
        # 如果单块仍然超大（罕见情况），按换行降级切割
        final_chunks = []
        for c in chunks:
            if len(c) > max_chunk_chars * 1.5:
                sub = c.split("\n")
                buf = []
                buf_len = 0
                for line in sub:
                    if buf_len + len(line) > max_chunk_chars and buf:
                        final_chunks.append("\n".join(buf))
                        buf = [line]
                        buf_len = len(line)
                    else:
                        buf.append(line)
                        buf_len += len(line)
                if buf:
                    final_chunks.append("\n".join(buf))
            else:
                final_chunks.append(c)
        return final_chunks if final_chunks else [text]

    def full_check(self, text: str, sources: List[str] = None,
                   source_dates: List[str] = None,
                   confidence_threshold: float = 0.6) -> Dict:
        """
        全链路防幻觉校验（v6.0）

        v6.0 改进：超长文本不再硬截断，而是按段落边界语义分块，
        各块独立校验后合并结果，取最严风险分。

        Args:
            text: 要校验的文本
            sources: 信息来源 URL 列表
            source_dates: 来源日期列表
            confidence_threshold: 置信度阈值，低于此值时 needs_confirmation=True

        Returns:
            Dict: 校验结果
        """
        sources = sources or []
        source_dates = source_dates or []

        # 语义分块：超长文本按段落边界分割，各块独立校验后合并
        CHUNK_CHARS = 3000  # ~750 中文 token，留余量
        chunks = self._split_by_chunks(text, CHUNK_CHARS) if len(text) > CHUNK_CHARS else [text]
        is_multichunk = len(chunks) > 1

        # 逐块校验
        def _run_check_on_text(txt):
            r = {
                "risk_score": 1.0,
                "is_suspicious": False,
                "indicators": [],
                "hallucination_confidence": 1.0,
                "total_claims": 0,
                "claims_with_citation": 0,
                "claims_without_citation": 0,
                "citation_precision": 1.0,
                "has_paragraph_end_refs": False,
                "statement_conf": 1.0,
                "needs_confirmation": False,
            }
            # 引用精确性
            ca = self.citation_analyzer.analyze_citation_precision(txt)
            r["total_claims"] = ca["total_claims"]
            r["claims_with_citation"] = ca["claims_with_citation"]
            r["claims_without_citation"] = ca["claims_without_citation"]
            r["citation_precision"] = ca["citation_precision"]
            r["has_paragraph_end_refs"] = ca["has_paragraph_end_refs"]
            # 幻觉检测
            suspicious, indic, conf = self.detect_hallucination_indicators(txt)
            r["is_suspicious"] = suspicious
            r["indicators"] = indic
            r["hallucination_confidence"] = round(conf, 3)
            # 语句级置信度
            sc = self._score_statement_confidence(txt, sources)
            r["statement_conf"] = sc["overall"]
            r["needs_confirmation"] = sc["overall"] < confidence_threshold
            # 综合风险分（不含来源权威性/时效性等全局维度）
            rs = 1.0
            if suspicious:
                rs *= 0.5
            if r["total_claims"] > 0:
                if r["citation_precision"] < 0.3:
                    rs *= 0.6
                elif r["citation_precision"] < 0.6:
                    rs *= 0.8
                elif r["citation_precision"] < 1.0:
                    rs *= 0.95
            if r["has_paragraph_end_refs"] and r["citation_precision"] < 0.4:
                rs *= 0.85
            if sc["overall"] < 0.5:
                rs *= 0.6
            elif sc["overall"] < 0.7:
                rs *= 0.8
            r["risk_score"] = round(rs, 3)
            return r, ca, sc, suspicious, indic, conf

        # 运行校验
        chunk_results = []
        merged_claims = {"total": 0, "with_citation": 0, "without_citation": 0}
        merged_warnings = set()
        merged_indicators = set()
        lowest_risk = 1.0
        lowest_statement_conf = 1.0
        has_suspicious = False
        needs_confirm = False

        for c in chunks:
            cr, ca, sc, susp, indic, conf = _run_check_on_text(c)
            chunk_results.append(cr)
            merged_claims["total"] += cr["total_claims"]
            merged_claims["with_citation"] += cr["claims_with_citation"]
            merged_claims["without_citation"] += cr["claims_without_citation"]
            # 安全合并 indicators（防止含 dict 等不可哈希元素）
            for ind in cr["indicators"]:
                if isinstance(ind, (str, int, float, bool)):
                    merged_indicators.add(ind)
                else:
                    merged_indicators.add(str(ind))
            lowest_risk = min(lowest_risk, cr["risk_score"])
            lowest_statement_conf = min(lowest_statement_conf, cr["statement_conf"])
            if cr["is_suspicious"]:
                has_suspicious = True
            if cr["needs_confirmation"]:
                needs_confirm = True
            if ca["warnings"]:
                # 安全合并 warnings
                for w in ca["warnings"]:
                    if isinstance(w, str):
                        merged_warnings.add(w)
                    else:
                        merged_warnings.add(str(w))

        # 来源权威性（全局只算一次）
        source_authority = {"scores": {}, "avg_score": 0}
        for url in sources:
            score = self.evaluate_source_authority(url)
            source_authority["scores"][url] = score
        if sources:
            source_authority["avg_score"] = sum(source_authority["scores"].values()) / len(sources)

        # 全局维度：时效性 + 交叉验证
        timeliness = self.check_timeliness(text, source_dates[0] if source_dates else None)
        cv_result = self.cross_validate([], sources)

        # === 合并最终结果 ===
        # 最终风险分 = 块内最严风险分 × 全局维度衰减
        final_risk = lowest_risk
        if source_authority.get("avg_score", 100) < 40:
            final_risk *= 0.7
        if timeliness.get("status") == "stale":
            final_risk *= 0.6
        elif timeliness.get("status") == "aged":
            final_risk *= 0.8
        if not cv_result["consensus"]:
            final_risk *= 0.8

        # 合并引用精确性（按总量加权）
        merged_cp = round(
            merged_claims["with_citation"] / merged_claims["total"]
            if merged_claims["total"] > 0 else 1.0, 3
        )
        merged_citation_analysis = {
            "total_claims": merged_claims["total"],
            "claims_with_citation": merged_claims["with_citation"],
            "claims_without_citation": merged_claims["without_citation"],
            "citation_precision": merged_cp,
            "has_paragraph_end_refs": any(cr["has_paragraph_end_refs"] for cr in chunk_results),
            "paragraph_ref_count": sum(cr.get("paragraph_ref_count", 0) for cr in chunk_results),
            "warnings": list(merged_warnings),
        }

        # 构建 result 字典
        result = {
            "overall_risk": "low",
            "risk_score": round(final_risk, 3),
            "source_authority": source_authority,
            "hallucination": {
                "is_suspicious": has_suspicious,
                "indicators": list(merged_indicators),
                "confidence": round(lowest_statement_conf, 3),
                "claims_analyzed": merged_claims["total"],
                "unreferenced_claims": merged_claims["without_citation"],
            },
            "timeliness": timeliness,
            "cross_validation": cv_result,
            "citation_analysis": merged_citation_analysis,
            "confidence": {"overall": round(lowest_statement_conf, 3)},
            "needs_confirmation": needs_confirm,
            "source_trace_ids": [],
            "warnings": [w for w in merged_warnings],
            "recommendations": [],
        }

        # 最终风险等级
        if result["risk_score"] >= 0.8:
            result["overall_risk"] = "low"
        elif result["risk_score"] >= 0.5:
            result["overall_risk"] = "medium"
        else:
            result["overall_risk"] = "high"

        # 多块提示
        if is_multichunk:
            result["recommendations"].append(f"文本长度超过3K字符，已按段落边界分为{len(chunks)}个语义块独立校验后合并")

        # 建议
        if result["overall_risk"] == "high":
            result["recommendations"].append("⚠️ 高风险：建议不要直接使用该信息，需找到权威来源核实")
        elif result["overall_risk"] == "medium":
            result["recommendations"].append("⚠️ 中风险：建议补充权威来源后再使用")
        if not sources:
            result["recommendations"].append("建议标注信息来源")
        if has_suspicious and merged_indicators:
            result["recommendations"].append(f"检测到可能的问题：{'、'.join(list(merged_indicators)[:3])}")
        if needs_confirm:
            result["recommendations"].append(
                f"⬇️ 整体置信度({lowest_statement_conf})低于阈值({confidence_threshold})，"
                "建议输出时附带置信度说明或主动核实"
            )
        if merged_claims["total"] > 0 and merged_cp < 0.6:
            result["recommendations"].append(
                f"建议对{merged_claims['total']}个事实声明中的{merged_claims['without_citation']}个未精确引用声明补充具体来源"
            )

        # 溯源记录（取前2块即可）
        trace_ids = []
        if sources:
            preview_text = chunks[0][:200] if is_multichunk else text[:200]
            for url in sources[:5]:
                trace_id = self.source_tracer.record(
                    statement=preview_text,
                    source_url=url,
                    source_type="web",
                    confidence=result["confidence"]["overall"],
                    metadata={
                        "overall_risk": result["overall_risk"],
                        "risk_score": result["risk_score"],
                        "citation_precision": merged_cp,
                    }
                )
                trace_ids.append(trace_id)
            for url in sources:
                self._update_source_credit(url, result["confidence"]["overall"])
        result["source_trace_ids"] = trace_ids

        # 无障碍可读性评分 — 全输出内容的多维度可读性分析
        # 在 full_check 中作为附加维度输出，不参与风险分计算（风险分只反映幻觉风险）
        try:
            # 延迟导入避免循环依赖
            from core.engines.hooks.accessibility_filter import score_quality
            readability = score_quality(text)
            result["readability"] = readability
            if readability.get("total", 0) < 3:
                result["recommendations"].append(
                    f"♿ 无障碍可读性偏低({round(readability.get('total', 0), 2)}/10)，"
                    "建议使用无障碍模式输出（去表格/简化符号/中文优先）"
                )
        except Exception:
            pass

        # 记录高/中风险
        if result["overall_risk"] in ("high", "medium"):
            self._log_alert({
                "type": f"risk_{result['overall_risk']}",
                "risk_score": result["risk_score"],
                "citation_precision": merged_cp,
                "unreferenced_claims": merged_claims["without_citation"],
                "confidence": result["confidence"]["overall"],
                "text_preview": chunks[0][:200] if is_multichunk else text[:200],
            })

        return result


# ═══════════════════════════════════════════════════════════════
# Preflight + PostCheck — 记忆融合 + 铁律前置 + 事后双重校验
# ═══════════════════════════════════════════════════════════════

# 惰性导入 preflight_checker（避免循环依赖）
_preflight_checker = None
_auto_memory = None
_crusheart_config = None


def _get_config() -> dict:
    """读取 .crusheart-config.json 配置（记忆融合配置）"""
    global _crusheart_config
    if _crusheart_config is not None:
        return _crusheart_config
    cfg_path = os.path.join(WORKSPACE, '.crusheart-config.json')
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding='utf-8') as f:
                _crusheart_config = json.load(f)
        else:
            _crusheart_config = {"antiFake": {"enabled": True, "blockOnHigh": True,
                                               "flagOnMid": True, "logOnly": False}}
    except Exception:
        _crusheart_config = {"antiFake": {"enabled": True, "blockOnHigh": True,
                                           "flagOnMid": True, "logOnly": False}}
    return _crusheart_config


def _get_auto_memory():
    """惰性导入 AutoMemory 实例"""
    global _auto_memory
    if _auto_memory is None:
        try:
            from core.engines.memory.auto_memory import get_memory
            _auto_memory = get_memory()
        except ImportError:
            pass
    return _auto_memory


def _get_preflight_checker():
    global _preflight_checker
    if _preflight_checker is None:
        try:
            from core.engines.quality import preflight_checker
            _preflight_checker = preflight_checker
        except ImportError:
            pass
    return _preflight_checker


# 将 preflight 方法加到 AntiFakeValidator 类上
def _patch_anti_fake_validator():
    """
    在 AntiFakeValidator 上附加 preflight 和 post_check 方法。
    因类定义已结束，用 patch 方式扩展。
    """

    def preflight(self, response: str, context: dict = None) -> dict:
        """
        铁律前置检查（新增）
        
        检查AI回复是否违反铁律。
        和原有的 three_rules_check() 不同：
          - three_rules_check → 检查用户输入是否触发铁律
          - preflight → 检查AI回复是否违反铁律
        
        Returns:
            {passed: bool, violations: [{rule_id, check_id, severity, reason, suggestion}],
             pass_rate: float, has_blockers: bool}
        """
        pfc = _get_preflight_checker()
        if pfc is None:
            return {"passed": True, "errors": ["preflight_checker 不可用"], "violations": []}
        
        ctx = context or {}
        checker = pfc.get_checker()
        result = checker.check(response, ctx)
        d = result.to_dict()
        d["pass_rate"] = round(1.0 - d["total_violations"] / max(len(checker.rules) * 4, 1), 3)
        d["has_blockers"] = result.has_blockers()
        return d

    def _check_memory_input(query: str) -> dict:
        """
        Layer 2: 记忆检索前置校验
        
        在 auto_memory.search() 前调用，检查检索请求是否含注入/劫持攻击。
        防止恶意内容通过记忆系统污染后续回复。
        
        Returns:
            {passed: bool, blocked: bool, reason: str|null,
             risk_level: low|mid|high}
        """
        if not query or not query.strip():
            return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}
        
        cfg = _get_config()
        if not cfg.get("antiFake", {}).get("enabled", True):
            return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}
        
        log_only = cfg.get("antiFake", {}).get("logOnly", False)
        
        # 注入攻击模式检测
        injection_patterns = [
            "ignore previous", "ignore all", "you are now",
            "disregard your", "forget your", "new instructions",
            "system prompt", "<system>", "override",
            "]]>", "]]:}}]", "{{[",
        ]
        q_lower = query.lower()
        for pat in injection_patterns:
            if pat in q_lower:
                alert = {
                    "type": "memory_injection_detected",
                    "ts": datetime.now(BEIJING_TZ).isoformat(),
                    "pattern": pat,
                    "query_preview": query[:100],
                }
                try:
                    validator = _get_checker_instance()
                    if validator:
                        validator._log_alert(alert)
                except Exception:
                    pass
                if log_only:
                    return {"passed": True, "blocked": False,
                            "reason": f"注入模式 '{pat}' 命中，仅记录模式",
                            "risk_level": "high"}
                return {"passed": False, "blocked": True,
                        "reason": f"注入模式 '{pat}' 被拦截",
                        "risk_level": "high"}
        
        # 格式污染检测
        format_abuse = [
            lambda q: q.count("[") > 20 or q.count("]") > 20,
            lambda q: q.count("{") > 20 or q.count("}") > 20,
            lambda q: len(q) > 2000,
        ]
        for check_fn in format_abuse:
            if check_fn(q_lower):
                alert = {
                    "type": "memory_format_abuse",
                    "ts": datetime.now(BEIJING_TZ).isoformat(),
                    "query_len": len(q_lower),
                    "query_preview": query[:100],
                }
                try:
                    validator = _get_checker_instance()
                    if validator:
                        validator._log_alert(alert)
                except Exception:
                    pass
                if log_only:
                    return {"passed": True, "blocked": False,
                            "reason": "格式污染命中，仅记录模式",
                            "risk_level": "mid"}
                return {"passed": False, "blocked": True,
                        "reason": "格式污染被拦截",
                        "risk_level": "mid"}
        
        return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}

    def _verify_response(response: str, context: dict = None) -> dict:
        """
        Layer 3: 回复后记忆校验
        
        验证 AI 回复中的事实性声明是否与记忆库中的已知事实一致。
        在 message:sent 阶段由 post_check 触发。
        
        Returns:
            {passed: bool, conflicts: [{fact, memory, similarity}],
             violations: list, risk_level: low|mid|high}
        """
        cfg = _get_config()
        if not cfg.get("antiFake", {}).get("enabled", True):
            return {"passed": True, "conflicts": [], "risk_level": "low"}
        
        if not response or len(response) < 30:
            return {"passed": True, "conflicts": [], "risk_level": "low"}
        
        # 提取回复中的事实性声明（数字、引号、专有名词）
        claims = []
        for sent in re.split(r'[。！？\n]', response):
            sent = sent.strip()
            if not sent or len(sent) < 10:
                continue
            # 判断是否含事实性内容
            has_number = bool(re.search(r'\d+[.\d]*', sent))
            has_quote = bool(re.search(r'["\x27\u201c\u201d]', sent))
            has_named = any(re.search(p, sent, re.I) for p in [
                r'\b(天津|北京|上海|广州|深圳|杭州|南京|成都|武汉|重庆|西安)\b',
                r'\b(中国|美国|日本|英国|法国|德国|俄罗斯|印度|韩国)\b',
                r'\b(华为|腾讯|阿里|百度|字节|小米|比亚迪|京东)\b',
            ])
            if has_number or has_quote or has_named:
                claims.append(sent)
        
        if not claims:
            return {"passed": True, "conflicts": [], "risk_level": "low"}
        
        # 尝试从记忆库检索冲突
        conflicts = []
        memory = _get_auto_memory()
        if memory:
            for claim in claims[:5]:  # 最多检查4个声明
                try:
                    mem_results = memory.search(claim, is_high_risk=False, budget_tokens=500)
                    for mr in (mem_results or [])[:3]:
                        mem_text = mr.get("content") or mr.get("text") or ""
                        mem_score = mr.get("score", 0)
                        if mem_score >= 0.85 and claim.lower() not in mem_text.lower():
                            # 高相似但内容不同 → 可能冲突
                            conflicts.append({
                                "claim": claim[:100],
                                "memory": mem_text[:200],
                                "similarity": mem_score,
                            })
                except Exception:
                    pass
        
        risk_level = "high" if len(conflicts) >= 2 else ("mid" if conflicts else "low")
        passed = risk_level == "low"
        
        if conflicts:
            alert_entry = {
                "type": "memory_response_conflict",
                "ts": datetime.now(BEIJING_TZ).isoformat(),
                "response_preview": response[:200],
                "conflict_count": len(conflicts),
            }
            try:
                validator = _get_checker_instance()
                if validator:
                    validator._log_alert(alert_entry)
            except Exception:
                pass
        
        return {
            "passed": passed,
            "conflicts": conflicts,
            "violations": [{"source": "memory_verify", "risk": risk_level,
                            "count": len(conflicts)}] if conflicts else [],
            "risk_level": risk_level,
        }

    def _get_checker_instance():
        """获取全局校验器实例（内部辅助）"""
        try:
            from core.engines.quality.anti_fake_validator import get_validator
            return get_validator()
        except Exception:
            return None

    def _check_memory_save(content: str, metadata: dict = None) -> dict:
        """
        Layer 2.5: 记忆存储前置校验

        在 AutoMemory.save() 写入前调用，检查要存入记忆的内容是否安全。
        防止幻觉/注入内容污染记忆库。

        Returns:
            {passed: bool, blocked: bool, reason: str|null,
             risk_level: low|mid|high}
        """
        if not content or not content.strip():
            return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}

        cfg = _get_config()
        if not cfg.get("antiFake", {}).get("enabled", True):
            return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}

        log_only = cfg.get("antiFake", {}).get("logOnly", False)

        # 1. 注入/劫持模式检测
        hijack_patterns = [
            "ignore previous", "ignore all", "you are now",
            "override", "replace all", "forget everything",
            "system prompt", "你现在的角色是", "忽略之前",
            "请记住以下内容",
        ]
        for pat in hijack_patterns:
            if pat.lower() in content.lower():
                msg = f"记忆存储被拦截: 检测到劫持模式 '{pat}'"
                if log_only:
                    logger.warning(f"[LOG_ONLY] {msg}")
                    return {"passed": True, "blocked": False, "risk_level": "mid",
                            "reason": msg}
                return {"passed": False, "blocked": True, "risk_level": "high",
                        "reason": msg}

        # 2. 疑似幻觉内容检测（含大量不确定词但声称是事实）
        uncertainty_count = sum(1 for p in UNCERTAINTY_PATTERNS if re.search(p, content))
        if uncertainty_count >= 3:
            msg = f"记忆存储警告: 含 {uncertainty_count} 个不确定性词，可能不是可靠事实"
            if log_only:
                logger.warning(f"[LOG_ONLY] {msg}")
                return {"passed": True, "blocked": False, "risk_level": "mid",
                        "reason": msg}
            return {"passed": False, "blocked": True, "risk_level": "mid",
                    "reason": msg}

        # 3. 内容长度检查（极短或无意义内容不存）
        if len(content.strip()) < 1:
            return {"passed": False, "blocked": True, "risk_level": "low",
                    "reason": "内容过短，拒绝存储"}

        # 4. 用户明确要求存储（user_explicit=True）→ 放宽校验
        if metadata and metadata.get("user_explicit", False):
            if uncertainty_count <= 5:
                return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}

        return {"passed": True, "blocked": False, "risk_level": "low", "reason": None}

    def post_check(self, response: str, context: dict = None) -> dict:
        """
        事后三重校验（新增）- 融合记忆层校验
        
        结合 full_check（内容真实性）+ preflight（铁律遵守）+ _verify_response（记忆校验）：
          1. full_check: 检查内容是否含幻觉风险
          2. preflight: 检查铁律遵守情况
          3. _verify_response: 检查回复是否与记忆库冲突
          4. 记录到错误数据库供 self_evolution 参考
        
        Returns:
            {passed: bool, truth_check: dict, iron_check: dict,
             memory_check: dict, violations: list, trace_ids: list}
        """
        ctx = context or {}
        
        # 1. 内容真实性检查 (full_check)
        sources = ctx.get("sources", [])
        source_dates = ctx.get("source_dates", [])
        truth_result = self.full_check(response, sources, source_dates)
        
        # 2. 铁律遵守检查 (preflight)
        iron_result = self.preflight(response, ctx)
        
        # 3. 记忆校验 (Layer 3)
        memory_result = self._verify_response(response, ctx)
        
        # 4. 汇总
        violations = []
        if truth_result.get("overall_risk") in ("high", "medium"):
            violations.append({
                "source": "full_check",
                "risk": truth_result["overall_risk"],
                "risk_score": truth_result["risk_score"],
                "reasons": truth_result.get("recommendations", []),
            })
        if not iron_result.get("passed", True):
            for v in iron_result.get("violations", []):
                violations.append({
                    "source": "preflight",
                    "rule_id": v.get("rule_id", "?"),
                    "severity": v.get("severity", "warn"),
                    "reason": v.get("reason", ""),
                })
        for v in memory_result.get("violations", []):
            violations.append(v)
        
        passed = (truth_result.get("overall_risk") != "high" and
                  iron_result.get("passed", True) and
                  memory_result.get("risk_level") != "high")
        
        # 5. 记录到告警日志
        if not passed:
            alert_entry = {
                "type": "post_check_failed",
                "ts": datetime.now(BEIJING_TZ).isoformat(),
                "response_preview": response[:200],
                "truth_risk": truth_result.get("overall_risk"),
                "iron_passed": iron_result.get("passed", True),
                "memory_risk": memory_result.get("risk_level"),
                "violation_count": len(violations),
            }
            try:
                self._log_alert(alert_entry)
            except Exception:
                pass
        
        return {
            "passed": passed,
            "truth_check": {
                "overall_risk": truth_result.get("overall_risk"),
                "risk_score": truth_result.get("risk_score"),
                "citation_precision": truth_result.get("citation_analysis", {}).get("citation_precision"),
            },
            "iron_check": {
                "passed": iron_result.get("passed", True),
                "violations": iron_result.get("violations", []),
                "has_blockers": iron_result.get("has_blockers", False),
            },
            "memory_check": {
                "passed": memory_result.get("passed", True),
                "conflicts": memory_result.get("conflicts", []),
                "risk_level": memory_result.get("risk_level", "low"),
            },
            "violations": violations,
            "trace_ids": truth_result.get("source_trace_ids", []),
        }

    # 挂载到类
    AntiFakeValidator.preflight = preflight
    AntiFakeValidator.post_check = post_check
    AntiFakeValidator._check_memory_input = staticmethod(_check_memory_input)
    AntiFakeValidator._check_memory_save = staticmethod(_check_memory_save)
    AntiFakeValidator._verify_response = staticmethod(_verify_response)


# 立即执行 patch
_patch_anti_fake_validator()


# ═══════════════════════════════════════════════════════════════
# 统一入口函数 — 供 daemon bridge / runPy / index.js 调用
# ═══════════════════════════════════════════════════════════════

def get_validator() -> AntiFakeValidator:
    from core.engines.init.engine_factory import SingletonRegistry
    return SingletonRegistry.get(AntiFakeValidator)

def run(text: str, sources = None) -> dict:
    """统一入口：校验文本是否存在幻觉风险"""
    validator = get_validator()
    return validator.full_check(text, sources or [])


def preflight_check(response: str, context: dict = None) -> dict:
    """统一入口：铁律前置检查"""
    validator = get_validator()
    return validator.preflight(response, context)


def post_check(response: str, context: dict = None) -> dict:
    """统一入口：事后双重校验"""
    validator = get_validator()
    return validator.post_check(response, context)


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
    args = sys.argv[1:]
    
    if "--preflight" in args:
        idx = args.index("--preflight")
        if idx + 1 < len(args):
            response = args[idx + 1]
            ctx = {}
            # 解析上下文参数（可选）
            if "--ctx" in args:
                cidx = args.index("--ctx")
                if cidx + 1 < len(args):
                    try:
                        ctx = json.loads(args[cidx + 1])
                    except json.JSONDecodeError:
                        pass
            result = preflight_check(response, ctx)
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(json.dumps({"error": "缺少回复文本参数"}))
    elif "--post-check" in args:
        idx = args.index("--post-check")
        if idx + 1 < len(args):
            response = args[idx + 1]
            ctx = {}
            if "--ctx" in args:
                cidx = args.index("--ctx")
                if cidx + 1 < len(args):
                    try:
                        ctx = json.loads(args[cidx + 1])
                    except json.JSONDecodeError:
                        pass
            result = post_check(response, ctx)
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(json.dumps({"error": "缺少回复文本参数"}))
    elif len(args) >= 1 and not args[0].startswith("--"):
        text = args[0]
        sources = args[1].split(",") if len(args) >= 2 and args[1] else []
        result = run(text, sources)
        print(json.dumps(result, ensure_ascii=False))
        if result.get("overall_risk") == "high":
            print("[BLOCKED] 高风险内容")
    else:
        print("用法:")
        print("  默认检查: python3 anti_fake_validator.py <text> [sources]")
        print("  铁律前置: python3 anti_fake_validator.py --preflight <response> [--ctx JSON]")
        print("  事后校验: python3 anti_fake_validator.py --post-check <response> [--ctx JSON]")

from core.engines.memory.exec_logger import log_execution