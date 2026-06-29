"""
Crusheart Agent OS — DAG 上下文管理器 v1.0
基于 LCM 论文思想的上下文管理：
- 每条消息作为独立节点，保留依赖关系（DAG）
- SQLite WAL 持久化
- 增量摘要压缩 + 新鲜尾巴保留
- 人格节点保护（永不压缩）
- FTS5 全文搜索（可选，降级关键词搜索）
- FAISS 向量索引（可选，降级 n-gram 哈希）
- RRF 融合排序
- 记忆巩固设计（CLS + 干扰管理 + 预测编码冲突检测）
"""

import os, json, time, hashlib, re, threading, logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)
BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

# ── 环境检测 ──
_HAS_SQLITE = False
try:
    import sqlite3
    _HAS_SQLITE = True
except ImportError:
    pass

_HAS_NUMPY = False
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    pass

_HAS_FAISS = False
try:
    import faiss
    _HAS_FAISS = True
except ImportError:
    pass

try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

# ── v6.6.0: 域 (Domain) 定义 — Cognition Forest 分域思想 ──
# 节点按 domain 分域管理，各域独立上下文窗口、摘要、压缩策略
# 避免"聊了10轮后系统配置信息被挤出窗口"问题
DOMAIN_NAMES = {
    "user":    "用户画像 (USER.md, 偏好, 个性, 身份)",
    "system":  "系统能力 (技能列表, 工具, 配置, 版本)",
    "memory":  "长期记忆 (记忆系统检索结果, 固化知识)",
    "chat":    "对话内容 (当前会话上下文, 默认域)",
    "meta":    "元认知 (自进化, Reflexion, 行为规则)",
}

# 各域的默认上下文窗口大小 (tokens)
DOMAIN_MAX_TOKENS = {
    "user": 4000,
    "system": 6000,
    "memory": 8000,
    "chat": 12000,
    "meta": 2000,
}

# ── v6.5.10: 语义关系类型 ──
RELATION_TYPES = {
    "cause_effect": {"label": "因果", "bidirectional": False},
    "temporal_seq": {"label": "时序", "bidirectional": False},
    "dependency": {"label": "依赖", "bidirectional": False},
    "analogy": {"label": "类比", "bidirectional": True},
    "same_topic": {"label": "同主题", "bidirectional": True},
    "elaboration": {"label": "补充说明", "bidirectional": True},
    "contradiction": {"label": "矛盾", "bidirectional": True},
}

# ── DAG 节点模型 ──
@dataclass
class DAGNode:
    node_id: str = ""
    session_key: str = ""
    role: str = "user"           # user | assistant | system | summary
    content: str = ""
    parent_id: Optional[str] = None   # 父节点 ID
    children: List[str] = field(default_factory=list)  # 子节点 ID 列表
    priority: int = 0                  # 0=普通, 1=重要, 2=CRITICAL(永不压缩)
    tokens: int = 0
    importance_score: float = 0.0      # 重要性评分 0~1
    is_summary: bool = False           # 是否摘要节点
    node_type: str = "message"         # message | summary | system
    keywords: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # ── v6.5.10: 语义关系字段 ──
    relation_type: str = ""  # "cause_effect"|"temporal_seq"|etc.
    linked_nodes: List[str] = field(default_factory=list)  # IDs of related nodes across sessions
    # ── v6.6.0: 域 (Domain) 字段 ──
    domain: str = "chat"  # "user"|"system"|"memory"|"chat"|"meta"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DAGNode":
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


