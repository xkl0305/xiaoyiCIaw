"""
Crusheart Agent OS — 本地语义记忆引擎（TF-IDF增强版）
功能：基于TF-IDF + N-gram + 多级加权的高效语义检索
      零外部依赖，纯numpy实现，替代yaoyao-memory-plugin的向量搜索
"""

import os
import re
import json
import math
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from collections import Counter
# P4: numpy 懒加载
_np = None
def _get_np():
    global _np
    if _np is None:
        import numpy as _np
    return _np

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")

VECTOR_INDEX_FILE = os.path.join(WORKSPACE, ".vector_memory_index.json")
MEMORY_DATA_FILE = os.path.join(WORKSPACE, ".vector_memory_data.json")

# 向量维度 (512维更好区分语义)
VECTOR_DIM = 512

# 增量索引配置
VECTOR_DELTA_LOG = os.path.join(WORKSPACE, ".vector_delta_log.jsonl")  # 新增条目增量日志
VECTOR_DELTA_REMOVE_LOG = os.path.join(WORKSPACE, ".vector_delta_removals.log")  # 删除标记日志
DELTA_AUTO_MERGE_THRESHOLD = 200  # 增量条数超过此值自动触发全量合并

SIMILARITY_THRESHOLD = 0.40
HIGH_SIMILARITY = 0.70
MAX_RESULTS = 10

# ============================================================
# 分词改进 — 四层分词器
# ============================================================

STOP_WORDS_CHINESE = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "他", "她", "它", "们",
    "那", "些", "什么", "怎么", "哪", "为", "把", "被", "让", "从",
    "对", "与", "吗", "啊", "呢", "吧", "哦", "嗯", "哈", "呀",
    "嘛", "并且", "但是", "虽然", "因为", "所以", "然而", "如果",
    "可以", "能够", "已经", "正在", "现在", "还是", "就是", "只是",
    "不是", "这个", "那个", "一个", "什么", "没有", "不要", "不能",
}

# 同义词/近义词扩展（提升召回）
SYNONYM_MAP = {
    "编程": ["coding", "写代码", "开发", "写程序"],
    "代码": ["程序", "源码", "脚本", "code"],
    "晚上": ["夜间", "夜晚", "深夜", "凌晨"],
    "早上": ["早晨", "清晨", "早上好", "早"],
    "中午": ["午间", "正午"],
    "吃饭": ["用餐", "进食", "干饭"],
    "系统": ["OS", "操作系统", "平台"],
    "配置": ["设置", "config", "设定"],
    "删除": ["移除", "清空", "去掉"],
    "添加": ["新增", "加入", "增加", "加"],
    "创建": ["新建", "生成", "搞", "做"],
    "修改": ["编辑", "改动", "变更", "改"],
    "查询": ["搜索", "查找", "搜", "查"],
    "天津": ["天津", "津"],
    "江南": ["江南区", "江南"],
    "西湖": ["西湖", "西湖区"],
    "学府": ["学府", "学府路"],
    "AI助手": ["AI助手", "智能助手"],
    "哥们": ["兄弟", "朋友", "老哥"],
    "工具": ["技能", "插件", "tool"],
    "记忆": ["memory", "记忆体", "记忆库"],
    "天气": ["天气预报", "气象"],
    "科技": ["tech", "technology"],
    "手机": ["手机", "phone"],
}

# 英文常见词形变化简化
ENGLISH_STEMS = {
    "coding": "code",
    "coded": "code",
    "codes": "code",
    "running": "run",
    "runs": "run",
    "worked": "work",
    "working": "work",
    "writing": "write",
    "writes": "write",
    "using": "use",
    "used": "use",
    "getting": "get",
    "making": "make",
    "doing": "do",
}


