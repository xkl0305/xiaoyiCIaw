"""
judge_engine.py — LLM-as-Judge 自评分 & 重放缓冲区 & Reflexion反思系统 & 纠正信号学习

功能：
  1. 回答完成后，用 Flash 模型做三维评分（忠实度/相关性/完整性）
  2. 高分回答自动存入 verified_memories.jsonl
  3. 低分回答自动触发 Reflexion 反思，存失败模式/根因/修复策略三元组
  4. 同类查询时注入 top-3 已验证记忆 + top-2 反思经验
  5. [v2.0] ReplayBuffer — 捕获用户纠正信号，蒸馏为可复用经验
  6. [v2.0] 纠正信号自动检测 + 技能失配检测 + 模式分类失配检测

架构定位：
  归入 engines/quality 引擎组，与 quality_dashboard.py 同级。
  JudgeEngine 负责 LLM-as-Judge 自评分，
  ReplayBuffer 负责用户纠正信号的学习闭环，
  两者共用 verified_memories 和 reflexions 存储体系。

用法：（CLI 已移至 cli.py）
  python3 -m core.engines.quality.cli score --query "xxx" --response "xxx"
  python3 -m core.engines.quality.cli replay --query "xxx"
"""

# ================================================================
# ReplayBuffer — 用户纠正信号重放缓冲区
# 捕获用户显式纠正、技能失配、模式误判等信号，
# 蒸馏为可复用经验，反哺系统判断能力
# ================================================================

import json
import os
import re
import time
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
VERIFIED_PATH = os.path.join(WORKSPACE, ".verified_memories.jsonl")
REFLEXION_PATH = os.path.join(WORKSPACE, ".reflexions.jsonl")

# 正则关键词提取（基于汉字窗口滑动，轻量级）
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "什么", "怎么", "为什么", "如何", "哪个", "这个", "那个", "因为", "所以",
    "但是", "如果", "可以", "应该", "可能", "已经", "正在", "还是", "或者",
    "吗", "呢", "吧", "啊", "呀", "啦", "嗯", "哦", "哈", "嘿"
}


def _extract_keywords(text: str, max_kw: int = 5) -> List[str]:
    """从文本中提取关键词（基于词频+排除停用词）"""
    # 中文关键词提取：按汉字窗口2-4字 + 英文单词
    words = re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]+\+?[a-zA-Z0-9]*', text)
    # 过滤停用词
    filtered = [w.lower() for w in words if w.lower() not in _STOP_WORDS and len(w.strip()) > 0]
    # 按长度排序（长词通常更有区分度），取 top
    # 简单策略：先按出现次数，再按长度
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: (-x[1], -len(x[0])))
    return [w for w, _ in sorted_words[:max_kw]]