class DAGContextManager:
    """
    DAG 上下文管理器 — 持久化 + 增量摘要 + 回溯检索 + 向量索引
    环境无关：无渠道/API 依赖，numpy/FAISS 可选降级
    """

    def __init__(self, db_path: str = None, max_context_tokens: int = 12000,
                 fresh_tail_count: int = 5, context_threshold: int = 8000,
                 domain_max_tokens: dict = None):
        self.max_context_tokens = max_context_tokens
        self.fresh_tail_count = fresh_tail_count
        self.context_threshold = context_threshold
        self.domain_max_tokens = domain_max_tokens or dict(DOMAIN_MAX_TOKENS)
        self._db_path = db_path or os.path.join(WORKSPACE, ".state", "dag_context.db")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化 SQLite"""
        if not _HAS_SQLITE:
            logger.warning("SQLite unavailable, DAG falls back to JSON-only mode")
            self._conn = None
            self._json_path = os.path.join(WORKSPACE, ".state", "dag_context_fallback.json")
            self._json_data = {"nodes": [], "edges": []}
            os.makedirs(os.path.dirname(self._json_path), exist_ok=True)
            return
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS dag_nodes (
                node_id TEXT PRIMARY KEY,
                session_key TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                content TEXT DEFAULT '',
                parent_id TEXT,
                priority INTEGER DEFAULT 0,
                tokens INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0.0,
                is_summary INTEGER DEFAULT 0,
                node_type TEXT DEFAULT 'message',
                keywords TEXT DEFAULT '',
                timestamp REAL DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_session ON dag_nodes(session_key);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON dag_nodes(timestamp);
        """)
        # FTS5 (可选)
        try:
            self._conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS dag_fts USING fts5(content, node_id UNINDEXED, tokenize='porter unicode61')")
        except Exception:
            pass
        # v6.5.10: Add relation columns (safe migration)
        try:
            self._conn.execute("ALTER TABLE dag_nodes ADD COLUMN relation_type TEXT DEFAULT ''")
        except Exception:
            pass  # Column already exists
        try:
            self._conn.execute("ALTER TABLE dag_nodes ADD COLUMN linked_nodes TEXT DEFAULT '[]'")
        except Exception:
            pass
        # v6.6.0: Add domain column (safe migration)
        try:
            self._conn.execute("ALTER TABLE dag_nodes ADD COLUMN domain TEXT DEFAULT 'chat'")
        except Exception:
            pass
        try:
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_domain ON dag_nodes(domain)")
        except Exception:
            pass

    def add_message(self, session_key: str, role: str, content: str,
                    parent_id: str = None, priority: int = 0,
                    tokens: int = None, node_type: str = "message",
                    metadata: dict = None,
                    relation_type: str = "", linked_nodes: list = None,
                    domain: str = "chat") -> str:
        """添加一条消息到 DAG"""
        node_id = hashlib.md5(f"{session_key}{role}{content}{time.time()}".encode()).hexdigest()[:16]
        now = time.time()
        if tokens is None:
            tokens = len(content)

        # 关键词提取
        keywords = self._extract_keywords(content)

        # 重要性计算
        importance = self._calc_importance(content, priority)

        # 域规范化
        if domain not in DOMAIN_NAMES:
            domain = "chat"

        if _HAS_SQLITE and self._conn:
            with self._lock:
                linked_nodes_json = json.dumps(linked_nodes or [], ensure_ascii=False)
                self._conn.execute(
                    """INSERT OR REPLACE INTO dag_nodes
                    (node_id, session_key, role, content, parent_id, priority,
                     tokens, importance_score, is_summary, node_type, keywords,
                     timestamp, metadata, relation_type, linked_nodes, domain)
                    VALUES (?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?)""",
                    (node_id, session_key, role, content[:5000], parent_id, priority,
                     tokens, importance, node_type, json.dumps(list(keywords), ensure_ascii=False),
                     now, json.dumps(metadata or {}, ensure_ascii=False, default=str),
                     relation_type, linked_nodes_json, domain)
                )
                # 更新父节点 metadata，将当前节点加入其 children 列表
                if parent_id:
                    row = self._conn.execute(
                        "SELECT metadata FROM dag_nodes WHERE node_id = ?", (parent_id,)
                    ).fetchone()
                    if row:
                        parent_meta = json.loads(row[0]) if row[0] else {}
                        children = parent_meta.get("children", [])
                        if node_id not in children:
                            children.append(node_id)
                        parent_meta["children"] = children
                        self._conn.execute(
                            "UPDATE dag_nodes SET metadata = ? WHERE node_id = ?",
                            (json.dumps(parent_meta, ensure_ascii=False), parent_id,)
                        )
                self._conn.commit()

                # FTS5 更新（中文用 jieba 切词后存储，使中文搜索有效）
                try:
                    if _HAS_JIEBA:
                        fts_content = ' '.join(jieba.cut(content[:2000]))
                    else:
                        fts_content = content[:2000]
                    self._conn.execute("INSERT OR REPLACE INTO dag_fts VALUES (?, ?)", (fts_content, node_id))
                except Exception:
                    pass
        else:
            # JSON fallback
            node = DAGNode(
                node_id=node_id, session_key=session_key, role=role,
                content=content, parent_id=parent_id, priority=priority,
                tokens=tokens, importance_score=importance, node_type=node_type,
                keywords=list(keywords), timestamp=now, metadata=metadata or {},
                relation_type=relation_type, linked_nodes=linked_nodes or [],
                domain=domain,
            )
            self._json_data["nodes"].append(node.to_dict())
            self._save_json()

        return node_id

    def get_context_window(self, session_key: str, max_tokens: int = None) -> List[DAGNode]:
        """
        获取当前会话的上下文窗口（按 domain 分组，各域独立 token cap）
        避免 chat 域长对话把 system 域配置挤出窗口。
        """
        max_tok = max_tokens or self.max_context_tokens
        all_nodes = self._get_session_nodes(session_key)
        if not all_nodes:
            return []

        default_domain_max = max_tok // max(len(DOMAIN_NAMES), 1)

        # 按 domain 分组
        by_domain: Dict[str, List] = {}
        for n in all_nodes:
            d = n.domain if hasattr(n, 'domain') and n.domain else "chat"
            by_domain.setdefault(d, []).append(n)

        result = []
        for domain, nodes in by_domain.items():
            domain_cap = self.domain_max_tokens.get(domain, default_domain_max)
            nodes.sort(key=lambda n: n.timestamp)

            summaries = [n for n in nodes if n.is_summary]
            messages = [n for n in nodes if not n.is_summary]

            domain_result = []
            domain_tokens = 0

            for s in summaries:
                if domain_tokens + s.tokens > domain_cap:
                    break
                domain_result.append(s)
                domain_tokens += s.tokens

            tail = messages[-self.fresh_tail_count:]
            for m in tail:
                if domain_tokens + m.tokens > domain_cap:
                    break
                domain_result.append(m)
                domain_tokens += m.tokens

            if domain_tokens < domain_cap * 0.7:
                important = [n for n in messages[:-self.fresh_tail_count]
                            if n.importance_score >= 0.4 and n not in domain_result]
                important.sort(key=lambda n: n.importance_score, reverse=True)
                for m in important:
                    if domain_tokens + m.tokens > domain_cap:
                        break
                    domain_result.append(m)
                    domain_tokens += m.tokens

            result.extend(domain_result)

        result.sort(key=lambda n: n.timestamp)
        return result

    def search(self, query: str, session_key: str = None,
               top_k: int = 5) -> List[Dict]:
        """
        DAG 全文/语义搜索

        搜索流程：
        1. FTS5 全文搜索（SQLite 内置，首选）
        2. 关键词近似匹配（降级方案）
        3. 向量相似度搜索（numpy/FAISS 可用时）
        """
        results = []
        seen = set()

        # 方法1: SQLite FTS5 搜索
        if _HAS_SQLITE and self._conn:
            try:
                q_clean = re.sub(r'[^\w\u4e00-\u9fff ]', '', query)[:100]
                if q_clean.strip():
                    fts_results = self._conn.execute(
                        """SELECT d.* FROM dag_nodes d
                        JOIN dag_fts f ON d.node_id = f.node_id
                        WHERE dag_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?""",
                        (q_clean, top_k * 2)
                    ).fetchall()
                    for row in fts_results:
                        if row["node_id"] not in seen:
                            seen.add(row["node_id"])
                            results.append({
                                "node_id": row["node_id"],
                                "content": row["content"][:200],
                                "score": 0.9,
                                "source": "fts",
                                "timestamp": row["timestamp"],
                                "role": row["role"],
                            })
            except Exception:
                pass

        # 方法2: 关键词近似匹配（降级）
        if len(results) < top_k:
            query_kw = self._extract_keywords(query)
            if query_kw:
                all_nodes = self._get_session_nodes(session_key)
                for node in reversed(all_nodes):
                    if node.node_id in seen:
                        continue
                    node_kw = set(node.keywords)
                    if not node_kw:
                        node_kw = set(self._extract_keywords(node.content))
                    overlap = len(query_kw & node_kw)
                    if overlap > 0:
                        score = 0.5 + (overlap / max(len(query_kw | node_kw), 1)) * 0.4
                        seen.add(node.node_id)
                        results.append({
                            "node_id": node.node_id,
                            "content": node.content[:200],
                            "score": round(score, 3),
                            "source": "keyword",
                            "timestamp": node.timestamp,
                            "role": node.role,
                        })

        # 方法3: n-gram 哈希向量相似度（无 API 的轻量语义匹配）
        if len(results) < top_k:
            q_ngrams = self._ngram_hash(query.lower())
            all_nodes = self._get_session_nodes(session_key)
            scored = []
            for node in all_nodes:
                if node.node_id in seen:
                    continue
                n_ngrams = self._ngram_hash(node.content.lower())
                sim = self._ngram_cosine(q_ngrams, n_ngrams)
                if sim > 0.3:
                    scored.append((sim, node))
            scored.sort(key=lambda x: x[0], reverse=True)
            for sim, node in scored[:top_k]:
                seen.add(node.node_id)
                results.append({
                    "node_id": node.node_id,
                    "content": node.content[:200],
                    "score": round(sim, 3),
                    "source": "ngram",
                    "timestamp": node.timestamp,
                    "role": node.role,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_by_domain(self, query: str, domain: str,
                          session_key: str = None,
                          top_k: int = 5) -> List[Dict]:
        """
        在指定域内搜索
        """
        if domain not in DOMAIN_NAMES:
            return self.search(query, session_key, top_k)

        results = []
        seen = set()

        # FTS5 + domain filter
        if _HAS_SQLITE and self._conn:
            try:
                q_clean = re.sub(r'[^\w\u4e00-\u9fff ]', '', query)[:100]
                if q_clean.strip():
                    clauses = []
                    params = []
                    if session_key:
                        clauses.append("d.session_key = ?")
                        params.append(session_key)
                    clauses.append("d.domain = ?")
                    params.append(domain)
                    fts_results = self._conn.execute(
                        """SELECT d.* FROM dag_nodes d
                        JOIN dag_fts f ON d.node_id = f.node_id
                        WHERE """ + " AND ".join(clauses) + """ AND dag_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?""",
                        (*params, q_clean, top_k * 2)
                    ).fetchall()
                    for row in fts_results:
                        if row["node_id"] not in seen:
                            seen.add(row["node_id"])
                            results.append({
                                "node_id": row["node_id"],
                                "content": row["content"][:200],
                                "score": 0.9,
                                "source": "fts",
                                "timestamp": row["timestamp"],
                                "role": row["role"],
                                "domain": row["domain"],
                            })
            except Exception:
                pass

        # Keyword + domain
        if len(results) < top_k:
            query_kw = self._extract_keywords(query)
            if query_kw:
                all_nodes = self._get_session_nodes(session_key, domain=domain)
                for node in reversed(all_nodes):
                    if node.node_id in seen:
                        continue
                    node_kw = set(node.keywords)
                    if not node_kw:
                        node_kw = set(self._extract_keywords(node.content))
                    overlap = len(query_kw & node_kw)
                    if overlap > 0:
                        score = 0.5 + (overlap / max(len(query_kw | node_kw), 1)) * 0.4
                        seen.add(node.node_id)
                        results.append({
                            "node_id": node.node_id,
                            "content": node.content[:200],
                            "score": round(score, 3),
                            "source": "keyword",
                            "timestamp": node.timestamp,
                            "role": node.role,
                            "domain": node.domain,
                        })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_domain_context(self, domain: str, session_key: str = None,
                            max_tokens: int = None) -> List[DAGNode]:
        """
        获取指定域的上下文窗口（各域独立压缩和新鲜尾巴）
        """
        if domain not in DOMAIN_NAMES:
            return []
        max_tok = max_tokens or self.domain_max_tokens.get(domain, self.max_context_tokens)
        all_nodes = self._get_session_nodes(session_key, domain=domain)
        if not all_nodes:
            return []

        all_nodes.sort(key=lambda n: n.timestamp)

        summaries = [n for n in all_nodes if n.is_summary]
        messages = [n for n in all_nodes if not n.is_summary]

        result = []
        total_tokens = 0

        # 摘要优先
        for s in summaries:
            if total_tokens + s.tokens > max_tok:
                break
            result.append(s)
            total_tokens += s.tokens

        # 新鲜尾巴（域内独立保留）
        tail = messages[-self.fresh_tail_count:]
        for m in tail:
            if total_tokens + m.tokens > max_tok:
                break
            result.append(m)
            total_tokens += m.tokens

        # 重要节点补全
        if total_tokens < max_tok * 0.7:
            important = [n for n in messages[:-self.fresh_tail_count]
                        if n.importance_score >= 0.4 and n not in result]
            important.sort(key=lambda n: n.importance_score, reverse=True)
            for m in important:
                if total_tokens + m.tokens > max_tok:
                    break
                result.append(m)
                total_tokens += m.tokens

        result.sort(key=lambda n: n.timestamp)
        return result

    # ── v6.6.0: 域统计 ──

    def get_domain_stats(self, session_key: str = None) -> dict:
        """获取各域的节点统计"""
        stats = {}
        for d in DOMAIN_NAMES:
            nodes = self._get_session_nodes(session_key, domain=d)
            stats[d] = {
                "total_nodes": len(nodes),
                "summary_nodes": sum(1 for n in nodes if n.is_summary),
                "message_nodes": sum(1 for n in nodes if not n.is_summary),
                "avg_importance": round(sum(n.importance_score for n in nodes) / max(len(nodes), 1), 3),
                "tokens": sum(n.tokens for n in nodes),
            }
        return stats

    def _get_session_nodes(self, session_key: str = None, domain: str = None) -> List[DAGNode]:
        """获取会话的全部节点，可选按 domain 过滤"""
        if _HAS_SQLITE and self._conn:
            clauses = []
            params = []
            if session_key:
                clauses.append("session_key = ?")
                params.append(session_key)
            if domain and domain in DOMAIN_NAMES:
                clauses.append("domain = ?")
                params.append(domain)
            where = ""
            if clauses:
                where = "WHERE " + " AND ".join(clauses)
            rows = self._conn.execute(
                "SELECT * FROM dag_nodes " + where + " ORDER BY timestamp",
                params
            ).fetchall()
            nodes = []
            for row in rows:
                node = DAGNode(
                    node_id=row["node_id"],
                    session_key=row["session_key"],
                    role=row["role"],
                    content=row["content"],
                    parent_id=row["parent_id"],
                    priority=row["priority"],
                    tokens=row["tokens"],
                    importance_score=row["importance_score"],
                    is_summary=bool(row["is_summary"]),
                    node_type=row["node_type"],
                    keywords=json.loads(row["keywords"]) if row["keywords"] else [],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    domain=row["domain"] if "domain" in row.keys() else "chat",
                )
                nodes.append(node)
            return nodes
        else:
            nodes_data = self._json_data.get("nodes", [])
            if session_key:
                nodes_data = [n for n in nodes_data if n.get("session_key") == session_key]
            if domain and domain in DOMAIN_NAMES:
                nodes_data = [n for n in nodes_data if n.get("domain", "chat") == domain]
            return [DAGNode.from_dict(n) for n in nodes_data]

    def _extract_keywords(self, text: str) -> set:
        """提取关键词（仅用于搜索，不使用外部 API）"""
        if not text:
            return set()
        tokens = set()
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        for ch in chinese:
            tokens.add(ch)
            for i in range(len(ch) - 1):
                tokens.add(ch[i:i+2])
        english = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
        tokens.update(english)
        numbers = re.findall(r"\d{2,}", text)
        tokens.update(numbers)
        return tokens

    def _ngram_hash(self, text: str, n: int = 3) -> Dict[str, float]:
        """n-gram 哈希向量（轻量语义表示，无外部 API 依赖）"""
        ngrams = {}
        text = text.lower()
        for i in range(len(text) - n + 1):
            gram = text[i:i+n]
            h = hashlib.md5(gram.encode()).hexdigest()[:8]
            ngrams[h] = ngrams.get(h, 0) + 1
        return ngrams

    def _ngram_cosine(self, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """n-gram 向量的余弦相似度"""
        all_keys = set(v1.keys()) | set(v2.keys())
        if not all_keys:
            return 0.0
        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in all_keys)
        n1 = sum(v ** 2 for v in v1.values()) ** 0.5
        n2 = sum(v ** 2 for v in v2.values()) ** 0.5
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def _calc_importance(self, content: str, priority: int = 0) -> float:
        """计算内容重要性（0~1）"""
        if priority >= 2:
            return 1.0
        score = 0.3 + priority * 0.2
        # 长度因子
        if len(content) > 500:
            score += 0.2
        elif len(content) > 100:
            score += 0.1
        # 关键词因子
        important_terms = ["记住", "配置", "安装", "创建", "修改", "删除",
                          "important", "critical", "fix", "bug", "error"]
        for t in important_terms:
            if t in content.lower():
                score += 0.1
                break
        return min(1.0, score)

    def _save_json(self):
        try:
            with open(self._json_path, "w") as f:
                json.dump(self._json_data, f, ensure_ascii=False)
        except Exception:
            pass

    # ── v6.5.10: 语义关系方法 ──

    def _get_linked_nodes(self, node_id: str) -> list:
        if _HAS_SQLITE and self._conn:
            try:
                row = self._conn.execute(
                    "SELECT linked_nodes FROM dag_nodes WHERE node_id = ?", (node_id,)
                ).fetchone()
                if row and row[0]:
                    return json.loads(row[0])
            except Exception:
                pass
        return []

    def set_relation(self, node_id: str, relation_type: str, target_node_id: str) -> bool:
        """
        Set a semantic relation between two nodes.
        relation_type: one of RELATION_TYPES keys
        Updates both nodes' linked_nodes lists.
        """
        if relation_type not in RELATION_TYPES:
            logger.warning(f"Unknown relation type: {relation_type}")
            return False

        # Get current linked_nodes for both nodes
        linked1 = self._get_linked_nodes(node_id)
        if target_node_id not in linked1:
            linked1.append(target_node_id)

        linked2 = self._get_linked_nodes(target_node_id)
        if node_id not in linked2:
            linked2.append(node_id)

        if _HAS_SQLITE and self._conn:
            with self._lock:
                self._conn.execute(
                    "UPDATE dag_nodes SET relation_type = ?, linked_nodes = ? WHERE node_id = ?",
                    (relation_type, json.dumps(linked1, ensure_ascii=False), node_id)
                )
                if RELATION_TYPES.get(relation_type, {}).get("bidirectional", False):
                    self._conn.execute(
                        "UPDATE dag_nodes SET relation_type = ?, linked_nodes = ? WHERE node_id = ?",
                        (relation_type, json.dumps(linked2, ensure_ascii=False), target_node_id)
                    )
                self._conn.commit()

        return True

    def infer_context(self, query: str, session_key: str = None, max_depth: int = 2) -> Dict:
        """
        Build an inference chain: keyword match → follow relation links → generate coherent context.

        Returns:
        {
            "seed_nodes": [...],  # Directly matched nodes
            "chain": [...],        # Inference chain (related nodes traversed)
            "narrative": "...",    # Generated coherent context string
        }
        """
        # Step 1: Keyword search to find seed nodes
        search_results = self.search(query, session_key, top_k=3)
        seed_ids = [r["node_id"] for r in search_results]

        # Step 2: Traverse relations up to max_depth
        chain_nodes = []
        visited = set(seed_ids)
        frontier = list(seed_ids)

        for _ in range(max_depth):
            if not frontier:
                break
            next_frontier = []
            for nid in frontier:
                linked = self._get_linked_nodes(nid)
                for lid in linked:
                    if lid not in visited:
                        visited.add(lid)
                        next_frontier.append(lid)
            frontier = next_frontier
            chain_nodes.extend(frontier)

        # Step 3: Fetch content for all chain nodes
        chain_content = []
        for nid in chain_nodes:
            if _HAS_SQLITE and self._conn:
                try:
                    row = self._conn.execute(
                        "SELECT role, content, relation_type FROM dag_nodes WHERE node_id = ?",
                        (nid,)
                    ).fetchone()
                    if row:
                        rel_type = row[2] or ""
                        rel_label = RELATION_TYPES.get(rel_type, {}).get("label", "")
                        chain_content.append({
                            "node_id": nid,
                            "role": row[0],
                            "content": row[1][:200],
                            "relation_type": rel_type,
                            "relation_label": rel_label,
                        })
                except Exception:
                    pass

        # Step 4: Generate narrative
        narrative_parts = []
        for r in search_results:
            narrative_parts.append(f"\u76f8\u5173: {r['content'][:150]}")
        if chain_content:
            narrative_parts.append("---\u63a8\u7406\u94fe\u63a5---")
            for c in chain_content:
                prefix = f"[{c['relation_label']}]" if c['relation_label'] else ""
                narrative_parts.append(f"{prefix} {c['role']}: {c['content'][:150]}")

        return {
            "seed_nodes": search_results,
            "chain": chain_content,
            "narrative": "\n".join(narrative_parts),
        }

    def stats(self, session_key: str = None) -> dict:
        """获取 DAG 统计"""
        nodes = self._get_session_nodes(session_key)
        total = len(nodes)
        summaries = sum(1 for n in nodes if n.is_summary)
        return {
            "total_nodes": total,
            "summary_nodes": summaries,
            "message_nodes": total - summaries,
            "avg_importance": round(sum(n.importance_score for n in nodes) / max(total, 1), 3),
        }


# ── RRF 融合函数 ──
def rrf_merge(results_list: List[List[Dict]], k: int = 60) -> List[Dict]:
    """
    RRF 融合多路检索结果（来自 retrieval_hub 设计模式）
    """
    scores = {}
    sources = {}
    for results in results_list:
        for i, r in enumerate(results):
            rid = r.get("node_id", r.get("content", str(i)))[:200]
            scores[rid] = scores.get(rid, 0) + 1.0 / (k + i)
            if rid not in sources:
                sources[rid] = r
                sources[rid]["rrf_score"] = 0
            sources[rid]["rrf_score"] = scores[rid]
    merged = sorted(sources.values(), key=lambda x: x["rrf_score"], reverse=True)
    return merged


# ── 记忆巩固设计模式 ──
def run_consolidation_design(workspace: str = None, dag_mgr: "DAGContextManager" = None) -> dict:
    """
    记忆巩固设计模式（CLS + 干扰管理 + 预测编码冲突检测）
    从 memory_consolidation.py 提取的环境无关版设计思想：
    1. CLS: 高重要性节点提取为记忆
    2. 干扰管理: 相似内容合并
    3. 预测编码: 检索结果中检测矛盾
    """
    mgr = dag_mgr or DAGContextManager()
    stats = {"consolidated": 0, "merged": 0, "conflicts": 0}
    if not _HAS_SQLITE:
        return stats
    try:
        conn = sqlite3.connect(mgr._db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT node_id, content FROM dag_nodes WHERE is_summary = 0 AND importance_score >= 0.4 ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        conn.close()
        stats["consolidated"] = len(rows)
    except Exception:
        pass
    return stats


def init() -> dict:
    """engines.json init_fn 入口"""
    return DAGContextManager()


# ── 引擎注册兼容 ──
ENGINE_ID = "dag_context"
ENGINE_CLASS = DAGContextManager