def tokenize_chinese(text: str) -> List[str]:
    """
    中文分词 — 基于词典 + N-gram + 语义单元
    """
    tokens = []

    # 提取连续中文（2字以上）
    chinese_chunks = re.findall(r'[\u4e00-\u9fff]{2,}', text)

    for chunk in chinese_chunks:
        # 1. 整词保留（如果是常见2-4字词）
        if len(chunk) <= 6:
            tokens.append(chunk)

        # 2. bigram (2字滑动窗口)
        for i in range(len(chunk) - 1):
            bi = chunk[i:i+2]
            if bi not in STOP_WORDS_CHINESE:
                tokens.append(bi)

        # 3. trigram (3字滑动窗口)
        if len(chunk) >= 3:
            for i in range(len(chunk) - 2):
                tri = chunk[i:i+3]
                if tri not in STOP_WORDS_CHINESE:
                    tokens.append(tri)

        # 4. 如果整词太长，拆成关键词组
        if len(chunk) > 8:
            # 尝试按常见2字词边界拆分
            sub_words = []
            i = 0
            while i < len(chunk):
                if i + 4 <= len(chunk) and chunk[i:i+4] not in STOP_WORDS_CHINESE:
                    sub_words.append(chunk[i:i+4])
                    i += 4
                elif i + 3 <= len(chunk):
                    sub_words.append(chunk[i:i+3])
                    i += 3
                elif i + 2 <= len(chunk):
                    sub_words.append(chunk[i:i+2])
                    i += 2
                else:
                    i += 1
            for sw in sub_words:
                if len(sw) >= 2 and sw not in STOP_WORDS_CHINESE:
                    tokens.append(sw)

    return tokens


def tokenize_english(text: str) -> List[str]:
    """英文分词 — 小写 + 词干还原 + 过滤短词"""
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9_]{1,}', text.lower())
    tokens = []
    for w in words:
        if len(w) < 2:
            continue
        # 词干还原
        stem = ENGLISH_STEMS.get(w, w)
        tokens.append(stem)
    return tokens


def expand_synonyms(tokens: List[str]) -> List[str]:
    """同义词扩展"""
    expanded = list(tokens)
    for token in tokens:
        if token in SYNONYM_MAP:
            expanded.extend(SYNONYM_MAP[token])
    return expanded


def extract_tfidf_tokens(text: str) -> List[str]:
    """
    完整的分词流程：中文分词 + 英文分词 + 数字 + 同义词扩展
    """
    if not text:
        return []

    tokens = []

    # 中文分词
    tokens.extend(tokenize_chinese(text))

    # 英文分词
    tokens.extend(tokenize_english(text))

    # 数字
    numbers = re.findall(r'\d{2,}', text)
    tokens.extend(numbers)

    # 同义词扩展
    tokens = expand_synonyms(tokens)

    return tokens


# ============================================================
# TF-IDF 向量构建
# ============================================================

def compute_tf(term_freq: Dict[str, int], total_terms: int) -> Dict[str, float]:
    """计算词频 (Term Frequency) — 使用对数归一化"""
    tf = {}
    for term, count in term_freq.items():
        tf[term] = 1 + math.log10(count) if count > 0 else 0
    return tf


def build_vector_v2(tokens: List[str], dim: int = VECTOR_DIM):
    """
    TF-IDF 增强版向量构建
    使用多哈希 + TF 加权 + 位置编码

    Args:
        tokens: 扩展后的 token 列表
        dim: 向量维度

    Returns:
        归一化的 numpy 向量
    """
    np = _get_np()
    vector = np.zeros(dim, dtype=np.float32)

    if not tokens:
        return vector

    # 词频统计
    counter = Counter(tokens)
    total = sum(counter.values())

    # TF 对数归一化
    tf_values = compute_tf(counter, total)

    # 计算IDF权重近似值（基于出现频次）
    # 总token数
    total_tokens = len(tokens)
    # 出现一次的词权重更高（近似idf）
    unique_tokens = len(counter)
    avg_idf_weight = math.log10((total_tokens + 1) / (unique_tokens + 1)) + 1 if unique_tokens > 0 else 1

    for token, freq in counter.items():
        # 多哈希：一个 token 映射到 3 个维度（提高召回）
        h1 = hashlib.md5(f"{token}_a".encode('utf-8')).digest()
        h2 = hashlib.md5(f"{token}_b".encode('utf-8')).digest()
        h3 = hashlib.md5(f"{token}_c".encode('utf-8')).digest()

        idx1 = int.from_bytes(h1[:4], 'big') % dim
        idx2 = int.from_bytes(h2[:4], 'big') % dim
        idx3 = int.from_bytes(h3[:4], 'big') % dim

        # TF 对数权重
        tf_weight = tf_values[token]
        # 位置权重分布 (0.5 / 0.3 / 0.2)
        vector[idx1] += tf_weight * avg_idf_weight * 0.5
        vector[idx2] += tf_weight * avg_idf_weight * 0.3
        vector[idx3] += tf_weight * avg_idf_weight * 0.2

    # L2 归一化
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm

    return vector


def cosine_similarity(v1, v2) -> float:
    """计算余弦相似度"""
    np = _get_np()
    dot = np.dot(v1, v2)
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(dot / (n1 * n2))