class JudgeEngine:
    """LLM-as-Judge 自评分引擎"""

    def __init__(self):
        self.verified_path = VERIFIED_PATH

    # ── 1. 评分 ─────────────────────────────────────

    def score(self, query: str, response: str, context: str = "") -> Dict:
        """
        对回答做三维评分

        返回:
            {
                "faithfulness": 0-10,   # 忠实度：是否编造
                "relevance": 0-10,       # 相关性：是否针对问题
                "completeness": 0-10,    # 完整性：是否漏关键点
                "passed": bool,          # 三项均≥7？
                "raw": str               # LLM 原始输出
            }
        """
        # 调 Flash 模型评分
        # 构造评分 prompt
        prompt = f"""请对以下回答进行三维评分（每项 1-10 分），只返回 JSON，不要多余内容：

用户问题：{query[:300]}

回答：{response[:800]}

评分维度：
1. faithfulness（忠实度）：回答是否基于事实？有没有编造或幻觉？
2. relevance（相关性）：回答是否直接针对用户问题？
3. completeness（完整性）：是否覆盖了问题的核心？有没有明显遗漏？

返回格式（严格 JSON）：
{{"faithfulness": 8, "relevance": 9, "completeness": 7}}

只需要 JSON，不要其他文字。"""

        raw = self._call_judge_llm(prompt)
        scores = self._parse_scores(raw)

        scores["passed"] = (
            scores.get("faithfulness", 0) >= 7
            and scores.get("relevance", 0) >= 7
            and scores.get("completeness", 0) >= 7
        )
        scores["raw"] = raw
        return scores

    def _call_judge_llm(self, prompt: str) -> str:
        """调用评分 LLM — 直接请求，不走 subprocess"""
        import json, urllib.request, os
        try:
            payload = json.dumps({
                "model": os.environ.get("JUDGE_MODEL", "<用户自行配置模型>"),
                "messages": [
                    {"role": "system", "content": "你是一个严格的评分助手，只输出 JSON。"},
                    {"role": "user", "content": prompt[:1500]}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }).encode()
            req = urllib.request.Request(
                os.environ.get('OPENCLAW_GATEWAY_URL', 'http://localhost:18789') + '/v1/chat/completions',
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + os.environ.get('OPENCLAW_API_KEY', '')
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                content = data['choices'][0]['message']['content']
                return content.strip()
        except Exception as e:
            logger.error(f"[JudgeEngine] LLM 调用失败: {e}")
            # 兜底（网络故障时标记为不可用，不放过任何回答）
            return json.dumps({"faithfulness": 0, "relevance": 0, "completeness": 0})

    def _parse_scores(self, raw: str) -> Dict:
        """从 LLM 输出中解析分数"""
        # 尝试直接解析 JSON
        try:
            # 找 JSON 块
            json_match = re.search(r'\{[^}]*"faithfulness"[^}]*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "faithfulness": max(1, min(10, int(data.get("faithfulness", 5)))),
                    "relevance": max(1, min(10, int(data.get("relevance", 5)))),
                    "completeness": max(1, min(10, int(data.get("completeness", 5)))),
                }
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        # 兜底（LLM 输出无法解析时，标记为最低分）
        return {"faithfulness": 0, "relevance": 0, "completeness": 0}

    # ── 2. 存储已验证记忆 ──────────────────────────

    def store_verified(self, query: str, response: str, scores: Dict, keywords: Optional[List[str]] = None):
        """高分回答存入 verified_memories.jsonl，低分触发反思"""
        if not scores.get("passed"):
            # 低分 → 触发 Reflexion
            self.reflect(query, response, scores)
            return

        record = {
            "query": query[:500],
            "response": response[:2000],
            "faithfulness": scores.get("faithfulness", 0),
            "relevance": scores.get("relevance", 0),
            "completeness": scores.get("completeness", 0),
            "keywords": keywords or _extract_keywords(query + " " + response),
            "ts": time.time(),
        }

        os.makedirs(os.path.dirname(self.verified_path), exist_ok=True)
        with open(self.verified_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 控制文件大小（保留最近 500 条）
        self._trim_file(500)

    def _trim_file(self, max_lines: int = 500):
        """保留最近 N 条"""
        if not os.path.exists(self.verified_path):
            return
        with open(self.verified_path) as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(self.verified_path, "w") as f:
                f.writelines(lines[-max_lines:])

    # ── 3. 重放缓冲区 ─────────────────────────────

    def replay(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        按关键词匹配，取 top-N 已验证记忆

        返回:
            [{"query": "...", "response": "...", "scores": {...}, ...]
        """
        if not os.path.exists(self.verified_path):
            return []

        query_kw = set(_extract_keywords(query, max_kw=8))

        records = []
        with open(self.verified_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 计算关键词重叠度
                rec_kw = set(r.get("keywords", []))
                overlap = len(query_kw & rec_kw)
                if overlap > 0:
                    r["_score"] = overlap + (r.get("faithfulness", 0) / 20)
                    records.append(r)

        # 按匹配度降序
        records.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return records[:top_k]

    def format_replay_context(self, query: str) -> str:
        """生成可直接注入上下文的字符串"""
        records = self.replay(query)
        if not records:
            return ""

        parts = ["📌 已验证参考："]
        for i, r in enumerate(records, 1):
            kw = ", ".join(r.get("keywords", [])[:3])
            parts.append(f"  [{i}] ({kw}) {r['response'][:200]}")
        return "\n".join(parts)

    # ── 4. 置信度分级 ──────────────────────────────

    def confidence_level(self, scores: Dict) -> str:
        """
        根据三维评分确定置信度等级。
        
        - 高：三项均 ≥ 8，且 passed=True → 可确信输出
        - 中：平均分 ≥ 5 → 有来源但建议核实
        - 低：平均分 < 5 或无数据 → 模型推理，无可靠来源
        
        Returns: "高" | "中" | "低"
        """
        f = scores.get("faithfulness", 0)
        r = scores.get("relevance", 0)
        c = scores.get("completeness", 0)
        avg = (f + r + c) / 3

        if avg >= 8 and scores.get("passed", False):
            return "高"
        elif avg >= 5:
            return "中"
        else:
            return "低"

    def format_confidence_tag(self, scores: Dict, sources: List[str] = None) -> str:
        """
        生成置信度标签，可追加到回复末尾。
        
        Args:
            scores: score() 返回的评分字典
            sources: 数据源列表，如 ["knowledge_graph", "web_result"]
        
        Returns:
            标签字符串，如 "[置信度: 高]" 或 "[置信度: 低] ⚠️ 来源待确认"
        """
        level = self.confidence_level(scores)
        if level == "高":
            return "✅ [置信度: 高 — 来源可靠]"
        elif level == "中":
            src_info = ""
            if sources:
                src_info = f" 参考源: {', '.join(sources[:3])}"
            return f"⚡ [置信度: 中 — 建议交叉核实]{src_info}"
        else:
            return "⚠️ [置信度: 低 — 模型推理，未经验证，请以实际为准]"

    # ── 5. 可追溯性 ─────────────────────────────────

    RESPONSE_TRACES_PATH = os.path.join(WORKSPACE, ".response_traces.jsonl")

    def add_trace(self, query: str, response: str, scores: Dict,
                  sources: List[Dict] = None, metadata: dict = None):
        """
        记录一条响应溯源信息。
        
        Args:
            query: 用户问题
            response: 系统回答
            scores: score() 返回的评分字典
            sources: [{"source": "知识图谱", "snippet": "...", "url": "..."}, ...]
            metadata: 附加元数据（如引擎版本、检索参数等）
        """
        trace = {
            "ts": time.time(),
            "query": query[:500],
            "response": response[:2000],
            "confidence": self.confidence_level(scores),
            "scores": {
                "faithfulness": scores.get("faithfulness"),
                "relevance": scores.get("relevance"),
                "completeness": scores.get("completeness"),
            },
            "sources": sources or [],
            "metadata": metadata or {},
            "trace_id": hashlib.md5(f"{time.time()}{query}{response[:100]}".encode()).hexdigest()[:12],
        }

        os.makedirs(os.path.dirname(self.RESPONSE_TRACES_PATH), exist_ok=True)
        with open(self.RESPONSE_TRACES_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

        return trace["trace_id"]

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """根据 trace_id 查询溯源记录"""
        if not os.path.exists(self.RESPONSE_TRACES_PATH):
            return None
        with open(self.RESPONSE_TRACES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                    if trace.get("trace_id") == trace_id:
                        return trace
                except json.JSONDecodeError:
                    continue
        return None

    # ── 6. Reflexion 反思系统 ─────────────────────

    def reflect(self, query: str, response: str, scores: Dict, scores_raw: str = "") -> Dict:
        """
        低分回答 → 分析失败原因 → 存反思三元组

        当 Judge 评分不通过（任意一项 ≤6）时触发。
        分析失败模式（幻觉/遗漏/矛盾/冗余/偏离），
        存反思三元组 (失败模式, 根因, 修复策略) 到 .reflexions.jsonl

        返回:
            {"reflected": bool, "patterns": [...], "reflexion_id": "..."}
        """
        passed = scores.get("passed", False)
        if passed:
            return {"reflected": False, "patterns": [], "reflexion_id": ""}

        # 低分 → 用 LLM 分析失败模式
        if scores_raw:
            patterns = self._analyze_failure(query, response, scores, scores_raw)
        else:
            patterns = self._guess_failure_patterns(scores)

        reflexion = {
            "query": query[:300],
            "response_preview": response[:300],
            "scores": scores,
            "patterns": patterns,
            "ts": time.time(),
        }

        os.makedirs(os.path.dirname(REFLEXION_PATH), exist_ok=True)
        with open(REFLEXION_PATH, "a") as f:
            f.write(json.dumps(reflexion, ensure_ascii=False) + "\n")

        self._trim_reflexions(200)

        # 更新 scores 追加反思信息
        scores["reflected"] = True
        scores["reflexion_patterns"] = patterns
        return {"reflected": True, "patterns": patterns, "reflexion_id": f"ref_{int(time.time())}"}

    def _analyze_failure(self, query: str, response: str, scores: Dict, raw: str) -> List[str]:
        """用 LLM 分析失败模式"""
        # 尝试从原始输出中解析
        try:
            data = json.loads(raw)
            if "patterns" in data:
                return data["patterns"][:3]
        except (json.JSONDecodeError, TypeError):
            pass

        prompt = (
            f"用户问题: {query[:200]}\n"
            f"回答: {response[:400]}\n"
            f"评分: 忠实度{scores.get('faithfulness',0)} 相关性{scores.get('relevance',0)} "
            f"完整性{scores.get('completeness',0)}\n\n"
            "分析失败原因，从以下模式中选择（可多选，用逗号分隔）：\n"
            "hallucination(编造/幻觉), omission(遗漏), contradiction(矛盾), "
            "redundancy(冗余), off_topic(偏离)\n"
            "返回格式: {\"patterns\": [\"hallucination\"]}\n"
            "只需要JSON。"
        )

        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "-c", f"""
import json, urllib.request, os
import logging
prompt = {json.dumps(prompt[:1000])}
payload = json.dumps({
    "model": "<用户自行配置模型>",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.1, "max_tokens": 100
}).encode()
try:
    req = urllib.request.Request(
        os.environ.get('OPENCLAW_GATEWAY_URL', 'http://localhost:18789') + '/v1/chat/completions',
        data=payload,
        headers={"Content-Type": "application/json"},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(data['choices'][0]['message']['content'])
except Exception:
    logging.exception("[judge_engine.py] suppressed")
"""],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout.strip()
            if output:
                import re as _re
                json_match = _re.search(r'\{[^}]*"patterns"[^}]*\}', output)
                if json_match:
                    data = json.loads(json_match.group())
                    return data.get("patterns", [])[:3]
        except Exception:
            pass

        return self._guess_failure_patterns(scores)

    def _guess_failure_patterns(self, scores: Dict) -> List[str]:
        """基于分数猜测失败模式（兜底）"""
        patterns = []
        if scores.get("faithfulness", 5) < 5:
            patterns.append("hallucination")
        if scores.get("relevance", 5) < 5:
            patterns.append("off_topic")
        if scores.get("completeness", 5) < 5:
            patterns.append("omission")
        if not patterns:
            patterns.append("redundancy")
        return patterns[:2]

    def get_reflexion(self, query: str, top_k: int = 2) -> List[Dict]:
        """
        同类查询时获取之前反思经验

        按关键词匹配最近的反思记录，返回匹配的反思三元组。
        供下次同类问题注入上下文使用。
        """
        if not os.path.exists(REFLEXION_PATH):
            return []

        query_kw = set(_extract_keywords(query, max_kw=8))

        reflexes = []
        with open(REFLEXION_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rec_kw = set(_extract_keywords(r.get("query", ""), max_kw=6))
                overlap = len(query_kw & rec_kw)
                if overlap > 0:
                    r["_score"] = overlap
                    reflexes.append(r)

        reflexes.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return reflexes[:top_k]

    def format_reflexion_context(self, query: str) -> str:
        """生成反思经验注入上下文"""
        reflexes = self.get_reflexion(query)
        if not reflexes:
            return ""

        parts = ["⚠️ 历史反思提示（同类问题曾出现以下问题）:"]
        for i, r in enumerate(reflexes, 1):
            patterns = ", ".join(r.get("patterns", []))
            parts.append(f"  [{i}] 模式: {patterns} | 问题: {r['query'][:60]}")
        return "\n".join(parts)

    def _trim_reflexions(self, max_lines: int = 200):
        if not os.path.exists(REFLEXION_PATH):
            return
        with open(REFLEXION_PATH) as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(REFLEXION_PATH, "w") as f:
                f.writelines(lines[-max_lines:])

    def reflexion_stats(self) -> Dict:
        """反思统计"""
        if not os.path.exists(REFLEXION_PATH):
            return {"total": 0}
        with open(REFLEXION_PATH) as f:
            lines = [l for l in f if l.strip()]
        if not lines:
            return {"total": 0}

        pattern_counts = {}
        for line in lines:
            try:
                r = json.loads(line)
                for p in r.get("patterns", []):
                    pattern_counts[p] = pattern_counts.get(p, 0) + 1
            except json.JSONDecodeError:
                pass

        return {
            "total": len(lines),
            "pattern_counts": dict(sorted(pattern_counts.items(), key=lambda x: -x[1])),
        }

    def stats(self) -> Dict:
        """统计信息"""
        if not os.path.exists(self.verified_path):
            return {"total": 0}

        with open(self.verified_path) as f:
            lines = [l for l in f if l.strip()]

        if not lines:
            return {"total": 0}

        total = len(lines)
        avg_f = sum(json.loads(l).get("faithfulness", 0) for l in lines) / total
        avg_r = sum(json.loads(l).get("relevance", 0) for l in lines) / total
        avg_c = sum(json.loads(l).get("completeness", 0) for l in lines) / total

        return {
            "total": total,
            "avg_faithfulness": round(avg_f, 1),
            "avg_relevance": round(avg_r, 1),
            "avg_completeness": round(avg_c, 1),
            "avg_total": round((avg_f + avg_r + avg_c) / 3, 1),
        }



# ── 事件类型 ─────────────────────────────────────
EVENT_TYPES = {
    "user_correction": "用户显式纠正（'不对/错了/不是'等）",
    "skill_mismatch": "技能选择错误（选了不合适的技能）",
    "mode_misclassification": "模式分类错误（Agent/快速模式选错）",
    "hallucination": "幻觉/编造内容",
    "execution_failure": "执行失败（工具调用失败/超时）",
    "omission": "遗漏关键信息",
}

# ── 用户纠正关键词模式 ──────────────────────────
# 精确匹配规则：
#   1. 短模式优先匹配完整短语而非单字，避免误触
#   2. 否定词优先匹配「主语 + 否定 + 评价」结构
#   3. 长模式（3字以上）不做额外限制
CORRECTION_PATTERNS = [
    # 整句否定（高可信）
    r"(不对吧|不对啊|不对呀|不对不对)",
    r"(不对[！!。]|错了[！!。])$",
    r"(弄错|搞错|说错|看错|理解错)",
    r"(搞反|做反|说反|搞反了|做反了|说反了)",
    r"应该[是]?.*(而不|却不|但没)",
    r"(不是|并非|并没有).*(这样|那样|如此)",
    r"你(理解|听|说|会错|搞|弄|做)(反|错|差了|不对)",
    r"我说的不是这个|我说的不是|不是这个意思",
    r"你理解错了|你理解有误|你误会了",
    r"我没说|我没说过|我没这个意思",
    r"不是[让叫要]你做|不是[让叫要]你用",
    r"换一个|换种|换个|重新[来做搞]|重做|重搞",
    r"这个(工具|方法|方式)(不对|错了|不行|不好)",
    r"没(理解|明白|讲清楚|说清楚|说清)",
    r"你(不|没有).*(明白|懂|理解)",
    r"stop|STOP|停止|停下|暂停|打住",
    # 短否定词（2字），需要"这个/你是/完全/全都/根本"等前缀才匹配
    r"(这个|你是|这是|完全|全都|根本)(不对|错了|不是|不行|不好)",
]

# ── 技能失配关键词 ─────────────────────────────
SKILL_MISMATCH_PATTERNS = [
    r"不是[找查]这个|不是要[找查]",
    r"用的不对|用错了|用错了工具|这个工具不对",
    r"这个工具不合适|不是用这个",
    r"不应该[用叫调取]这个|不是[用叫调取]这个",
    r"另一[个种]工具|换成[的]?另一个",
    r"不是[用叫调取](的|这个)",
]


# ── 被动反馈识别模式 ──────────────────────────
# 原则：不问不打扰，用户自然流露再记
# 精确度优先：宁可漏记也少误触

# 强正面信号：独立出现即说明回答有价值
POSITIVE_FEEDBACK_STRONG = [
    r"(学到了|明白了|懂了|清楚了)[！!。.]?[\s]*$",
    r"就想要这个|正想要|正[好是]我要的|就是这个|正需要",
    r"很棒|很赞|厉害了|优秀了|太棒了|太赞了",
    r"(很|挺|蛮|真|太)(不错|好|棒|厉害|准|详细|全面|到位)[！!。.\s]*$",
    r"(非常|十分|特别)(不错|好|棒|满意|详细|全面|有用|到位)",
    r"(满意|完美|精准|详细|清晰|全面|透彻|到位)[！!。.\s]*$",
    r"(有用|好用|管用|靠谱|实用)[！!。.\s]*$",
    r"这次(回答|答案|结果)(不错|很好|对了|很棒|可以|很准|靠谱)",
    r"这个答案(不错|很好|对了|可以|靠谱)",
    r"对的对的|对对对|没错没错|是的是的|正解|完全正确",
]

# 弱正面信号：搭配后续消息使用时需排除反悔
POSITIVE_FEEDBACK_WEAK = [
    r"(辛苦了|好的|好嘞|好滴|好哒|OK|ok)[！!。.\s]*$",
    r"知道了|晓得了|了解了",
    r"(有帮助|有道理|说得对|你说得对|是这样的)",
    r"(谢谢|多谢|感谢)(你|啦|了|！|!|。|.)?[\s]*$",
]

# 负面信号
NEGATIVE_FEEDBACK_PATTERNS = [
    r"(太|有点|有点|有些|过于)(啰嗦|长|复杂|笼统|敷衍|简单)[了]?[！!。]?$",
    r"(没|没有)(讲|说)(清楚|明白|完整|全|透)[！!。]?$",
    r"(不够|不太|不够)(具体|详细|清晰|准确|深入)[！!。]?$",
    r"(答非所问|避重就轻|敷衍了事|糊弄[人]?|瞎说|乱说)",
    r"(废话|套话|空话|假大空|模板[化]?[的]?回答)",
    r"(毫无|没什么|没有)(帮助|用处|意义|价值)[！!。]?$",
    r"(算了|不问你了|叫别人[吧]?|我再问别人|换人[吧]?)",
    r"这个(回答|答案)(不对|不行|不好|差[劲]?|没用)[！!。]?$",
]


class ReplayBuffer:
    """重放缓冲区 — 捕获纠正信号 → 蒸馏经验 → 反哺系统"""

    RB_BUFFER_DIR = os.path.join(WORKSPACE, ".replay_buffer")
    RB_RECORDS_PATH = os.path.join(RB_BUFFER_DIR, "records.jsonl")
    RB_DISTILLED_PATH = os.path.join(RB_BUFFER_DIR, "distilled.jsonl")
    RB_METADATA_PATH = os.path.join(RB_BUFFER_DIR, "meta.json")

    def __init__(self):
        os.makedirs(self.RB_BUFFER_DIR, exist_ok=True)
        self._meta = self._load_meta()

    # ── 公共方法 ─────────────────────────────────

    def _similar_events(self, user_message: str, threshold: float = 0.7) -> List[Dict]:
        """检查最近事件是否有语义相似的，避免重复记录"""
        records = self._load_all()
        if not records:
            return []

        # 提取用户消息关键词
        msg_kw = set(self._extract_keywords(user_message, max_kw=10))
        if not msg_kw:
            return []

        similar = []
        for r in records[-50:]:  # 只查最近 50 条
            r_msg = r.get("context", {}).get("user_message", "")
            r_kw = set(self._extract_keywords(r_msg, max_kw=10))
            if not r_kw:
                continue
            # Jaccard 相似度
            overlap = len(msg_kw & r_kw)
            union = len(msg_kw | r_kw)
            jaccard = overlap / union if union > 0 else 0
            if jaccard >= threshold:
                similar.append((jaccard, r))

        similar.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in similar]

    def record(self, event: Dict) -> str:
        """
        记录一个纠正/失败事件。

        写入前做语义去重：最近 50 条中用户消息 Jaccard 相似度 ≥0.7 →
        不新增记录，改为更新现有记录的 occurrence_count 和最近时间。

        Args:
            event: 事件数据，格式：
                {
                    "type": "user_correction",
                    "context": {
                        "user_message": "用户原话",
                        "assistant_response": "我当时的回复（可选）",
                        "task_type": "任务类型（可选）",
                        "conversation_stage": "对话阶段（可选）",
                    },
                    "error": {
                        "description": "错误描述",
                        "details": "额外细节（可选）",
                    },
                    "correction": {
                        "expected": "应该怎么做（可选）",
                        "fixed_by_user": True/False,
                        "fixed_by_system": True/False,
                    },
                    "meta": {
                        "source": "user_explicit|auto_detect|judge_engine|pipeline",
                        "severity": "low|medium|high",
                    }
                }

        Returns:
            record_id: 记录ID
        """
        user_msg = event.get("context", {}).get("user_message", "")

        # 去重检查：相似事件合并而非新增
        similar = self._similar_events(user_msg, threshold=0.7)
        if similar:
            duplicate = similar[0]
            dup_id = duplicate["id"]
            # 更新 occurrence_count 和 last_seen
            existing = self._load_all_lines()
            updated = []
            found = False
            for line in existing:
                try:
                    r = json.loads(line)
                    if r["id"] == dup_id:
                        r["occurrence_count"] = r.get("occurrence_count", 1) + 1
                        r["last_seen"] = datetime.now(BEIJING_TZ).isoformat()
                        updated.append(json.dumps(r, ensure_ascii=False) + "\n")
                        found = True
                    else:
                        updated.append(line)
                except json.JSONDecodeError:
                    updated.append(line)
            if found:
                with open(self.RB_RECORDS_PATH, "w") as f:
                    f.writelines(updated)
                return dup_id

        record_id = f"rb_{int(time.time())}_{os.urandom(4).hex()}"

        record = {
            "id": record_id,
            "type": event.get("type", "user_correction"),
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "occurrence_count": 1,
            "last_seen": datetime.now(BEIJING_TZ).isoformat(),
            "context": {
                "user_message": event.get("context", {}).get("user_message", ""),
                "assistant_response": event.get("context", {}).get("assistant_response", ""),
                "task_type": event.get("context", {}).get("task_type", ""),
                "conversation_stage": event.get("context", {}).get("conversation_stage", ""),
            },
            "error": {
                "description": event.get("error", {}).get("description", ""),
                "details": event.get("error", {}).get("details", ""),
            },
            "correction": {
                "expected": event.get("correction", {}).get("expected", ""),
                "fixed_by_user": event.get("correction", {}).get("fixed_by_user", False),
                "fixed_by_system": event.get("correction", {}).get("fixed_by_system", False),
            },
            "meta": {
                "source": event.get("meta", {}).get("source", "auto_detect"),
                "severity": event.get("meta", {}).get("severity", "medium"),
                "confidence": event.get("meta", {}).get("confidence", 0.5),
            },
        }

        # 追加写入
        with open(self.RB_RECORDS_PATH, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 更新元数据
        self._update_meta(event.get("type", "user_correction"))

        return record_id

    def detect_correction(self, user_message: str,
                          assistant_response: str = "",
                          context: Optional[Dict] = None) -> Optional[Dict]:
        """
        检测用户消息是否包含纠正信号。
        如果有，自动构建并记录事件。

        Args:
            user_message: 用户最新消息
            assistant_response: 上一条助手回复
            context: 额外上下文

        Returns:
            如果检测到纠正事件 → 记录的数据；否则 None
        """
        msg_lower = user_message.lower()

        # 1. 检查纠正关键词
        is_correction = False
        matched_pattern = ""
        for pat in CORRECTION_PATTERNS:
            if re.search(pat, user_message):
                is_correction = True
                matched_pattern = pat
                break

        # 2. 检查技能失配关键词
        is_skill_mismatch = False
        for pat in SKILL_MISMATCH_PATTERNS:
            if re.search(pat, user_message):
                is_skill_mismatch = True
                matched_pattern = pat
                break

        if not is_correction and not is_skill_mismatch:
            return None

        # 确定类型
        if is_skill_mismatch:
            event_type = "skill_mismatch"
        elif any(k in msg_lower for k in ["幻觉", "编造", "没这个", "没有这回事"]):
            event_type = "hallucination"
        elif any(k in msg_lower for k in ["漏了", "少了", "没提", "没说", "没讲"]):
            event_type = "omission"
        else:
            event_type = "user_correction"

        # 构建事件
        event = {
            "type": event_type,
            "context": {
                "user_message": user_message[:500],
                "assistant_response": assistant_response[:1000],
                "task_type": (context or {}).get("task_type", ""),
                "conversation_stage": (context or {}).get("conversation_stage", ""),
            },
            "error": {
                "description": f"检测到纠正信号（模式: {matched_pattern}）",
                "details": f"用户消息: {user_message[:200]}",
            },
            "correction": {
                "expected": "",
                "fixed_by_user": True,
                "fixed_by_system": False,
            },
            "meta": {
                "source": "user_explicit",
                "severity": "medium",
                "confidence": 0.7,
            },
        }

        return self.record(event)

    def detect_feedback(self, user_message: str) -> Optional[Dict]:
        """
        被动检测用户自然流露的评价：
          - 正面："不错""学到了""很好"
          - 负面："太啰嗦""不够详细"

        不主动询问，用户不评价就不管。
        负面反馈会同时作为纠正信号记录。

        Args:
            user_message: 用户最新消息

        Returns:
            如果检测到 → 记录的数据；否则 None
        """
        # 先检测是否包含纠正信号（已有逻辑）
        correction = self.detect_correction(user_message, assistant_response="")
        if correction:
            return correction

        # 被动检测正面评价
        # 强信号：独立出现即记录，高可信度
        for pat in POSITIVE_FEEDBACK_STRONG:
            if re.search(pat, user_message):
                event = {
                    "type": "user_feedback",
                    "context": {
                        "user_message": user_message[:500],
                        "assistant_response": "",
                    },
                    "error": {
                        "description": f"用户正面反馈（强信号: {pat}）",
                    },
                    "correction": {
                        "expected": "",
                        "fixed_by_user": False,
                        "fixed_by_system": False,
                    },
                    "meta": {
                        "source": "passive_detect",
                        "severity": "low",
                        "confidence": 0.8,
                        "feedback_type": "positive",
                    },
                }
                return self.record(event)

        # 弱正面信号：先看后续消息有没有反悔，没有则记录，降低可信度
        for pat in POSITIVE_FEEDBACK_WEAK:
            if re.search(pat, user_message):
                event = {
                    "type": "user_feedback",
                    "context": {
                        "user_message": user_message[:500],
                        "assistant_response": "",
                    },
                    "error": {
                        "description": f"用户正面反馈（弱信号: {pat}）",
                    },
                    "correction": {
                        "expected": "",
                        "fixed_by_user": False,
                        "fixed_by_system": False,
                    },
                    "meta": {
                        "source": "passive_detect",
                        "severity": "low",
                        "confidence": 0.5,
                        "feedback_type": "positive_weak",
                    },
                }
                return self.record(event)

        # 被动检测负面评价
        for pat in NEGATIVE_FEEDBACK_PATTERNS:
            if re.search(pat, user_message):
                event = {
                    "type": "user_feedback",
                    "context": {
                        "user_message": user_message[:500],
                        "assistant_response": "",
                    },
                    "error": {
                        "description": f"用户负面反馈（模式: {pat}）",
                    },
                    "correction": {
                        "expected": "",
                        "fixed_by_user": True,
                        "fixed_by_system": False,
                    },
                    "meta": {
                        "source": "passive_detect",
                        "severity": "medium",
                        "confidence": 0.7,
                        "feedback_type": "negative",
                    },
                }
                return self.record(event)

        return None

    def detect_skill_mismatch(self, skill_name: str,
                              user_intent: str,
                              result: Dict) -> Optional[str]:
        """
        检测技能选择是否失配。
        根据技能返回结果和用户意图判断。

        Args:
            skill_name: 选择的技能名
            user_intent: 用户意图
            result: 技能执行结果

        Returns:
            如果检测到失配 → record_id；否则 None
        """
        success = result.get("success", True)
        error = result.get("error", "")
        result_msg = result.get("result", "")

        # 技能执行失败但有更具体原因 → 可能是失配
        if not success and error:
            event = {
                "type": "skill_mismatch",
                "context": {
                    "user_message": user_intent[:500],
                    "task_type": user_intent[:200],
                },
                "error": {
                    "description": f"技能 '{skill_name}' 执行失败：{error[:200]}",
                    "details": f"完整错误: {error[:500]}",
                },
                "correction": {
                    "fixed_by_user": False,
                    "fixed_by_system": True,
                },
                "meta": {
                    "source": "auto_detect",
                    "severity": "medium",
                    "confidence": 0.5,
                },
            }
            return self.record(event)

        return None

    def detect_mode_mismatch(self, chosen_mode: str,
                             user_message: str,
                             user_next_message: str = "") -> Optional[str]:
        """
        检测模式分类是否错误。
        如果用户后续消息显示了明显的模式不匹配，记录。

        Args:
            chosen_mode: pipeline 选择的模式 ("fast"/"agent")
            user_message: 用户原始消息
            user_next_message: 用户下一轮消息（可选）

        Returns:
            如果检测到失配 → record_id；否则 None
        """
        if not user_next_message:
            return None

        # 如果选了快速模式但用户下一轮需要复杂处理
        if chosen_mode == "fast":
            complaint_indicators = [
                "没讲完", "没说清楚", "不够", "太简单", "详细点",
                "继续", "接着", "还没",
            ]
            if any(k in user_next_message for k in complaint_indicators):
                event = {
                    "type": "mode_misclassification",
                    "context": {
                        "user_message": user_message[:500],
                        "assistant_response": "",
                        "task_type": "",
                    },
                    "error": {
                        "description": f"快速模式选择不当，用户后续要求更多内容",
                        "details": f"选了快速模式但用户后续说: {user_next_message[:200]}",
                    },
                    "correction": {
                        "expected": "应该选 Agent 模式",
                        "fixed_by_user": False,
                        "fixed_by_system": True,
                    },
                    "meta": {
                        "source": "auto_detect",
                        "severity": "low",
                        "confidence": 0.4,
                    },
                }
                return self.record(event)

        # 如果选了 Agent 模式但用户说"太啰嗦"等
        if chosen_mode == "agent":
            complaint_indicators = [
                "太长了", "不要这么多", "简洁点", "少说点",
                "废话", "啰嗦",
            ]
            if any(k in user_next_message for k in complaint_indicators):
                event = {
                    "type": "mode_misclassification",
                    "context": {
                        "user_message": user_message[:500],
                        "assistant_response": "",
                        "task_type": "",
                    },
                    "error": {
                        "description": f"Agent 模式选择不当，用户觉得信息过量",
                        "details": f"选了Agent模式但用户后续说: {user_next_message[:200]}",
                    },
                    "correction": {
                        "expected": "应该选快速模式",
                        "fixed_by_user": False,
                        "fixed_by_system": True,
                    },
                    "meta": {
                        "source": "auto_detect",
                        "severity": "low",
                        "confidence": 0.4,
                    },
                }
                return self.record(event)

        return None

    # ── 统计分析 ─────────────────────────────────

    def stats(self) -> Dict:
        """缓冲区统计"""
        records = self._load_all()
        if not records:
            return {
                "total": 0,
                "by_type": {},
                "by_severity": {},
                "by_source": {},
                "recent_rates": {},
                "top_patterns": [],
                "last_distilled": self._meta.get("last_distilled", "never"),
            }

        by_type = Counter(r["type"] for r in records)
        by_severity = Counter(r["meta"]["severity"] for r in records)
        by_source = Counter(r["meta"]["source"] for r in records)

        # 最近7天的事件率
        cutoff = time.time() - 7 * 86400
        recent = [r for r in records
                  if self._to_ts(r.get("timestamp", "")) > cutoff]
        recent_rate = len(recent) / 7  # 每日平均

        # 高频描述模式
        descriptions = [r["error"]["description"] for r in records
                        if r.get("error", {}).get("description")]
        top_descriptions = [d for d, _ in Counter(descriptions).most_common(10)]

        return {
            "total": len(records),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "by_source": dict(by_source),
            "recent_7d_rate": round(recent_rate, 2),
            "recent_7d_count": len(recent),
            "top_patterns": top_descriptions[:5],
            "last_distilled": self._meta.get("last_distilled", "never"),
            "next_distillation_due": (
                records[-1]["timestamp"]
                if self._meta.get("last_distilled") == "never"
                else ""
            ),
        }

    def get_by_type(self, event_type: str, limit: int = 20) -> List[Dict]:
        """按事件类型查询"""
        records = self._load_all()
        filtered = [r for r in records if r["type"] == event_type]
        return filtered[-limit:]

    def get_recent(self, limit: int = 20) -> List[Dict]:
        """获取最近事件"""
        records = self._load_all()
        return records[-limit:]

    # ── 蒸馏 ─────────────────────────────────────

    def distill(self, min_occurrences: int = 3) -> List[Dict]:
        """
        蒸馏高频模式 → 可复用经验

        流程：
        1. 加载所有记录
        2. 按"类型+错误描述"聚合
        3. 次数≥min_occurrences 的 → 生成经验
        4. 写入蒸馏文件 + 更新元数据

        Returns:
            蒸馏后的经验列表
        """
        records = self._load_all()
        if len(records) < min_occurrences:
            return []

        # 聚合：按 (type, error_description) 分组
        groups = defaultdict(list)
        for r in records:
            key = (r["type"], r["error"]["description"])
            groups[key].append(r)

        distilled = []
        for (event_type, desc), items in groups.items():
            if len(items) < min_occurrences:
                continue

            # 提取关键词
            keywords = self._extract_keywords(
                " ".join([
                    items[-1]["context"]["user_message"],
                    items[-1]["correction"].get("expected", ""),
                    desc,
                ])
            )

            # 构建经验记录
            experience = {
                "id": f"dist_{int(time.time())}_{os.urandom(4).hex()}",
                "timestamp": datetime.now(BEIJING_TZ).isoformat(),
                "type": event_type,
                "description": EVENT_TYPES.get(event_type, event_type),
                "pattern": desc,
                "occurrences": len(items),
                "first_seen": items[0]["timestamp"],
                "last_seen": items[-1]["timestamp"],
                "keywords": keywords,
                "example_errors": [
                    {
                        "user_message": i["context"]["user_message"][:200],
                        "expected": i["correction"].get("expected", ""),
                    }
                    for i in items[-3:]  # 最近3条示例
                ],
                "suggested_rule": self._suggest_rule(event_type, desc, keywords),
            }
            distilled.append(experience)

        # 写入蒸馏文件
        if distilled:
            with open(self.RB_DISTILLED_PATH, "a") as f:
                for d in distilled:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")

        # 更新元数据
        self._meta["last_distilled"] = datetime.now(BEIJING_TZ).isoformat()
        self._meta["last_distill_count"] = len(distilled)
        self._save_meta()

        return distilled

    def get_distilled(self, event_type: Optional[str] = None) -> List[Dict]:
        """获取已蒸馏的经验"""
        if not os.path.exists(self.RB_DISTILLED_PATH):
            return []
        records = []
        with open(self.RB_DISTILLED_PATH) as f:
            for line in f:
                try:
                    r = json.loads(line.strip())
                    if event_type is None or r.get("type") == event_type:
                        records.append(r)
                except json.JSONDecodeError:
                    continue
        return records

    def format_as_evolution_proposal(self, distilled: Dict) -> Dict:
        """
        将蒸馏结果格式化为自进化提案。
        供 self_evolution_engine 消费。
        """
        return {
            "source": "replay_buffer",
            "title": f"[纠正学习] {distilled['description']} — {distilled['pattern'][:40]}",
            "summary": f"在{distilled['occurrences']}次相似事件中发现稳定模式: {distilled['pattern']}",
            "rules": [distilled["suggested_rule"]] if distilled["suggested_rule"] else [],
            "examples": [
                f"用户说「{e['user_message']}」时的期望: {e['expected']}"
                for e in distilled.get("example_errors", [])
            ],
            "tags": ["replay_buffer", distilled["type"], "correction_learning"],
            "when_to_use": f"当检测到{distilled['description']}模式时",
            "meta": {
                "occurrences": distilled["occurrences"],
                "first_seen": distilled["first_seen"],
                "last_seen": distilled["last_seen"],
                "confidence": min(1.0, distilled["occurrences"] / 10),
            },
        }

    def harvest_to_evolution(self, min_occurrences: int = 3) -> Dict:
        """
        C3 桥接: 蒸馏 → 格式化 → 注入 SelfEvolutionEngine.
        自动化端到端闭还: 纠正记录 → 模式蒸馏 → 规则注册.

        Returns: {"distilled": int, "registered": int, "skipped": int}
        """
        distilled = self.distill(min_occurrences=min_occurrences)
        result = {"distilled": len(distilled), "registered": 0, "skipped": 0}
        if not distilled:
            return result

        try:
            from core.engines.hooks.self_evolution_engine import get_evolution_engine
            engine = get_evolution_engine()
            for d in distilled:
                proposal = self.format_as_evolution_proposal(d)
                rules = proposal.get("rules", [])
                if not rules:
                    result["skipped"] += 1
                    continue
                for rule in rules:
                    try:
                        engine.register_rule(
                            content=rule,
                            source="replay_buffer_harvest",
                            category="correction_learning",
                            tags=proposal.get("tags", []),
                        )
                        result["registered"] += 1
                    except Exception:
                        result["skipped"] += 1
        except ImportError:
            pass  # SelfEvolution 未安装
        except Exception:
            pass  # 非阻塞
        return result

    def clear_old(self, days: int = 90) -> int:
        """
        清理旧记录。

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        if not os.path.exists(self.RB_RECORDS_PATH):
            return 0

        cutoff = time.time() - days * 86400
        kept = []
        removed = 0

        with open(self.RB_RECORDS_PATH) as f:
            for line in f:
                try:
                    r = json.loads(line.strip())
                    ts = self._to_ts(r.get("timestamp", ""))
                    if ts > cutoff:
                        kept.append(line)
                    else:
                        removed += 1
                except json.JSONDecodeError:
                    kept.append(line)

        with open(self.RB_RECORDS_PATH, "w") as f:
            f.writelines(kept)

        return removed

    # ── 内部方法 ─────────────────────────────────

    def _load_all(self) -> List[Dict]:
        """加载所有记录（解析为 dict）"""
        if not os.path.exists(self.RB_RECORDS_PATH):
            return []
        records = []
        with open(self.RB_RECORDS_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _load_all_lines(self) -> List[str]:
        """加载所有原始行（含末尾换行）"""
        if not os.path.exists(self.RB_RECORDS_PATH):
            return []
        with open(self.RB_RECORDS_PATH) as f:
            return f.readlines()

    def _load_meta(self) -> Dict:
        if os.path.exists(self.RB_METADATA_PATH):
            try:
                with open(self.RB_METADATA_PATH) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": 1,
            "total_records": 0,
            "by_type": {},
            "last_distilled": "never",
            "last_distill_count": 0,
            "created_at": datetime.now(BEIJING_TZ).isoformat(),
        }

    def _save_meta(self):
        with open(self.RB_METADATA_PATH, "w") as f:
            json.dump(self._meta, f, indent=2, ensure_ascii=False)

    def _update_meta(self, event_type: str):
        self._meta["total_records"] = self._meta.get("total_records", 0) + 1
        by_type = self._meta.get("by_type", {})
        by_type[event_type] = by_type.get(event_type, 0) + 1
        self._meta["by_type"] = by_type
        self._save_meta()

    def _to_ts(self, iso_str: str) -> float:
        """ISO 时间字符串 → 时间戳"""
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0

    def _extract_keywords(self, text: str, max_kw: int = 5) -> List[str]:
        """从文本中提取关键词"""
        words = re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]+\+?[a-zA-Z0-9]*', text)
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不",
                       "人", "都", "一", "上", "也", "很", "到", "说", "要",
                       "去", "你", "会", "着", "没有", "看", "好", "自己",
                       "这", "他", "她", "它", "们", "那", "些", "这个",
                       "什么", "怎么", "为什么", "如何", "因为", "所以",
                       "但是", "如果", "可以", "应该", "可能", "已经",
                       "还是", "或者", "吗", "呢", "吧", "啊", "呀", "啦",
                       "嗯", "哦", "哈", "嘿"}
        filtered = [w.lower() for w in words if w.lower() not in stop_words and len(w.strip()) > 0]
        freq = {}
        for w in filtered:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: (-x[1], -len(x[0])))
        return [w for w, _ in sorted_words[:max_kw]]

    def _suggest_rule(self, event_type: str, description: str,
                      keywords: List[str]) -> str:
        """根据事件类型和关键词，生成建议规则"""
        if event_type == "skill_mismatch":
            return (
                f"当用户意图包含关键词 '{'/'.join(keywords[:3])}' 时，"
                f"优先选择对应领域的专用技能而非通用技能。"
                f"如果某个技能的执行结果为空或明显不对，立即检查技能选择是否正确。"
            )
        elif event_type == "hallucination":
            return (
                f"在回答包含数据/数字/统计信息的问题时，"
                f"必须标注来源并区分确定性数据和推测性内容。"
                f"如果不确定，明说'这个我不确定，建议核实'。"
            )
        elif event_type == "mode_misclassification":
            return (
                f"当用户请求涉及复杂分析、多步操作或需要外部工具时，"
                f"优先选择 Agent 模式而非快速模式。"
                f"反之，如果用户只问简单问题，优先快速模式。"
            )
        elif event_type == "omission":
            return (
                f"在回答后检查：是否涵盖了用户所有子问题？"
                f"如果用户问题包含多个维度，按点逐一回应，避免只答了部分。"
            )
        else:
            return (
                f"检测到用户纠正模式 '{description[:40]}'，"
                f"建议下次遇到类似上下文时调整回应方式。"
            )





# ── CLI 入口已移至 core/engines/quality/cli.py（#46 拆分） ──
# 用法：python3 -m core.engines.quality.cli score --query ...
# 或：python3 cli.py score --query ...