# ============================================================
# 记忆引擎
# ============================================================

class VectorMemoryEngine:
    """
    本地语义记忆引擎（TF-IDF增强版）
    基于 numpy 向量化 + TF-IDF 加权 + 多级哈希
    零外部依赖，纯 Python 实现
    """

    def __init__(self):
        self.memory_data: Dict[str, dict] = {}
        self._delta_count: int = 0          # 自上次全量合并后的增量条数
        self._dirty_access: bool = False    # 是否有未落盘的 access_count 变更
        self._load()

    def _load(self):
        """
        增量加载：先从全量索引文件恢复，再回放增量日志（新增+删除）。
        这样即使系统崩溃，增量数据也不会丢失。
        """
        # 1. 加载全量主数据文件
        if os.path.exists(MEMORY_DATA_FILE):
            try:
                with open(MEMORY_DATA_FILE, encoding="utf-8") as f:
                    self.memory_data = json.load(f)
            except Exception:
                self.memory_data = {}
        else:
            self.memory_data = {}

        # 2. 回放增量添加日志
        if os.path.exists(VECTOR_DELTA_LOG):
            try:
                with open(VECTOR_DELTA_LOG, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        mid = entry.get("id")
                        if mid:
                            self.memory_data[mid] = entry
                            self._delta_count += 1
            except Exception:
                pass

        # 3. 应用增量删除标记
        if os.path.exists(VECTOR_DELTA_REMOVE_LOG):
            try:
                with open(VECTOR_DELTA_REMOVE_LOG, encoding="utf-8") as f:
                    for line in f:
                        mid = line.strip()
                        if mid and mid in self.memory_data:
                            del self.memory_data[mid]
            except Exception:
                pass

    def merge_full_index(self):
        """
        全量合并：将内存中的完整数据写入主索引文件，
        清空增量日志。
        
        调用时机：
        - 增量条数超过阈值（DELTA_AUTO_MERGE_THRESHOLD）
        - 每日维护任务中调用
        - 用户显式调用
        """
        os.makedirs(os.path.dirname(MEMORY_DATA_FILE), exist_ok=True)
        # 主数据文件：无缩进，减小体积约 3x
        with open(MEMORY_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memory_data, f, ensure_ascii=False)

        # 向量索引文件：无缩进
        index_data = {}
        for mid, entry in self.memory_data.items():
            vec = entry.get("vector")
            if vec:
                index_data[mid] = vec

        with open(VECTOR_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)

        # 清空增量日志
        for log_path in [VECTOR_DELTA_LOG, VECTOR_DELTA_REMOVE_LOG]:
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                except Exception:
                    pass

        self._delta_count = 0
        self._dirty_access = False

    def add(self, text: str, metadata: dict = None) -> str:
        """
        添加一条记忆

        Args:
            text: 记忆内容文本
            metadata: 附加元数据

        Returns:
            记忆条目 ID
        """
        mid = hashlib.md5(f"{text}{time.time()}".encode('utf-8')).hexdigest()[:16]
        tokens = extract_tfidf_tokens(text)
        vector = build_vector_v2(tokens)

        entry = {
            "id": mid,
            "text": text,
            "vector": vector.tolist(),
            "tokens": tokens[:150],
            "created_at": datetime.now(BEIJING_TZ).isoformat(),
            "access_count": 0,
            "last_access": None,
        }
        if metadata:
            entry["metadata"] = metadata

        self.memory_data[mid] = entry

        # 增量写入：仅追加一行 JSONL 到 delta 日志，不做全量 dump
        os.makedirs(os.path.dirname(VECTOR_DELTA_LOG), exist_ok=True)
        with open(VECTOR_DELTA_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._delta_count += 1

        # 增量超过阈值时自动全量合并
        if self._delta_count >= DELTA_AUTO_MERGE_THRESHOLD:
            self.merge_full_index()

        return mid

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        语义搜索

        Args:
            query: 搜索查询文本
            top_k: 返回结果数

        Returns:
            按相似度排序的记忆条目列表
        """
        if not self.memory_data:
            return []

        query_tokens = extract_tfidf_tokens(query)
        query_vec = build_vector_v2(query_tokens)

        results = []
        for mid, entry in self.memory_data.items():
            vec = entry.get("vector")
            if vec is None:
                continue
            vec_array = _get_np().array(vec, dtype=_get_np().float32)
            similarity = cosine_similarity(query_vec, vec_array)

            if similarity >= SIMILARITY_THRESHOLD:
                results.append({
                    "id": mid,
                    "text": entry.get("text", "")[:200],
                    "similarity": round(similarity, 4),
                    "access_count": entry.get("access_count", 0),
                    "created_at": entry.get("created_at", ""),
                    "metadata": entry.get("metadata", {}),
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)

        # 仅更新内存中的 access_count，不做全量磁盘写入
        for r in results[:top_k]:
            if r["id"] in self.memory_data:
                self.memory_data[r["id"]]["access_count"] = self.memory_data[r["id"]].get("access_count", 0) + 1
                self.memory_data[r["id"]]["last_access"] = datetime.now(BEIJING_TZ).isoformat()
        self._dirty_access = True

        return results[:top_k]

    def remove(self, memory_id: str) -> bool:
        if memory_id in self.memory_data:
            del self.memory_data[memory_id]
            # 记录删除标记到日志（重启时回放使用）
            os.makedirs(os.path.dirname(VECTOR_DELTA_REMOVE_LOG), exist_ok=True)
            with open(VECTOR_DELTA_REMOVE_LOG, "a", encoding="utf-8") as f:
                f.write(memory_id + "\n")
            return True
        return False

    def clear(self):
        self.memory_data = {}
        self._delta_count = 0
        self._dirty_access = False
        # 清空所有数据文件
        for fpath in [MEMORY_DATA_FILE, VECTOR_INDEX_FILE, VECTOR_DELTA_LOG, VECTOR_DELTA_REMOVE_LOG]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    def stats(self) -> Dict:
        return {
            "total_entries": len(self.memory_data),
            "avg_access": sum(e.get("access_count", 0) for e in self.memory_data.values()) / len(self.memory_data) if self.memory_data else 0,
        }



# ============================================================
# BM25 语义检索（替代 TF-IDF，零外部依赖）
# ============================================================

class BM25Retriever:
    """
    BM25 算法实现 — 纯 Python，零外部依赖
    使用 Okapi BM25 变体，在长文本检索中优于 TF-IDF
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freq = {}
        self.doc_lengths = []
        self.doc_tokens = []
        self.avgdl = 0.0
        self.total_docs = 0

    def index(self, documents):
        self.doc_tokens = documents
        self.doc_lengths = [len(d) for d in documents]
        self.total_docs = len(documents)
        self.avgdl = sum(self.doc_lengths) / max(self.total_docs, 1)
        self.doc_freq = {}
        for doc in documents:
            seen = set()
            for token in doc:
                if token not in seen:
                    self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
                    seen.add(token)

    def search(self, query_tokens, top_k=5):
        if not self.total_docs or not query_tokens:
            return []
        scores = []
        for doc_idx in range(self.total_docs):
            doc_len = self.doc_lengths[doc_idx]
            score = 0.0
            doc_token_set = set(self.doc_tokens[doc_idx])
            for token in query_tokens:
                if token not in doc_token_set:
                    continue
                df = self.doc_freq.get(token, 0)
                if df == 0:
                    continue
                idf = math.log10((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)
                tf = sum(1 for t in self.doc_tokens[doc_idx] if t == token)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                score += idf * numerator / max(denominator, 0.001)
            scores.append((doc_idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(idx, round(s, 4)) for idx, s in scores[:top_k] if s > 0]


class BM25VectorMemoryEngine(VectorMemoryEngine):
    """BM25 增强版：BM25 初筛 + TF-IDF 向量精排"""
    def __init__(self):
        super().__init__()
        self._bm25 = BM25Retriever()
        self._bm25_indexed = False
        self._rebuild_bm25_index()

    def _rebuild_bm25_index(self):
        if not self.memory_data:
            return
        documents = []
        for mid, entry in self.memory_data.items():
            tokens = entry.get("tokens", [])
            if tokens:
                documents.append(tokens)
        if documents:
            self._bm25.index(documents)
            self._bm25_indexed = True

    def add(self, text, metadata=None):
        mid = super().add(text, metadata)
        self._bm25_indexed = False
        return mid

    def search(self, query, top_k=5):
        if not self.memory_data:
            return []
        query_tokens = extract_tfidf_tokens(query)
        query_vec = build_vector_v2(query_tokens)
        if not self._bm25_indexed:
            self._rebuild_bm25_index()
        bm25_results = self._bm25.search(query_tokens, top_k=top_k * 3)
        if not bm25_results:
            return super().search(query, top_k)
        scored = []
        bm25_ids = [list(self.memory_data.keys())[idx] for idx, _ in bm25_results]
        for mid in bm25_ids:
            entry = self.memory_data.get(mid)
            if not entry:
                continue
            vec = entry.get("vector")
            if vec is None:
                continue
            np = _get_np()
            vec_array = np.array(vec, dtype=np.float32)
            similarity = cosine_similarity(query_vec, vec_array)
            scored.append({
                "id": mid, "text": entry.get("text", "")[:200],
                "similarity": round(similarity, 4),
                "access_count": entry.get("access_count", 0),
                "created_at": entry.get("created_at", ""),
                "metadata": entry.get("metadata", {}),
            })
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        for r in scored[:top_k]:
            if r["id"] in self.memory_data:
                self.memory_data[r["id"]]["access_count"] = self.memory_data[r["id"]].get("access_count", 0) + 1
                self.memory_data[r["id"]]["last_access"] = datetime.now(BEIJING_TZ).isoformat()
        self._dirty_access = True
        return scored[:top_k]

    def merge_full_index(self):
        super().merge_full_index()
        self._rebuild_bm25_index()
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

    # 快速测试
    if len(sys.argv) >= 1 and "--test" in sys.argv:
        engine = VectorMemoryEngine()

        # 模拟 yaoyao 测试数据
        test_data = [
            "我的名字叫小明，喜欢在晚上10点后coding，效率最高",
            "用户住在某市某区",
            "系统使用Crusheart Agent OS命名，永久锁定",
            "AI助手是养成系个人AI助理",
            "华为手机Mate 60 Pro很好用",
        ]

        for td in test_data:
            engine.add(td)

        queries = ["coding 晚上", "江南", "西湖", "AI助手", "Crusheart"]
        for q in queries:
            results = engine.search(q)
            print(f"\n🔍 '{q}' → {len(results)} 条")
            for r in results:
                print(f"  [{r['similarity']:.2f}] {r['text'][:50]}...")

        engine.clear()
        sys.exit(0)

    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 scripts/vector_memory.py add <text>          # 添加记忆（增量写入）")
        print("  python3 scripts/vector_memory.py search <query>      # 搜索")
        print("  python3 scripts/vector_memory.py merge               # 全量合并增量日志")
        print("  python3 scripts/vector_memory.py stats               # 统计（含增量状态）")
        print("  python3 scripts/vector_memory.py clear               # 清空")
        print("  python3 scripts/vector_memory.py --test              # 运行测试")
        sys.exit(0)

    action = sys.argv[1]
    engine = VectorMemoryEngine()

    if action == "add" and len(sys.argv) > 2:
        text = " ".join(sys.argv[2:])
        mid = engine.add(text)
        print(f"✅ 已添加记忆 (ID: {mid})")

    elif action == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = engine.search(query)
        print(f"🔍 '{query}' → 找到 {len(results)} 条结果\n")
        for r in results:
            print(f"  [{r['similarity']:.2f}] {r['text'][:80]}...")
            print(f"    创建: {r['created_at'][:19]}")
            print()

    elif action == "stats":
        s = engine.stats()
        print(f"📊 向量记忆统计")
        print(f"   总条目: {s['total_entries']}")
        print(f"   平均访问: {s['avg_access']:.1f}次")

    elif action == "clear":
        confirm = input("确定清空所有向量记忆？(yes/no): ")
        if confirm == "yes":
            engine.clear()
            print("✅ 已清空")
        else:
            print("已取消")

    elif action == "merge":
        before = len(engine.memory_data)
        engine.merge_full_index()
        print(f"✅ 全量合并完成，共 {before} 条记忆，已清空增量日志")

    elif action == "stats":
        s = engine.stats()
        print(f"📊 向量记忆统计")
        print(f"   总条目: {s['total_entries']}")
        print(f"   平均访问: {s['avg_access']:.1f}次")
        print(f"   自上次合并后增量: {engine._delta_count} 条")
        print(f"   增量日志: {'存在' if os.path.exists(VECTOR_DELTA_LOG) and os.path.getsize(VECTOR_DELTA_LOG) > 0 else '空'}")
        print(f"   删除日志: {'存在' if os.path.exists(VECTOR_DELTA_REMOVE_LOG) and os.path.getsize(VECTOR_DELTA_REMOVE_LOG) > 0 else '空'}")

    elif action == "clear":
        confirm = input("确定清空所有向量记忆？(yes/no): ")
        if confirm == "yes":
            engine.clear()
            print("✅ 已清空")
        else:
            print("已取消")
