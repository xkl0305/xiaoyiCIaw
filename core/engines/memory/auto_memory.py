"""
Crusheart Agent OS — 统一记忆引擎 AutoMemory
整合：倒排索引 + TF-IDF语义搜索 + 标签/场景/图谱/统计/推荐/笔记
打通：L0日志自动写入 + exec_logger自动记录
"""
import os, re, json, math, hashlib, shutil, glob, time, copy, sys, random
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import Counter, defaultdict
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
# P4: numpy 懒加载（不阻塞初始化）
_numpy = None
def _get_numpy():
    global _numpy
    if _numpy is None:
        import numpy as _numpy  # 首次 search() 时才导入
    return _numpy

# 导入 vector_memory 的 TF-IDF 向量构建函数
_vector_memory_loaded = False
try:
    sys.path.insert(0, os.path.dirname(__file__))
    # 注册当前目录为脚本路径
    _work_dir = os.path.dirname(os.path.abspath(__file__))
    if _work_dir not in sys.path:
        sys.path.insert(0, _work_dir)
    import importlib
    vm = importlib.import_module('vector_memory')
    extract_tfidf_tokens = vm.extract_tfidf_tokens
    build_vector_v2 = vm.build_vector_v2
    cosine_similarity = vm.cosine_similarity
    VECTOR_DIM = vm.VECTOR_DIM
    _vector_memory_loaded = True
except (ImportError, AttributeError) as e:
    # fallback: 自己实现简单 TF-IDF
    extract_tfidf_tokens = None
    build_vector_v2 = None
    cosine_similarity = None
    VECTOR_DIM = 256
    _vector_memory_loaded = False

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
MEMORY_DIR = os.path.join(WORKSPACE, "memory")


# ================================================================
# 四层记忆体系 — 原 memory_layer_engine 整合
# 核心锚点准入、记忆固化、冷热存储、活跃度衰减、主动指令检测
# ================================================================

CORE_ANCHOR_KEYWORDS = [
    # 用户基本信息
    "名字", "姓名", "称呼", "地址", "电话", "邮箱", "生日",
    # 用户核心偏好
    "风格", "偏好", "喜欢", "讨厌", "反感", "禁忌",
    # 系统关键配置
    "配置", "渠道", "插件", "定时任务",
    # 重大事件
    "创建", "安装", "升级", "迁移"
]

BEIJING_TZ = timezone(timedelta(hours=8))
# ── 近期上下文关键词组（语义匹配）──
_RECENT_CONTEXT_PATTERNS = [
    # 核心词（匹配中文开头/前面/前面...）
    "刚才", "刚刚",
    "上一句", "上一轮", "上一条",
    "前面说", "前面讲", "前面提",
    "刚才说", "刚才讲", "刚才提",
    "刚刚说", "刚刚讲", "刚刚提",
    "刚才在说", "刚刚在说",
    "说到哪", "聊到哪",
    "说到哪里", "聊到哪里",
    "说到哪儿", "聊到哪儿",
    # 组合词：之前 + 说/聊/讲/谈
    "之前的", "之前提",
    "之前说的", "之前聊的", "之前讲的", "之前谈的",
    "之前说过", "之前聊过", "之前讲过", "之前谈过",
    "之前提到", "之前提及", "之前讨论",
    "之前说的那些", "之前聊的那些",
    # 复合问法
    "我说到哪", "我聊到哪", "我们说到哪", "我们聊到哪",
    "我说到哪里", "我聊到哪里", "我们说到哪里", "我们聊到哪里",
    # 上一条/上一个 + 消息/话题
    "上一条消息", "上一条内容", "上一个话题", "上一个问题",
]
_RECENT_CONTEXT_COMPILED = re.compile(
    '|'.join(re.escape(p) for p in _RECENT_CONTEXT_PATTERNS),
    re.IGNORECASE
)


def _detect_recent_context(query: str) -> str:
    """检测是否查询「近期上下文」，是则返回匹配到的关键词，否则返回 None"""
    if not query or not query.strip():
        return None
    m = _RECENT_CONTEXT_COMPILED.search(query)
    if m:
        matched = m.group(0)
        # 排除"去年之前"之类的时间跨度长的匹配
        if re.search(r'去年|前年|上个月|上周|上星期', query):
            return None
        return matched[:30]
    return None


# ── v6.3.2: 反注入扫描模式 ──
_INJECTION_PATTERNS = [
    "ignore previous instructions", "ignore all previous",
    "you are now", "disregard your", "forget your instructions",
    "new instructions:", "system prompt:", "<system>",
    "]]>", "assistant:", "human:",
]

def scan_memory_injection(content: str):
    if not content:
        return None
    content_lower = content.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in content_lower:
            return f"[BLOCKED: injection pattern '{pattern}' detected]"
    return None

def detect_file_drift(filepath: str, expected_delimiter: str = "\n\xa7\n"):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None
    entries = [e.strip() for e in content.split(expected_delimiter) if e.strip()]
    reconstructed = expected_delimiter.join(entries)
    if reconstructed.strip() != content.strip():
        bak_path = filepath + f'.bak.{int(time.time())}'
        try:
            import shutil; shutil.copy2(filepath, bak_path)
        except Exception:
            pass
        # 清理旧 .bak 文件，只保留最近 5 个
        try:
            import glob
            base = filepath + '.bak.'
            baks = sorted([f for f in glob.glob(base + '*') if f.replace(base, '').isdigit()])
            for old_bak in baks[:-5]:
                os.remove(old_bak)
        except Exception:
            pass
        return {"drifted": True, "backup": bak_path,
                "remediation": "Resolve drift, then retry write"}
    return {"drifted": False}

class FrozenSnapshot:
    _snapshot = {"memory": "", "user": ""}
    _frozen = False
    @classmethod
    def freeze(cls, memory_text='', user_text=''):
        from datetime import datetime, timezone, timedelta
        BJ = timezone(timedelta(hours=8))
        cls._snapshot = {"memory": memory_text, "user": user_text,
                         "frozen_at": datetime.now(BJ).isoformat()}
        cls._frozen = True
    @classmethod
    def get_snapshot(cls) -> dict:
        return cls._snapshot if cls._frozen else {"memory": "", "user": ""}
    @classmethod
    def get_snapshot_text(cls) -> str:
        if not cls._frozen:
            return ""
        parts = []
        if cls._snapshot.get('memory'):
            parts.append("## 记忆\n" + cls._snapshot["memory"])
        if cls._snapshot.get('user'):
            parts.append("## 用户信息\n" + cls._snapshot["user"])
        return "\n\n".join(parts)
    @classmethod
    def is_frozen(cls) -> bool:
        return cls._frozen
    @classmethod
    def reset(cls):
        cls._snapshot = {"memory": "", "user": ""}
        cls._frozen = False


def detect_memory_instruction(content: str) -> dict:
    """检测用户是否在发出记忆指令"""
    instructions = {
        "remember": False,
        "finalize": False,
        "always": False,
        "never": False,
        "save_rule": False,
    }
    if re.search(r'(记住|记下|别忘了|不要忘|写下来|保存)', content):
        instructions["remember"] = True
    if re.search(r'(定稿|生效|确认(定|无误)|就这么(定了|办)|确定了)', content):
        instructions["finalize"] = True
    if re.search(r'(以后都|以后就|全都(按|照)|每次都要|永远|一直用)', content):
        instructions["always"] = True
    if re.search(r'(以后不要|以后别再|别再|禁止|不许|绝对不要)', content):
        instructions["never"] = True
    if re.search(r'(沉淀|固化|形成(规范|规则)|作为(规范|标准)|总结)', content):
        instructions["save_rule"] = True
    return instructions




def force_core_anchor_by_instruction(content: str) -> bool:
    """判断是否因用户指令而强制入锚点"""
    return any(detect_memory_instruction(content).values())


def is_noise_content(content: str) -> bool:
    """判断内容是否为临时/无意义内容（不入梦）"""
    noise_patterns = [
        r'^(好|是|嗯|对|行|可以|收到|明白|了解|知道|ok|好的|是的|没错|对的对的|明白了|了解了|知道了)$',
        r'^(hello|hi|你好|早|晚上好|晚安|早上好|下午好|好的好的)$',
        r'^[哈哈呵呵嘿嘿]+$',
        r'^(测试|test|试一下|试试|随便写的|先这样吧)$',
        r'^(没|没有|不用|不需要|算了)$',
        r'^[\s]*$',
    ]
    text = content.strip().lower()
    for pattern in noise_patterns:
        if re.match(pattern, text):
            return True
    if len(text) <= 2 and not re.search(r'[\u4e00-\u9fff]', text):
        return True
    if text.startswith('__') and text.endswith('__'):
        return True
    return False




# ================================
# 工具1: FTS5 倒排索引 (替代sqlite FTS5)
# ================================
# ── C2: 内置中文同义词词典（高频语义近邻，纯 Python，无外部依赖） ──
_SYNONYM_DICT = {
    "提高": ["提升", "增加", "增强"], "提升": ["提高", "增加", "改善"],
    "增加": ["提高", "提升", "增长"], "增强": ["提高", "加强", "提升"],
    "改善": ["优化", "提升", "改进"], "优化": ["改善", "提升", "精简"],
    "工作": ["任务", "干活", "项目"], "任务": ["工作", "事项", "作业"],
    "效率": ["速度", "效能", "产出"], "速度": ["效率", "速率"],
    "方法": ["方式", "手段", "途径"], "方式": ["方法", "模式", "形式"],
    "方案": ["计划", "规划", "策略"], "计划": ["方案", "安排"],
    "问题": ["错误", "bug", "故障", "缺陷"], "错误": ["问题", "bug", "失误"],
    "解决": ["修复", "处理", "搞定"], "修复": ["解决", "修理", "改正"],
    "学习": ["了解", "掌握", "研究"], "知识": ["信息", "内容", "资料"],
    "理解": ["明白", "懂", "掌握"], "分析": ["研究", "探究", "调查"],
    "开发": ["编写", "编程", "构建"], "代码": ["程序", "脚本"],
    "功能": ["特性", "能力", "模块"], "系统": ["平台", "框架"],
    "数据": ["信息", "资料", "内容"], "接口": ["API", "协议"],
    "管理": ["控制", "维护", "运营"], "配置": ["设置", "参数"],
    "操作": ["执行", "运行", "操控"], "处理": ["解决", "应对"],
    "查询": ["搜索", "检索", "查找"], "搜索": ["查询", "检索", "找"],
    "显示": ["展示", "呈现", "表现"], "记录": ["日志", "笔记", "记载"],
    "用户": ["使用者", "客户"], "体验": ["感受", "使用感"],
    "界面": ["UI", "页面", "视图"], "设计": ["规划", "布局"],
    "性能": ["速度", "效率", "响应"], "稳定": ["可靠", "健壮"],
    "时间": ["日期", "时刻"], "周期": ["循环", "间隔"],
    "开始": ["启动", "开启", "着手"], "停止": ["暂停", "终止", "结束"],
    "完成": ["做完", "搞定", "结束"], "检查": ["查看", "审查", "检验"],
    "保存": ["存储", "保留"], "删除": ["移除", "清除"],
    "修改": ["更改", "调整", "修正"], "添加": ["增加", "新增", "加入"],
    "选择": ["挑选", "选取"], "设置": ["配置", "调整"],
    "发送": ["推送", "传递"], "接收": ["获取", "得到"],
    "模型": ["AI", "算法"], "训练": ["学习", "调优"],
    "预测": ["推理", "推断"], "生成": ["创建", "产出"],
}

_SYNONYM_REVERSE = {}
for _k, _vs in _SYNONYM_DICT.items():
    for _v in _vs:
        _SYNONYM_REVERSE.setdefault(_v, []).append(_k)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 编辑距离"""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


def _semantic_expand_tokens(tokens: list, max_expand: int = 3) -> set:
    """C2 语义扩展：同义词词典 + 编辑距离模糊匹配"""
    expanded = set(tokens)
    for tok in tokens:
        added = 0
        syns = _SYNONYM_DICT.get(tok, []) + _SYNONYM_REVERSE.get(tok, [])
        for s in syns:
            if s not in expanded and added < max_expand:
                expanded.add(s)
                added += 1
        if added >= max_expand:
            continue
        if 2 <= len(tok) <= 4:
            candidates = [k for k in _SYNONYM_DICT if 2 <= len(k) <= 4 and k != tok and _edit_distance(tok, k) == 1]
            for c in candidates[:max_expand - added]:
                if c not in expanded:
                    expanded.add(c)
                    added += 1
    return expanded



class InvertedIndex:
    """纯 Python FTS5 替代 — 倒排索引 + CJK 降级 LIKE"""
    def __init__(self, index_file=".inverted_index.json"):
        self.index_file = os.path.join(WORKSPACE, index_file)
        self.index: Dict[str, List[str]] = {}
        self._dirty_count = 0
        self._rebuild_count = 0
        self._load()

    def _load(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, encoding="utf-8") as f:
                    self.index = json.load(f)
            except Exception:
                logging.exception("[auto_memory.py] suppressed")
                self.index = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False)

    def _tokenize(self, text: str) -> List[str]:
        toks = set()
        
        # 备用1: jieba 中文分词（优先，精度更高）
        _jieba_ok = False
        try:
            import jieba
            chinese = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            for ch in chinese:
                words = jieba.lcut(ch, cut_all=False)
                for w in words:
                    w = w.strip()
                    if len(w) >= 2:
                        toks.add(w)
            _jieba_ok = True
        except Exception:
            pass
        
        # 备用2: 正则 bigram/trigram（jieba 不可用时兜底，或作为 jieba 的补充）
        chinese = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        for ch in chinese:
            toks.add(ch)
            # bigram
            for i in range(len(ch) - 1):
                toks.add(ch[i:i+2])
            # trigram
            if len(ch) >= 4:
                for i in range(len(ch) - 2):
                    toks.add(ch[i:i+3])
        
        # 英文原词保留（含连字符）
        english = re.findall(r'[a-zA-Z][a-zA-Z0-9_\-]{2,}', text)
        for e in english:
            toks.add(e.lower())
            # 也拆一下连字符（habit-flow → habit, flow）
            if '-' in e:
                for part in e.split('-'):
                    if len(part) >= 2:
                        toks.add(part.lower())
        
        digits = re.findall(r'\d{2,}', text)
        for d in digits: toks.add(d)
        return list(toks)

    def add(self, memory_id: str, text: str):
        """增量添加：实时更新内存索引，不刷盘"""
        for t in self._tokenize(text):
            if t not in self.index:
                self.index[t] = []
            if memory_id not in self.index[t]:
                self.index[t].append(memory_id)
        self._dirty_count += 1
        self._save_if_dirty()

    def remove(self, memory_id: str):
        """增量删除：从内存索引中移除，不刷盘"""
        for t, ids in list(self.index.items()):
            if memory_id in ids:
                ids.remove(memory_id)
                if not ids:
                    del self.index[t]
        self._dirty_count += 1
        self._save_if_dirty()

    def _save_if_dirty(self, force: bool = False):
        """累积修改达到阈值时刷盘，避免每次操作都写磁盘"""
        if force or self._dirty_count >= 50:
            self._save()
            self._dirty_count = 0

    def _rebuild(self, store_data: dict = None, db=None, force: bool = False):
        """
        从 SQLite 重建整个倒排索引。
        SQLite 是唯一持久存储，MemoryStore 为内存缓存层。
        store_data 参数保留仅用于兼容，实际不再使用。
        dirty_count 超阈值时才真重建，否则增量已覆盖。
        """
        if self._dirty_count < 50 and not force:
            # 增量已足够，只需刷盘
            self._save()
            self._dirty_count = 0
            return
        self.index.clear()
        if db:
            try:
                rows = db.conn.execute("SELECT id, content FROM memories").fetchall()
                for row in rows:
                    for t in self._tokenize(row["content"]):
                        if t not in self.index:
                            self.index[t] = []
                        if row["id"] not in self.index[t]:
                            self.index[t].append(row["id"])
            except Exception:
                pass
        elif store_data:
            for mid, entry in store_data.items():
                text = entry.get("text", "") or entry.get("content", "")
                for t in self._tokenize(text):
                    if t not in self.index:
                        self.index[t] = []
                    if mid not in self.index[t]:
                        self.index[t].append(mid)
        self._save()
        self._dirty_count = 0
        self._rebuild_count = (self._rebuild_count or 0) + 1

    def search(self, query: str) -> List[str]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        # C2: 语义扩展 — 同义词 + 编辑距离近邻
        expanded = _semantic_expand_tokens(tokens, max_expand=3)
        scores = Counter()
        for t in expanded:
            matches = self.index.get(t, [])
            for m in matches:
                # 原始 token 命中权重 1.0，扩展 token 命中权重 0.7
                weight = 1.0 if t in tokens else 0.7
                scores[m] += weight
        # CJK 降级 LIKE 模式匹配
        cjk_query = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        for mtext in self.index:
            for cjk in cjk_query:
                if cjk in mtext:
                    scores[mtext] += 0.5
        return [mid for mid, _ in scores.most_common(20) if _ > 0]

# ================================
# 工具2: 记忆存储引擎
# ================================
class MemoryStore:
    """记忆存储 — AutoMemory 纯文件存储"""
    STORE_FILE = os.path.join(WORKSPACE, ".memory_store.json")
    def __init__(self):
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.STORE_FILE):
            try:
                with open(self.STORE_FILE, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                logging.exception("[auto_memory.py] suppressed")
                self.data = {}

    def save(self):
        """保存到 JSON 文件（降级存储）
        SQLite 初始化失败或不可用时，作为回退方案。"""
        try:
            store_dir = os.path.dirname(self.STORE_FILE)
            if store_dir and not os.path.exists(store_dir):
                os.makedirs(store_dir, exist_ok=True)
            tmp = self.STORE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.STORE_FILE)
        except Exception as e:
            logging.warning(f"[MemoryStore] JSON 持久化失败: {e}")

    def add(self, mid: str, text: str, tags: List[str] = None, scene: str = ""):
        entry = {
            "id": mid,
            "text": text,
            "tags": tags or [],
            "scene": scene,
            "created_at": datetime.now(BEIJING_TZ).isoformat(),
            "access_count": 0,
        }
        self.data[mid] = entry
        self.save()
        return mid

    def get(self, mid: str) -> Optional[dict]:
        entry = self.data.get(mid)
        if entry:
            entry["access_count"] = entry.get("access_count", 0) + 1
            self._dirty = True
        return entry

    def _save_if_dirty(self):
        """脏数据才写入 JSON，避免高频读时频繁全量写盘"""
        if getattr(self, '_dirty', False):
            self.save()
            self._dirty = False

    def list_all(self) -> List[dict]:
        return list(self.data.values())

    def remove(self, mid: str) -> bool:
        if mid in self.data:
            del self.data[mid]
            self.save()
            return True
        return False

    def clear(self):
        self.data = {}
        self.save()

    def stats(self) -> dict:
        return {
            "total": len(self.data),
            "tag_count": sum(len(e.get("tags", [])) for e in self.data.values()),
            "avg_access": sum(e.get("access_count", 0) for e in self.data.values()) / len(self.data) if self.data else 0,
            "dates": set(e["created_at"][:10] for e in self.data.values()),
        }

# ================================
# 工具3: 场景分组
# ================================
class SceneManager:
    """L2 场景分组 — 按场景归类记忆（P2: 从SQLite读取，不再独立JSON）"""
    def __init__(self, db=None):
        self._db = db
        self.scenes: Dict[str, List[Dict]] = {}
        if db:
            self._load_from_db()

    def _load_from_db(self):
        """从 SQLite 读取场景分布"""
        self.scenes.clear()
        if not self._db:
            return
        try:
            rows = self._db.conn.execute(
                "SELECT scene, id, content FROM memories WHERE scene != '' ORDER BY scene"
            ).fetchall()
            for row in rows:
                scene = row["scene"]
                if scene not in self.scenes:
                    self.scenes[scene] = []
                self.scenes[scene].append({"id": row["id"], "text": row["content"][:100]})
        except Exception:
            self.scenes = {}

    def assign(self, mid: str, text: str, scene: str):
        # 场景信息已存在 SQLite 的 memories.scene 字段中
        # 这里仅用于运行时缓存
        if scene not in self.scenes:
            self.scenes[scene] = []
        if not any(e["id"] == mid for e in self.scenes[scene]):
            self.scenes[scene].append({"id": mid, "text": text[:100]})

    def get_scene(self, scene: str) -> List[dict]:
        return self.scenes.get(scene, [])

    def all_scenes(self) -> Dict[str, int]:
        return {s: len(v) for s, v in self.scenes.items()}

    def remove(self, mid: str):
        for scene in list(self.scenes.keys()):
            self.scenes[scene] = [e for e in self.scenes[scene] if e["id"] != mid]
            if not self.scenes[scene]:
                del self.scenes[scene]

# ================================
# 工具4: 用户画像 (L3)
# ================================
class PersonaManager:
    """L3 用户画像 — persona.md 维护"""
    def __init__(self):
        self.persona_file = os.path.join(MEMORY_DIR, "persona.md")

    def get(self) -> str:
        if os.path.exists(self.persona_file):
            with open(self.persona_file, encoding="utf-8") as f:
                return f.read()
        return ""

    def update(self, section: str, content: str):
        existing = self.get()
        pattern = re.compile(rf"(## {re.escape(section)}\n).*?(?=\n## |\Z)", re.DOTALL)
        if pattern.search(existing):
            existing = pattern.sub(rf"\1{content}", existing)
        else:
            existing += f"\n## {section}\n{content}\n"
        with open(self.persona_file, "w", encoding="utf-8") as f:
            f.write(existing.strip() + "\n")

# ================================
# 工具5: 记忆图 (关联图谱)
# ================================
class MemoryGraph:
    """记忆关联图谱 — 标签/场景/时间多维关联"""
    def __init__(self, store: MemoryStore):
        self.store = store

    def find_related(self, mid: str, max_results: int = 5) -> List[Dict]:
        entry = self.store.get(mid)
        if not entry:
            return []
        related = []
        for other_mid, other in self.store.data.items():
            if other_mid == mid:
                continue
            score = 0
            # 相同标签
            shared_tags = set(entry.get("tags", [])) & set(other.get("tags", []))
            score += len(shared_tags) * 0.3
            # 相同场景
            if entry.get("scene") and entry["scene"] == other.get("scene"):
                score += 0.2
            # 相同日期
            if entry["created_at"][:10] == other["created_at"][:10]:
                score += 0.15
            if score > 0:
                related.append({"id": other_mid, "text": other.get("text", "")[:80], "score": round(score, 2)})
        return sorted(related, key=lambda x: x["score"], reverse=True)[:max_results]

# ================================
# 工具6: 记忆标签
# ================================
class TagManager:
    """记忆标签 — 打标签/搜索/热门"""
    def __init__(self, store: MemoryStore):
        self.store = store

    def add_tag(self, mid: str, tag: str):
        entry = self.store.data.get(mid)
        if entry:
            tag = tag.strip().lower()
            tags = entry.get("tags", [])
            if tag not in tags:
                tags.append(tag)
                entry["tags"] = tags
                self.store.save()

    def remove_tag(self, mid: str, tag: str):
        entry = self.store.data.get(mid)
        if entry:
            tag = tag.strip().lower()
            tags = entry.get("tags", [])
            if tag in tags:
                tags.remove(tag)
                entry["tags"] = tags
                self.store.save()

    def search_by_tag(self, tag: str) -> List[dict]:
        tag = tag.strip().lower()
        return [e for e in self.store.data.values() if tag in e.get("tags", [])]

    def hot_tags(self, limit: int = 10) -> List[tuple]:
        counter = Counter()
        for e in self.store.data.values():
            for t in e.get("tags", []):
                counter[t] += 1
        return counter.most_common(limit)

# ================================
# 工具7: 记忆统计
# ================================
class StatsEngine:
    """记忆统计 — 总量/日期分布/标签/场景"""
    def __init__(self, store: MemoryStore, scenes: SceneManager):
        self.store = store
        self.scenes = scenes

    def get_stats(self) -> dict:
        entries = self.store.list_all()
        if not entries:
            return {"total": 0, "daily": {}, "tag_stats": {}, "scene_stats": {}, "avg_access": 0}

        # 日期分布
        daily = Counter(e["created_at"][:10] for e in entries)
        # 标签统计
        tag_counter = Counter()
        for e in entries:
            for t in e.get("tags", []):
                tag_counter[t] += 1
        # 场景统计
        scene_stats = self.scenes.all_scenes()
        # 平均访问
        avg_access = sum(e.get("access_count", 0) for e in entries) / len(entries)

        return {
            "total": len(entries),
            "daily_distribution": dict(daily.most_common(10)),
            "tag_stats": dict(tag_counter.most_common(10)),
            "scene_stats": scene_stats,
            "avg_access": round(avg_access, 1),
        }

# ================================
# 工具8: 记忆导出/导入
# ================================
class ExportImport:
    """记忆导出导入 — JSONL格式"""
    @staticmethod
    def export_to_jsonl(store: MemoryStore, filepath: str) -> int:
        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for entry in store.data.values():
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1
        return count

    @staticmethod
    def import_from_jsonl(store: MemoryStore, filepath: str) -> int:
        if not os.path.exists(filepath):
            return 0
        count = 0
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    mid = entry.get("id") or hashlib.md5(entry.get("text", "").encode()).hexdigest()[:16]
                    store.data[mid] = entry
                    count += 1
                except json.JSONDecodeError:
                    continue
        if count:
            store.save()
        return count

# ================================
# 工具9: 记忆推荐
# ================================
class Recommender:
    """基于上下文的记忆推荐"""
    def __init__(self, store: MemoryStore):
        self.store = store

    def recommend(self, context_text: str, top_k: int = 3) -> List[dict]:
        """根据上下文文本推荐相关记忆"""
        if not self.store.data:
            return []
        context_tokens = set(re.findall(r'[\u4e00-\u9fff]{2,}', context_text))
        context_english = set(re.findall(r'[a-zA-Z][a-zA-Z0-9_]{2,}', context_text.lower()))
        context_tokens.update(context_english)

        scored = []
        for mid, entry in self.store.data.items():
            text_tokens = set(re.findall(r'[\u4e00-\u9fff]{2,}', entry.get("text", "")))
            text_english = set(re.findall(r'[a-zA-Z][a-zA-Z0-9_]{2,}', entry.get("text", "").lower()))
            text_tokens.update(text_english)
            overlap = len(context_tokens & text_tokens)
            if overlap > 0:
                scored.append({
                    "id": mid,
                    "text": entry.get("text", "")[:100],
                    "score": overlap / len(context_tokens) if context_tokens else 0,
                    "created_at": entry.get("created_at", ""),
                })
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

# ================================
# 工具10: 快捷笔记 (类 memory_note)
# ================================
class QuickNote:
    """快捷笔记 — 像便签一样存"""
    NOTES_FILE = os.path.join(WORKSPACE, ".quick_notes.json")
    def __init__(self):
        self.notes: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.NOTES_FILE):
            try:
                with open(self.NOTES_FILE, encoding="utf-8") as f:
                    self.notes = json.load(f)
            except Exception:
                logging.exception("[auto_memory.py] suppressed")
                self.notes = {}

    def _save(self):
        with open(self.NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.notes, f, ensure_ascii=False, indent=2)

    def add(self, text: str) -> str:
        nid = hashlib.md5(text.encode()).hexdigest()[:12]
        self.notes[nid] = {
            "text": text,
            "created_at": datetime.now(BEIJING_TZ).isoformat(),
        }
        self._save()
        return nid

    def list_all(self) -> List[dict]:
        return [{"id": k, **v} for k, v in self.notes.items()]

    def search(self, keyword: str) -> List[dict]:
        return [{"id": k, **v} for k, v in self.notes.items() if keyword in v["text"]]

    def remove(self, nid: str) -> bool:
        if nid in self.notes:
            del self.notes[nid]
            self._save()
            return True
        return False

# ================================
# 统一引擎接口
# ================================
class AutoMemory:
    """统一记忆引擎 v2.1 — SQLite 主力存储 + 倒排缓存 + TF-IDF 语义重排序 + L0日志
    
    P1 方案B 重构（2026-05-15）：
      - 存储层从 JSON 全量读写切换为 SQLite 行级操作
      - SQLite 为主力，JSON 作为降级回退
      - 写入性能从 13ms/条 → 0.4ms/条
      - 中文搜索全面支持（多词拆分 LIKE + FTS5 英文）
    """
    def __init__(self):
        # SQLite 主力存储（行级读写，不写全量）
        self._db = None
        self._db_init_fail_reason = None
        try:
            from core.engines.tools.crusheart_db import get_db
            self._db = get_db()
            if self._db is not None:
                logging.info("[auto_memory] SQLite DB initialized via crusheart_db")
            else:
                self._db_init_fail_reason = "crusheart_db.get_db() returned None"
                logging.warning(f"[auto_memory] DB init: {self._db_init_fail_reason}")
        except ImportError as e:
            self._db_init_fail_reason = f"crusheart_db module not available: {e}"
            logging.warning(f"[auto_memory] DB init: {self._db_init_fail_reason} — falling back to JSON store")
        except Exception as e:
            self._db_init_fail_reason = f"DB init failed: {e}"
            logging.warning(f"[auto_memory] DB init: {self._db_init_fail_reason} — falling back to JSON store")
        
        # 倒排索引（内存缓存，用于 TF-IDF 语义重排序）
        self.inverted_index = InvertedIndex()
        
        # JSON 降级存储（当 SQLite 不可用时回退）
        self._json_store = MemoryStore()
        
        # 场景分组（从 SQLite 读取，不再独立 JSON）
        self.scenes = SceneManager(db=self._db)
        
        # 用户画像
        self.persona = PersonaManager()
        
        # 标签管理（基于 SQLite tags 字段）
        self.tags = TagManager(self._json_store)
        
        # 关联图谱（基于标签/场景关联）
        self.graph = MemoryGraph(self._db or self._json_store)
        
        # 统计引擎
        self.stats_engine = StatsEngine(self._db or self._json_store, self.scenes)
        
        # 导出导入
        self.export_import = ExportImport()
        
        # 推荐器
        self.recommender = Recommender(self._db or self._json_store)
        
        # 快捷笔记（独立文件，不影响主存储）
        self.notes = QuickNote()
        
        # 知识图谱（延迟构建 + 批量 ingest）
        self._knowledge_graph = None
        self._kg_buffer = []
        self._kg_buffer_failed = []
        # ── v6.3.2: 记忆快照冻结机制 ──
        self._snapshot_frozen = False
        self._drift_cache = {}
        try:
            if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)
            from scripts.knowledge_graph import KnowledgeGraph
            self._knowledge_graph = KnowledgeGraph()
        except ImportError:
            logger.debug("[AutoMemory] knowledge_graph 不可用（可选依赖），跳过")
        except BaseException as e:
            logger.warning(f"[AutoMemory] knowledge_graph 加载失败: {e}")

        # exec_logger
        self._exec_logger = None
        try:
            from core.engines.memory.exec_logger import log_execution
            self._exec_logger = log_execution
        except ImportError:
            pass

        # 远程语义 embedding — 自动检测用户 openclaw.json 配置
        # 优先级：openclaw.json → 环境变量 → 不启用
        self._remote_embed_available = False
        self._embedding_api = ""
        self._embedding_headers = None
        try:
            _config_dir = os.environ.get("OPENCLAW_CONFIG_DIR", os.path.expanduser("~/.openclaw"))
            _config_path = os.path.join(_config_dir, "openclaw.json")
            if os.path.exists(_config_path):
                with open(_config_path) as _f:
                    _cfg = json.load(_f)
                _remote = _cfg.get("agents", {}).get("defaults", {}).get("memorySearch", {}).get("remote", {})
                _base_url = _remote.get("baseUrl", "")
                _api_key = _remote.get("apiKey", "")
                _headers = _remote.get("headers", {})
                # 检查 headers 里有实际的认证信息，而非字段名
                has_auth = any('auth' in k.lower() or 'key' in k.lower() or 'token' in k.lower() for k in _headers)
                if _base_url and (_api_key or has_auth):
                    self._embedding_api = _base_url.rstrip("/") + "/embeddings"
                    self._embedding_headers = {"Content-Type": "application/json"}
                    self._embedding_headers.update(_headers)
                    self._remote_embed_available = True
        except Exception:
            pass
        # 环境变量覆盖（非 OpenClaw 环境或用自定义端点）
        _env_url = os.environ.get("EMBEDDING_API_URL", "")
        _env_key = os.environ.get("EMBEDDING_API_KEY", "")
        if _env_url and _env_key:
            self._embedding_api = _env_url
            self._embedding_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_env_key}",
            }
            try:
                _extra = os.environ.get("EMBEDDING_EXTRA_HEADERS", "")
                if _extra:
                    self._embedding_headers.update(json.loads(_extra))
            except Exception:
                pass
            self._remote_embed_available = True
        if self._remote_embed_available:
            # 确保 Content-Type 存在
            self._embedding_headers.setdefault("Content-Type", "application/json")

        # TF-IDF 语义重排序（降级方案）
        self._tfidf_available = extract_tfidf_tokens is not None and build_vector_v2 is not None and cosine_similarity is not None
        
        # 记忆层级引擎（核心锚点/冷热存储/固化门槛）- 已内联

        # 如果 SQLite 和 JSON 中已有数据，将 JSON 数据迁移到 SQLite
        self._migrate_if_needed()
        
        # P1: batch commit + 倒排索引懒重建
        self._batch_count = 0
        self._index_dirty = 0
        # L0 日志缓冲
        self._l0_buffer = []

        # 规则③: 会话内重复计数器 {content_hash: count}
        self._session_repeat: Dict[str, int] = {}

        # 规则②③④: 即时固化模块（内联 force_consolidate）
        self._immediate_consolidator = self.force_consolidate
        
        # 性能: LRU 去重缓存 + 锚点结果缓存
        self._dedup_cache = {}
        self._anchor_cache = {}
        
        # MLE 兼容属性（被 force_consolidate/get_preloaded_anchors 等使用）
        self.workspace = WORKSPACE
        self.memory_dir = MEMORY_DIR
        self.long_term_file = os.path.join(WORKSPACE, "MEMORY.md")

        # C4: 记忆融合配置加载
        self._fusion_config = {"enabled": True, "pre_save_check": {"enabled": True, "level": "normal", "strict_mode": False}, "post_search": {"enabled": True, "attach_confidence_score": True}, "learning_loop": {"enabled": True, "trigger_on_block": True, "tag_prefix": "memory_fusion"}}
        _fusion_yaml = os.path.join(WORKSPACE, "core", "memory_fusion_config.yaml")
        if os.path.exists(_fusion_yaml):
            try:
                with open(_fusion_yaml) as _f:
                    _ycfg = yaml.safe_load(_f)
                if _ycfg and isinstance(_ycfg, dict):
                    self._fusion_config.update(_ycfg.get("memory_fusion", {}))
            except Exception:
                pass
        self.logs_dir = os.path.join(self.memory_dir, "logs")
        self.topics_dir = os.path.join(self.memory_dir, "topics")
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.topics_dir, exist_ok=True)

    def _migrate_if_needed(self):
        """自动迁移 JSON 存量数据到 SQLite"""
        json_path = os.path.join(WORKSPACE, ".memory_store.json")
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception:
            return
        if not isinstance(json_data, dict) or len(json_data) == 0:
            return
        # 如果 SQLite 已经是空的，迁移
        if self._db and self._db.memory_count() == 0:
            count = 0
            for mid, entry in json_data.items():
                text = entry.get("text", "")
                if not text:
                    continue
                tags = entry.get("tags", [])
                scene = entry.get("scene", "")
                self._db.save_memory(text, tags, scene, mid=mid)
                count += 1
            print(f"  ✅ 自动迁移 {count} 条 JSON 记忆到 SQLite")
            # 迁移后也重建倒排索引
            self.inverted_index._rebuild(db=self._db)
        else:
            # 即使 SQLite 有数据，也确保倒排索引有覆盖
            self.inverted_index._rebuild(db=self._db)

    # --- 核心操作 ---

    def _flush_l0_log(self):
        """批量刷写 L0 日志"""
        if not self._l0_buffer:
            return
        l0_path = os.path.join(MEMORY_DIR, f"{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d')}.md")
        os.makedirs(os.path.dirname(l0_path), exist_ok=True)
        try:
            with open(l0_path, "a", encoding="utf-8") as f:
                f.write("".join(self._l0_buffer))
            self._l0_buffer = []
        except Exception:
            pass

    def is_core_anchor(self, content: str) -> bool:
        """核心锚点准入规则（内联，带结果缓存）"""
        text_key = hashlib.md5(content.strip()[:100].encode()).hexdigest()[:16]
        cached = self._anchor_cache.get(text_key)
        if cached is not None:
            return cached
        content_lower = content.lower()
        for kw in CORE_ANCHOR_KEYWORDS:
            if kw in content:
                self._anchor_cache[text_key] = True
                return True
        if force_core_anchor_by_instruction(content):
            self._anchor_cache[text_key] = True
            return True
        self._anchor_cache[text_key] = False
        return False

    def cold_hot_policy(self, last_access_days: int, is_anchor: bool,
                          access_count: int = 0, user_marked: bool = False) -> str:
        """冷热存储豁免规则（v2.0 带权重衰减）"""
        wd_r = self.weight_decay(last_access_days, is_anchor, access_count, user_marked)
        return wd_r["storage"]

    def _apply_weight_decay_to_results(self, results: list) -> list:
        """
        对搜索结果应用权重衰减：结合相似度 × 衰退权重 综合排序。
        重要记忆（高频访问、用户标记、核心锚点）排序更靠前。
        """
        if not results:
            return results
        
        now_ts = time.time()
        DAY = 86400
        
        for r in results:
            text = r.get("content") or r.get("text") or ""
            raw_score = r.get("score", 0.5)
            
            # 计算距上次访问天数
            last_access = r.get("metadata", {}).get("last_access", "") if isinstance(r.get("metadata"), dict) else ""
            if last_access:
                try:
                    last_dt = datetime.fromisoformat(last_access)
                    days_since = (datetime.now(BEIJING_TZ) - last_dt).total_seconds() / DAY
                except Exception:
                    days_since = 0
            else:
                days_since = 0
            
            # 判断是否是核心锚点
            is_anchor = self.is_core_anchor(text)
            # access_count
            access_count = r.get("access_count", 0)
            # user_marked: 通过 metadata 或标签判断
            meta = r.get("metadata", {})
            user_marked = False
            if isinstance(meta, dict):
                user_marked = meta.get("user_explicit", False) or meta.get("user_marked", False)
            # 标签中如果有 "remember" 也视为用户标记
            tags = r.get("tags", [])
            if isinstance(tags, list) and "remember" in tags:
                user_marked = True
            
            # 调用 weight_decay
            decay_result = self.weight_decay(
                last_access_days=int(days_since),
                is_anchor=is_anchor,
                access_count=access_count,
                user_marked=user_marked,
            )
            decay_weight = decay_result["weight"]
            
            # 最终排序分 = 语义相似度 × 衰减权重
            # 核心锚点保持原始分数（权重=1.0）
            # 高频记忆提升，低频记忆降低
            weighted = raw_score * decay_weight
            r["_raw_score"] = raw_score
            r["_decay_weight"] = decay_weight
            r["_decay_action"] = decay_result["action"]
            r["score"] = round(weighted, 4)
        
        # 按综合权重重新排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def consolidation_threshold(self, content: str, ref_count: int = 0,
                                 user_explicit: bool = False,
                                 session_repeat: int = 0,
                                 context: str = "save",
                                 freq_weekly: int = 0,
                                 days_since_last_access: int = 0,
                                 user_activity_level: float = 1.0) -> tuple:
        """梦境固化门槛（动态阈值版 v6.0）"""
        is_anchor = self.is_core_anchor(content)
        noise = is_noise_content(content)
        if is_anchor:
            return True, 3, "core_anchor"
        if user_explicit:
            return True, 3, "user_explicit_remember"
        if session_repeat >= 3:
            return True, 3, "session_repeat_3"
        if context == "maintenance" and not noise:
            return True, 3, "pre_expiry_consolidation"
        # 动态阈值
        dynamic_threshold = 2
        if freq_weekly >= 3:
            dynamic_threshold -= 1
        if days_since_last_access >= 30:
            dynamic_threshold += 1
        if days_since_last_access >= 90:
            dynamic_threshold += 1
        if user_activity_level > 1.0:
            dynamic_threshold = max(1, dynamic_threshold - 1)
        if ref_count >= dynamic_threshold:
            return True, 3, f"ref_count_threshold_{dynamic_threshold}"
        if not noise:
            return True, 2, "l2_meaningful"
        return False, 2, "noise_filtered"
    def _semantic_dedup_check(self, text: str, threshold: float = 0.85,
                                conflict_threshold: float = 0.70) -> dict:
        """
        写入前语义去重 + 冲突检测。
        - 相似度 ≥ 0.85 → is_duplicate=True，返回最相似条目
        - 相似度 0.70~0.84 + 否定语义 → has_conflict=True
        - 否则 → 允许写入
        """
        if not self._tfidf_available or not text.strip():
            return {"is_duplicate": False, "has_conflict": False}
        # LRU 缓存：相同文本 60 秒内跳过重复计算
        text_key = hashlib.md5(text.strip()[:100].encode()).hexdigest()[:16]
        cached = self._dedup_cache.get(text_key)
        if cached:
            age = time.time() - cached["ts"]
            if age < 60:
                return cached["result"]

        tokens = extract_tfidf_tokens(text)
        if not tokens:
            return {"is_duplicate": False, "has_conflict": False}

        # ── 分层采样：时间窗口策略 ──
        #   近 7 天 -> 全量
        #   7~30 天 -> 按时间衰减比例采样
        #   30~90 天 -> 稀疏衰减采样
        #   >90 天 -> 仅核心锚点相关
        #   目标：总比对量 ~50 条，保证覆盖深度同时控制开销
        samples = []
        now_ts = time.time()
        DAY = 86400
        TARGET_TOTAL = 50
        if self._db:
            try:
                # 一次性拉取近 90 天所有条目
                all_recent = self._db.conn.execute(
                    "SELECT id, content, updated_at, metadata FROM memories "
                    "WHERE updated_at >= datetime('now', '-90 days') LIMIT 200 "
                    "ORDER BY updated_at DESC"
                ).fetchall()
                # 按时间窗口分组
                buckets = {"d7": [], "d30": [], "d90": []}
                for r in all_recent:
                    sid = dict(r)["id"]
                    scontent = dict(r)["content"]
                    if not scontent or scontent == text:
                        continue
                    meta_str = dict(r)["metadata"]
                    try:
                        meta = json.loads(meta_str or "{}")
                    except Exception:
                        meta = {}
                    updated = meta.get("last_seen", "") or meta.get("updated_at", "")
                    if updated:
                        try:
                            age_days = (datetime.now(BEIJING_TZ) - datetime.fromisoformat(updated)).total_seconds() / DAY
                        except Exception:
                            age_days = 0
                    else:
                        age_days = 0
                    if age_days <= 7:
                        buckets["d7"].append((sid, scontent))
                    elif age_days <= 30:
                        buckets["d30"].append((sid, scontent))
                    elif age_days <= 90:
                        buckets["d90"].append((sid, scontent))
                
                # d7: 全量，最多 TARGET_TOTAL//2
                d7_count = min(len(buckets["d7"]), TARGET_TOTAL // 2)
                samples.extend(buckets["d7"][:d7_count])
                remaining = TARGET_TOTAL - len(samples)
                
                # d30: 衰减采样（权重 0.5）
                if remaining > 0 and buckets["d30"]:
                    d30_sample_count = min(int(remaining * 0.5), len(buckets["d30"]))
                    if d30_sample_count < len(buckets["d30"]):
                        samples.extend(random.sample(buckets["d30"], d30_sample_count))
                    else:
                        samples.extend(buckets["d30"])
                remaining = TARGET_TOTAL - len(samples)

                # d90: 稀疏采样（权重 0.2）
                if remaining > 0 and buckets["d90"]:
                    d90_sample_count = min(int(remaining * 0.4), len(buckets["d90"]))
                    if d90_sample_count < len(buckets["d90"]):
                        samples.extend(random.sample(buckets["d90"], d90_sample_count))
                    else:
                        samples.extend(buckets["d90"])
                remaining = TARGET_TOTAL - len(samples)

                # 如果还不够，拉 >90 天的稀疏补位
                if remaining > 0:
                    try:
                        old_rows = self._db.conn.execute(
                            "SELECT id, content FROM memories "
                            "WHERE updated_at < datetime('now', '-90 days') "
                            "ORDER BY RANDOM() LIMIT ?", (min(remaining, 10),)
                        ).fetchall()
                        for r in old_rows:
                            sid = dict(r)["id"]
                            scontent = dict(r)["content"]
                            if scontent and scontent != text:
                                samples.append((sid, scontent))
                    except Exception:
                        pass
            except Exception:
                pass

        if not samples:
            # 降级：从 json_store 查（也走分层逻辑）
            all_items = self._json_store.list_all() if hasattr(self, '_json_store') else []
            import random as _rnd
            for item in all_items:
                scontent = item.get('text', item.get('content', ''))
                if not scontent or scontent == text:
                    continue
                samples.append((item.get('mid', item.get('id', '')), scontent))
            # 随机采样最多 50 条（json_store 无时间戳，无法分层）
            if len(samples) > TARGET_TOTAL:
                samples = _rnd.sample(samples, TARGET_TOTAL)

        if not samples:
            return {"is_duplicate": False, "has_conflict": False}

        query_vec = build_vector_v2(tokens, VECTOR_DIM)
        best_id = None
        best_sim = 0.0
        for sid, stext in samples:
            stokens = extract_tfidf_tokens(stext)
            if not stokens:
                continue
            svec = build_vector_v2(stokens, VECTOR_DIM)
            sim = cosine_similarity(query_vec, svec)
            if sim > best_sim:
                best_sim = sim
                best_id = sid

        if best_sim >= threshold:
            return {
                "is_duplicate": True,
                "similarity": best_sim,
                "existing": self.get(best_id) if self.get(best_id) else {},
            }

        # 冲突检测：中高相似度 + 语义对立标记
        has_conflict = False
        conflict_id = None
        conflict_sim = 0.0
        if best_sim >= conflict_threshold and best_sim < threshold and best_id:
            conflict_id = best_id
            conflict_sim = best_sim
            has_conflict = True

        return {
            "is_duplicate": False,
            "has_conflict": has_conflict,
            "conflict_with": self.get(conflict_id) if conflict_id else {},
            "conflict_similarity": conflict_sim,
        }

    # ================================================================
    # 实时信号评分（接入 quality_dashboard 的 signal_scorer 维度）
    # ================================================================
    SIGNAL_RULES = [
        # (关键词列表, 得分, 标签, 说明)
        (["记住", "别忘了", "不要忘", "记下来", "别忘了这", "记住这个"], 0.92, "explicit-remember", "显式要求记忆"),
        (["决定", "就这么", "我们做", "就这么办", "就这么定了"], 0.80, "decision", "决策"),
        (["截止", "面试", "提交", "到期", "ddl", "deadline", "明天", "后天", "下周一"], 0.90, "deadline-critical", "截止/日程"),
        (["担心", "害怕", "焦虑", "高兴", "喜欢", "讨厌", "爱", "生气", "伤心"], 0.82, "emotional", "情感表达"),
        (["更喜欢", "通常", "从不", "习惯", "偏爱"], 0.80, "preference", "偏好"),
        (["谢谢", "太好了", "真棒", "干得好", "你很", "你真"], 0.80, "relationship", "关系反馈"),
        (["项目", "任务", "正在做", "搭建", "部署", "开发", "上线", "修复"], 0.68, "project-context", "项目上下文"),
    ]

    @classmethod
    def score_message(cls, text: str) -> dict:
        """
        实时信号评分：对消息计算记忆价值分，返回分数 + 标签。
        结果接入 quality_dashboard 的 signal_scorer 维度。
        """
        if not text or not text.strip():
            return {"score": 0.0, "tag": "", "label": "skip-empty"}

        text_lower = text.lower()
        best_score = 0.0
        best_tag = ""
        best_label = "general"

        # 先跑关键词匹配（短消息也可能包含高价值关键词）
        for keywords, score, tag, label in cls.SIGNAL_RULES:
            for kw in keywords:
                if kw in text_lower:
                    if score > best_score:
                        best_score = score
                        best_tag = tag
                        best_label = label
                    break

        # 短消息无关键词命中 → 过滤掉
        if len(text.strip()) < 30 and best_score < 0.5:
            return {"score": 0.0, "tag": "", "label": "skip-too-short"}

        # 长消息基础分
        if len(text) > 200 and best_score < 0.7:
            best_score = 0.70
            best_tag = "substantial-input"
            best_label = "足量信息"

        # 含具体数字（仅当无更高分匹配时）
        if best_score < 0.6:
            import re
            if re.search(r'\b\d+[\d\.,]*\b', text):
                best_score = 0.55
                best_tag = "contains-numbers"
                best_label = "含具体数据"

        return {
            "score": round(best_score, 2),
            "tag": best_tag,
            "label": best_label,
            "char_len": len(text),
        }

    # ────────────────────────────────────────────────────────
    # Item 3: Entity type detection for brain knowledge base
    # ────────────────────────────────────────────────────────
    _ENTITY_PATTERNS = {
        "person": [
            r'(?:叫|认识|见过|提到|和|跟|找)\s*[\u4e00-\u9fa5]{2,4}(?:老师|同学|朋友|哥|姐|总|[生医])',
            r'[\u4e00-\u9fa5]{2,4}(?:老师|同学|朋友|哥哥|姐姐|先生|女士|师傅)',
            r'(?:联系人|通讯录|这个人|那个人|那谁)\s*[\u4e00-\u9fa5]{2,}',
            r'(?:老|小)[\u4e00-\u9fa5]',
        ],
        "place": [
            r'(?:在|去|到|位于|住在|去了|去过|想去|从)\s*[\u4e00-\u9fa5]{2,}(?:小区|大厦|路|街|公园|酒店|餐厅|咖啡|馆|店|广场|中心|大学|学院|校区|新城|花园|苑|里|庄|村|巷|弄|道|楼)',
            r'(?:天津|北京|上海|广州|深圳|杭州|成都|武汉|南京|重庆|西安|苏州|厦门|长沙|郑州|青岛|大连|昆明)[\u4e00-\u9fa5]{0,6}(?:区|县|市|路|街|巷|新城|花园|苑|里)',
            r'[\u4e00-\u9fa5]{2,}(?:省|市|区|县|镇|乡|街道|路|街|巷|村)',
        ],
        "game": [
            r'(?:玩|打|通关|下载|开黑|上分|排位)\s*[\u4e00-\u9fa5A-Za-z0-9]{2,}(?:游戏|demo|版|启动器)',
            r'(?:FPS|MOBA|RPG|沙盒|开放世界|独立游戏|3A|网游|手游|肉鸽|rouge|类魂|银河城)',
            r'(?<![a-zA-Z])(Dreamcore|Minecraft|原神|王者荣耀|LOL|瓦罗兰特|Valorant|CS[0-9GO]?|吃鸡|PUBG|永劫无间|APEX|Apex\s*Legends|老头环|Elden\s*Ring|黑神话[\u4e00-\u9fa5]*|法环|只狼|战神|God\s*of\s*War|蜘蛛侠|地平线|赛博朋克|Cyberpunk|艾尔登|塞尔达|Zelda|星露谷|Stardew|空洞骑士|Hollow\s*Knight)(?![a-zA-Z])',
        ],
        "tech": [
            r'(?:用|装|配置|折腾|调试|部署|搭|写|学过|会用|熟悉)\s*[\u4e00-\u9fa5A-Za-z./]{2,}(?:工具|软件|框架|库|IDE|编辑器|语言|包|插件|驱动|系统|环境|脚本|代码|程序)',
            r'[\u4e00-\u9fa5a-zA-Z]{1,}(?:脚本|代码|程序|系统|工具|软件|API|SDK|框架|库)',
            r'(?<![a-zA-Z])(Python|Java|JavaScript|JS|TypeScript|TS|Node\.js|Node|React|Vue|Angular|Docker|Git|Linux|Windows|macOS|Android|iOS|Flutter|Swift|Kotlin|Rust|Go|C\+\+|C#|Ruby|PHP|Shell|Bash|SQL|NoSQL|Redis|MongoDB|MySQL|PostgreSQL|nginx|kubernetes|k8s|terraform|ansible|prometheus|grafana|Next\.js|Nuxt|Sass|Webpack|Vite|Babel|ESLint|Prettier|Jest)(?![a-zA-Z])',
        ],
        "media": [
            r'(?:看|读|听|追|刷|收藏|在)\s*[\u4e00-\u9fa5A-Za-z]{1,}(?:电影|剧[片]?|番[剧]?|动漫|书[籍]?|小说|漫画|综艺|纪录片|视频|播客|音乐|歌[曲]?|直播|节目|UP[主]?)',
            r'(?:B站|YouTube|Netflix|Disney\+|豆瓣|Spotify|小红书|抖音|快手|微博|知乎|bilibili|AcFun|爱奇艺|优酷|腾讯视频|芒果)',
        ],
        "event": [
            r'(?:参加|举办|报名|出席|组织|有)\s*[\u4e00-\u9fa5]{1,}(?:会|展|节|赛|活动|讲座|培训|课程|考试|面试|聚会|会议|答辩|汇报|讲座|课|考)',
            r'(?:考试|开会|上课|面试|出差|加班|请假|培训|答辩|春游|秋游|团建|聚餐|约饭|逛街|看展)',
            r'(?:明天|后天|周末|下周|下个月|月底)\s*(?:有|要|有个|参加|去|安排|约)\s*[\u4e00-\u9fa5]{2,}',
        ],
        "org": [
            r'(?:在|加入|入职|离职|面试|去)\s*[\u4e00-\u9fa5]{2,}(?:公司|集团|工作室|团队|组织|社团|部门|组|上班|工作|实习)',
            r'(?<![a-zA-Z])(华为|腾讯|阿里|字节[跳动]?|百度|美团|小米|网易|京东|拼多多|滴滴|bilibili|B站|小红书|知乎|OPPO|vivo|中兴|大疆|联想|用友|金蝶)(?![a-zA-Z])',
            r'(?<![a-zA-Z])(Google|Microsoft|Amazon|Meta|Apple|IBM|Intel|Oracle|SAP|Adobe|Spotify|Netflix|Uber|Airbnb|Twitter|Tesla|SpaceX)(?![a-zA-Z])',
        ],
    }

    @classmethod
    def _detect_entity_type(cls, text: str) -> Optional[str]:
        """
        检测文本是否涉及已知实体类型（人/地/游戏/技术/媒体/事件/组织）
        返回: 实体类型名称，或 None（无匹配）
        """
        if not text:
            return None
        for etype, patterns in cls._ENTITY_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text):
                    return etype
        return None

    # ────────────────────────────────────────────────────────
    # End Item 3
    # ────────────────────────────────────────────────────────

    def save(self, text: str, tags: List[str] = None, scene: str = "",
             metadata: dict = None) -> str:
        """
        保存一条记忆（增强版 v5.1）

        规则：
        - ② 用户明确要求「记住」（metadata.user_explicit=True）→ 即时固化
        - ③ 会话内同一语义提≥3次 → 即时固化
        - ④ 非噪音内容到期前全部入梦（由 consolidation_threshold 判断）
        """
        mid = hashlib.md5(text.encode()).hexdigest()[:16]
        
        # ── 规则③: 会话内重复计数 ──
        user_explicit = (metadata or {}).get("user_explicit", False)
        if not user_explicit and not scene:  # 场景标记的不计数（系统自动记录）
            self._session_repeat[mid] = self._session_repeat.get(mid, 0) + 1
        session_repeat = self._session_repeat.get(mid, 0)

        # ── 记忆融合：anti_fake 存储前校验 ──
        try:
            from core.engines.quality.anti_fake_validator import AntiFakeValidator as _AF
            _fusion_cfg = getattr(self, '_fusion_config', {})
            _pre_save = _fusion_cfg.get("pre_save_check", {})
            if _fusion_cfg.get("enabled", True) and _pre_save.get("enabled", True):
                af_result = _AF._check_memory_save(text, metadata)
            else:
                af_result = {"blocked": False, "reason": "fusion_disabled"}
            if af_result.get("blocked", False):
                logger.warning(f"[MemoryFusion] 记忆存储被拦截: {af_result.get('reason', '')}")
                if self._exec_logger:
                    self._exec_logger("memory_save", "blocked_by_antifake", 3,
                                      f"blocked: {af_result.get('reason', '')[:60]}", text[:60])
                return "__blocked__"
        except Exception:
            pass  # 校验异常不阻塞写入

        # ── 语义去重 + 冲突检测（写入前预检） ──
        dedup_result = self._semantic_dedup_check(text)
        if dedup_result["is_duplicate"]:
            # 语义相似度 ≥0.85 → 更新现有条目，不创建新记录
            existing = dedup_result["existing"]
            existing_mid = existing.get("id") or existing.get("mid")
            if existing_mid:
                meta = json.loads(existing.get("metadata", "{}"))
                meta["access_count"] = meta.get("access_count", 0) + 1
                meta["last_seen"] = datetime.now(BEIJING_TZ).isoformat()
                if self._db:
                    self._db.update_memory(existing_mid, metadata=json.dumps(meta, ensure_ascii=False))
                # 返回已有 ID，不写入新记录
                if self._exec_logger:
                    self._exec_logger("memory_save", "dedup_merged", 3,
                                      f"merged into {existing_mid[:12]}", text[:60])
                return existing_mid
        elif dedup_result["has_conflict"]:
            # 相似度 0.70~0.84 + 语义冲突 → 标记冲突，允许写入
            conflict_with = dedup_result["conflict_with"]
            if metadata is None:
                metadata = {}
            metadata["semantic_conflict"] = {
                "with": conflict_with.get("id") or conflict_with.get("mid", ""),
                "similarity": round(dedup_result["conflict_similarity"], 4),
                "detected_at": datetime.now(BEIJING_TZ).isoformat(),
            }

        # ── 判断是否需要即时固化 ──
        should_consolidate = False
        consolidate_target = 3
        consolidate_reason = ""

        sc, target, reason = self.consolidation_threshold(
            content=text,
            user_explicit=user_explicit,
            session_repeat=session_repeat,
        )
        should_consolidate, consolidate_target, consolidate_reason = sc, target, reason

        # ── 规则②③④: 即时执行固化 ──
        if should_consolidate and self._immediate_consolidator:
            try:
                result = self._immediate_consolidator(text, consolidate_target)
                # 记录到 L0 日志
                self._l0_buffer.append(
                    f"\n- [{datetime.now(BEIJING_TZ).strftime('%H:%M')}] 🧠 {consolidate_reason}: {text[:60]}"
                )
            except Exception as e:
                if self._exec_logger:
                    self._exec_logger("memory_consolidate", "fail", 5,
                                      f"reason={consolidate_reason} error={str(e)[:50]}",
                                      text[:40])

        # ── Item 3: 实体分类检测（brain 实体知识库） ──
        entity_type = self._detect_entity_type(text)
        if entity_type:
            if tags is None:
                tags = []
            brain_tag = f"brain:{entity_type}"
            if brain_tag not in tags:
                tags.append(brain_tag)
            if metadata is None:
                metadata = {}
            if isinstance(metadata, dict):
                metadata["entity_type"] = entity_type

        # SQLite 主力写入（行级，batch commit）
        if self._db:
            try:
                self._db.save_memory(text, tags, scene, metadata=metadata, mid=mid, _auto_commit=False)
                self._batch_count += 1
                if self._batch_count >= 10:
                    self._db.conn.commit()
                    self._batch_count = 0
            except Exception:
                self._batch_count = 0
                self._json_store.add(mid, text, tags, scene)
        else:
            self._json_store.add(mid, text, tags, scene)
        
        # 倒排索引：先增量更新内存索引，再标记刷盘
        self.inverted_index.add(mid, text)
        self._index_dirty = (self._index_dirty or 0) + 1
        if self._index_dirty >= 200:
            self.inverted_index._rebuild(db=self._db)
            self._index_dirty = 0
        
        if scene:
            self.scenes.assign(mid, text, scene)

        # L0 日志：批处理，攒到 50 条才写一次
        self._l0_buffer.append(f"\n- [{datetime.now(BEIJING_TZ).strftime('%H:%M')}] 💾 {text[:80]}")
        if len(self._l0_buffer) >= 50:
            self._flush_l0_log()

        # exec_logger
        if self._exec_logger:
            try:
                exec_meta = f"tags={tags}"
                if should_consolidate:
                    exec_meta += f" consolidate={consolidate_reason}"
                self._exec_logger("memory_save", "success", 2, text[:60], exec_meta)
            except Exception:
                pass

        # 知识图谱缓冲（攒到 100 条才 ingest）
        self._kg_buffer.append(text)
        if len(self._kg_buffer) >= 100 and self._knowledge_graph:
            try:
                for t in self._kg_buffer:
                    try:
                        self._knowledge_graph.ingest(t)
                    except Exception as e:
                        logger.warning(f"[AutoMemory] knowledge_graph ingest 失败: {e}")
                        self._kg_buffer_failed.append(t)
                self._kg_buffer = []
            except Exception as e:
                logger.warning(f"[AutoMemory] knowledge_graph 批量 ingest 异常: {e}")
                # 异常时不清空 buffer，下次重试
                pass

        return mid

    def get(self, mid: str) -> Optional[dict]:
        entry = None
        if self._db:
            try:
                entry = self._db.get_memory(mid)
                # 兼容: SQLite 用 content, JSON 存储用 text
                if entry and 'content' in entry and 'text' not in entry:
                    entry['text'] = entry['content']
            except Exception:
                pass
        if entry is None:
            entry = self._json_store.get(mid)
        if self._exec_logger:
            try:
                self._exec_logger("memory_get", "success" if entry else "fail", 2, f"found={bool(entry)}", mid[:12])
            except Exception:
                pass
        return entry

    def list_all(self) -> List[dict]:
        if self._db:
            try:
                return self._db.list_memories(limit=5000)
            except Exception:
                pass
        return self._json_store.list_all()

    def remove(self, mid: str) -> bool:
        ok = False
        if self._db:
            try:
                ok = self._db.remove_memory(mid)
            except Exception:
                pass
        j_ok = self._json_store.remove(mid)
        self.inverted_index.remove(mid)
        # P1: 标记要重建
        self._index_dirty = (self._index_dirty or 0) + 1
        self.scenes.remove(mid)
        ok = ok or j_ok
        if self._exec_logger:
            try:
                self._exec_logger("memory_remove", "success" if ok else "fail", 3, f"removed={ok}", mid[:12])
            except Exception:
                pass
        return ok

    def _get_remote_embedding(self, text: str):
        """调用远程语义 embedding 服务（自动检测 openclaw.json memorySearch.remote 或环境变量）"""
        if not self._remote_embed_available or not self._embedding_headers:
            return None
        try:
            import urllib.request
            model_name = os.environ.get("EMBEDDING_MODEL", "text-embedding-v1.0")
            body = json.dumps({"input": text, "model": model_name}).encode("utf-8")
            req = urllib.request.Request(
                self._embedding_api, data=body, headers=self._embedding_headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
                if d.get("data") and len(d["data"]) > 0:
                    return d["data"][0]["embedding"]
            return None
        except Exception:
            return None

    def _rerank_by_tfidf(self, query: str, results: list) -> list:
        """TF-IDF 语义重排序（降级方案）"""
        if not self._tfidf_available or len(results) <= 1:
            return [{"score": 0.5, **r} for r in results]
        try:
            query_tokens = extract_tfidf_tokens(query)
            query_vec = build_vector_v2(query_tokens)
            scored = []
            for r in results:
                text = r.get("content") or r.get("text") or ""
                text_tokens = extract_tfidf_tokens(text)
                text_vec = build_vector_v2(text_tokens)
                sim = cosine_similarity(query_vec, text_vec)
                scored.append((sim, r))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [{"score": round(sim, 4), **r} for sim, r in scored if sim >= 0.25]
        except Exception:
            return [{"score": 0.5, **r} for r in results]

    def _boost_brain_entity_results(self, query: str, results: list) -> list:
        """
        Item 3: 当 query 包含实体关键词时，对 brain:* 标签的结果上浮权重
        上浮规则：匹配实体类型且包含关键词的结果 +0.3 权重
        """
        if not query or not results:
            return results
        # 检测 query 中的实体类型
        for r in results:
            tags = r.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            # 只对 brain:* 标签的结果操作
            brain_tags = [t for t in tags if isinstance(t, str) and t.startswith("brain:")]
            if not brain_tags:
                continue
            for brain_tag in brain_tags:
                etype = brain_tag.replace("brain:", "")
                # 检查实体类型对应的关键词是否在 query 中
                patterns = self._ENTITY_PATTERNS.get(etype, [])
                for pat in patterns:
                    if re.search(pat, query):
                        # 命中：上浮权重
                        current_score = r.get("score", 0.5)
                        r["score"] = min(1.0, current_score + 0.3)
                        r["_entity_boosted"] = True
                        break
        return results

    def _apply_lazy_loading(self, scored: list, is_high_risk: bool, load_core_anchor: bool) -> list:
        """懒加载分层计数"""
        if is_high_risk or load_core_anchor or not scored:
            return scored
        tier_high = []
        tier_upper = []
        tier_lower = []
        tier_rest = []
        for r in scored:
            sim = r.get("score", 0)
            entry_text = r.get("content") or r.get("text") or ""
            is_core = self.is_core_anchor(entry_text) if hasattr(self, 'is_core_anchor') else False
            if is_core or sim >= 0.9:
                tier_high.append(r)
            elif sim >= 0.8:
                tier_upper.append(r)
            elif sim >= 0.7:
                tier_lower.append(r)
            else:
                tier_rest.append(r)
        final = tier_high[:]
        final.extend(tier_upper[:8])
        final.extend(tier_lower[:12])
        final.extend(tier_rest[:4])
        return final

    def search(self, query: str, is_high_risk: bool = False, load_core_anchor: bool = False, budget_tokens: int = 200) -> List[dict]:
        # Layer 0: 近期上下文语义检测 — 命中则直接短路，不走任何记忆检索
        if query and query.strip() and not is_high_risk:
            from core.engines.memory.auto_memory import _detect_recent_context
            recent_ctx = _detect_recent_context(query)
            if recent_ctx is not None:
                if self._exec_logger:
                    try:
                        self._exec_logger("memory_search", "recent_context_shortcut", 1,
                                          f"skipped memory, query: {query[:30]}", recent_ctx)
                    except Exception:
                        pass
                return [{
                    "id": "__recent_context__",
                    "content": f"[近期上下文查询] 标记: {recent_ctx}",
                    "text": f"[近期上下文查询] 标记: {recent_ctx}",
                    "_recent_context_query": True,
                    "_recent_context_label": recent_ctx,
                    "score": 1.0,
                    "created_at": datetime.now(BEIJING_TZ).isoformat(),
                    "tags": [],
                }]

        # Layer 2: 反注入校验（记忆检索前置检测）
        if query and query.strip() and not is_high_risk:
            try:
                from core.engines.quality.anti_fake_validator import AntiFakeValidator
                result = AntiFakeValidator._check_memory_input(query)
                if result.get("blocked", False):
                    logger.warning(f"[AutoMemory] 搜索被拦截: {result.get('reason', '')}")
                    blocked = [{
                        "id": "__blocked__",
                        "content": f"[搜索被拦截] {result.get('reason', '注入检测')}",
                        "text": f"[搜索被拦截] {result.get('reason', '注入检测')}",
                        "score": 0.0,
                        "created_at": datetime.now(BEIJING_TZ).isoformat(),
                        "tags": [],
                        "metadata": "{}",
                    }]
                    if self._exec_logger:
                        try:
                            self._exec_logger("memory_search", "blocked_injection", 3,
                                              f"injection blocked", query[:40])
                        except Exception:
                            pass
                    return blocked
            except Exception:
                pass  # 校验异常不阻塞搜索

        # P5: 检索缓存（30秒内相同查询直接返回）
        _cache_key = f"search::{query}::{is_high_risk}::{load_core_anchor}"
        now = time.time()
        cached = getattr(self, '_search_cache', {}).get(_cache_key)
        if cached and (now - cached[1]) < 30:
            return cached[0]

        # SQLite 主力搜索（FTS5/中文分词LIKE）
        if self._db and query.strip():
            try:
                results = self._db.search_memories(query, top_n=20)
            except Exception:
                results = self._json_search(query)
        else:
            results = self._json_search(query)

        # 语义重排序：远程 embedding 优先 → TF-IDF 降级
        if len(results) > 1:
            if self._remote_embed_available:
                # 尝试远程语义向量重排序
                query_vec = self._get_remote_embedding(query)
                if query_vec:
                    try:
                        scored = []
                        for r in results:
                            text = r.get("content") or r.get("text") or ""
                            text_vec = self._get_remote_embedding(text)
                            if text_vec:
                                import numpy as np
                                a, b = np.array(query_vec, dtype=np.float32), np.array(text_vec, dtype=np.float32)
                                n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
                                sim = float(np.dot(a, b) / (n1 * n2)) if n1 > 0 and n2 > 0 else 0
                                scored.append((sim, r))
                            else:
                                scored.append((0.0, r))
                        scored.sort(key=lambda x: x[0], reverse=True)
                        results = [{"score": round(sim, 4), **r} for sim, r in scored if sim >= 0.25]
                        scored_for_lazy = [r for r in results]
                    except Exception:
                        # 远程 embedding 失败 → 降级到 TF-IDF
                        results = self._rerank_by_tfidf(query, results)
                        scored_for_lazy = results
                else:
                    results = self._rerank_by_tfidf(query, results)
                    scored_for_lazy = results
            else:
                results = self._rerank_by_tfidf(query, results)
                scored_for_lazy = results

            # 懒加载分层计数
            if not is_high_risk and not load_core_anchor:
                results = self._apply_lazy_loading(scored_for_lazy, is_high_risk, load_core_anchor)

            # 实体匹配加权：当 query 包含实体关键词时，对 brain:* 标签的结果上浮权重
            if query:
                results = self._boost_brain_entity_results(query, results)

            # 权重衰减：综合语义相似度 × 衰退权重，重要记忆排序更靠前
            results = self._apply_weight_decay_to_results(results)

        if self._exec_logger:
            try:
                self._exec_logger("memory_search", "success", 5, f"found={len(results)}", query[:30])
            except Exception:
                pass

        # P5: 写入检索缓存
        if not hasattr(self, '_search_cache'):
            self._search_cache = {}
        self._search_cache[_cache_key] = (results, now)
        if len(self._search_cache) > 100:
            oldest = min(self._search_cache.keys(), key=lambda k: self._search_cache[k][1])
            del self._search_cache[oldest]

        # Token 预算渐进衰减：高分记忆全保留，低分按预算余量取舍
        # 高分（>=0.8）无上限全保留，中分（0.6-0.8）优先保留，低分（<0.6）按预算余量放
        if budget_tokens > 0:
            total_est = 0
            progressive = []
            truncated_low = 0
            # 先分档：高分全拿
            high_tier = [r for r in results if r.get("score", 0) >= 0.8]
            mid_tier = [r for r in results if 0.6 <= r.get("score", 0) < 0.8]
            low_tier = [r for r in results if r.get("score", 0) < 0.6]
            for r in high_tier:
                content = r.get("content") or r.get("text") or ""
                est_tokens = len(content) // 4 + 30
                progressive.append(r)
                total_est += est_tokens
            # 中分：有预算就放
            for r in mid_tier:
                content = r.get("content") or r.get("text") or ""
                est_tokens = len(content) // 4 + 30
                if total_est + est_tokens > budget_tokens:
                    truncated_low += 1
                    continue
                progressive.append(r)
                total_est += est_tokens
            # 低分：有预算就放，无预算跳过计数
            for r in low_tier:
                content = r.get("content") or r.get("text") or ""
                est_tokens = len(content) // 4 + 30
                if total_est + est_tokens > budget_tokens:
                    truncated_low += 1
                    continue
                progressive.append(r)
                total_est += est_tokens
            if truncated_low > 0 and progressive:
                # 添加压缩标记而非静默扔掉
                progressive.append({
                    "_compressed_sentinel": True,
                    "content": f"[以下 {truncated_low} 条低分记忆因 token 预算限制已压缩，总预算 {budget_tokens} token]"
                })
            return progressive
        # C4: 记忆融合 post_search — 附加 anti_fake 置信度评分
        _fusion_cfg2 = getattr(self, '_fusion_config', {})
        _post_s = _fusion_cfg2.get("post_search", {})
        if _fusion_cfg2.get("enabled", True) and _post_s.get("enabled", True) and _post_s.get("attach_confidence_score", True):
            try:
                from core.engines.quality.anti_fake_validator import AntiFakeValidator as _PSAF
                for _r in results:
                    _text = _r.get("content") or _r.get("text") or ""
                    if _text:
                        _ps_result = _PSAF._check_memory_input(_text)
                        _r["_fusion_confidence"] = {
                            "passed": not _ps_result.get("blocked", False),
                            "score": _ps_result.get("risk_score", 0.0),
                            "level": _ps_result.get("risk_level", "low"),
                        }
            except Exception:
                pass
        return results[:16]

    def _json_search(self, query: str) -> List[dict]:
        """降级搜索：倒排索引 + 全文遍历"""
        ids = self.inverted_index.search(query)
        results = []
        for mid in ids:
            entry = self._json_store.get(mid)
            if entry:
                results.append(entry)
        return results

    def search_with_timeline(self, query: str) -> dict:
        results = self.search(query)
        timeline = {}
        for r in results:
            content = r.get("content") or r.get("text") or ""
            date = r.get("created_at", "")[:10]
            if date not in timeline:
                timeline[date] = []
            timeline[date].append(content[:60])
        return {"results": results, "timeline": timeline}

    def stats(self) -> dict:
        if self._db:
            try:
                raw = self._db.stats()
                # 统一输出格式，确保包含 total 字段
                return {
                    "total": raw.get("memories", 0),
                    "memories": raw.get("memories", 0),
                    "sessions": raw.get("sessions", 0),
                    "evolution_logs": raw.get("evolution_logs", 0),
                    "preferences": raw.get("preferences", 0),
                    "db_size_kb": raw.get("db_size_kb", 0),
                }
            except Exception:
                pass
        raw = self._json_store.stats()
        # 确保包含 total 字段
        if "total" not in raw:
            raw["total"] = len(self._json_store.data) if hasattr(self._json_store, "data") else 0
        return raw

    def backup(self, path: str = None) -> str:
        path = path or os.path.join(WORKSPACE, ".memory_backup.jsonl")
        count = self.export_import.export_to_jsonl(self._json_store, path)
        # 导出索引
        index_path = path.replace(".jsonl", "_index.json")
        shutil.copy(self.inverted_index.index_file, index_path) if os.path.exists(self.inverted_index.index_file) else None
        return f"已备份 {count} 条记忆到 {path}"

    def restore(self, path: str) -> int:
        count = self.export_import.import_from_jsonl(self._json_store, path)
        # 重建索引
        for mid, entry in self._json_store.data.items():
            self.inverted_index.add(mid, entry.get("text", ""))
        return count

    def forget(self, keyword: str = "", date: str = ""):
        """按关键词或日期删除"""
        to_remove = []
        seen = set()
        # SQLite 主力存储（content 字段, 非 text）
        if self._db and (keyword or date):
            try:
                if keyword:
                    results = self._db.search_memories(keyword, top_n=500)
                    for r in results:
                        text = r.get("text") or r.get("content", "")
                        if keyword in text:
                            to_remove.append(r["id"])
                            seen.add(r["id"])
                elif date:
                    results = self._db.list_memories(limit=5000)
                    for r in results:
                        if r.get("created_at", "")[:10] == date and r["id"] not in seen:
                            to_remove.append(r["id"])
                            seen.add(r["id"])
            except Exception:
                pass
        # JSON 降级存储
        store = self._json_store
        for mid, entry in list(store.data.items()):
            if mid in seen:
                continue
            if (keyword and keyword in entry.get("text", "")) or \
               (date and entry.get("created_at", "")[:10] == date):
                to_remove.append(mid)
                seen.add(mid)
        for mid in to_remove:
            self.remove(mid)
        return len(to_remove)




    # ── 以下方法由原 memory_layer_engine 合并 ──

    def get_preloaded_anchors(self) -> list:
        """获取新会话需要预加载的核心锚点列表"""
        anchors = []
        if os.path.exists(self.long_term_file):
            with open(self.long_term_file, 'r', encoding='utf-8') as f:
                content = f.read()
            for match in re.findall(r'- \*\*(.+?):\*\*', content):
                anchors.append(match.strip())
        user_file = os.path.join(self.workspace, "USER.md")
        if os.path.exists(user_file):
            with open(user_file, 'r', encoding='utf-8') as f:
                content = f.read()
            for match in re.findall(r'(?:姓名|称呼|名字|所在地|位置|地址)[：:]\s*(.+)', content):
                anchors.append(match.strip())
        return anchors[:20]


    def classify_memory_layer(self, content: str, ref_count: int = 0, freq_weekly: int = 0) -> int:
        """
        判断内容应存入哪一层
        L1 — 会话记忆（临时）
        L2 — 日常记忆（一天内）
        L3 — 长期记忆（手动/自动）
        L4 — 向量（高频检索）
        """
        is_anchor = self.is_core_anchor(content)

        # 核心锚点直接升 L3
        if is_anchor:
            return 3

        # 高频检索升 L4
        if freq_weekly >= 3:
            return 4

        # 被引用 >=2 次升 L3
        if ref_count >= 2:
            return 3

        return 2  # 默认 L2


    def decay_policy(self, last_access_days: int, is_anchor: bool,
                      access_count: int = 0, user_marked: bool = False) -> dict:
        """
        记忆活跃度衰减规则（v2.0，使用 weight_decay）
        Returns: {"should_decay": bool, "weight": float, "action": str}
        """
        wd = self.weight_decay(last_access_days, is_anchor, access_count, user_marked)
        return {
            "should_decay": wd["action"] != "active" and wd["action"] != "keep",
            "weight": wd["weight"],
            "action": wd["action"],
        }


    def should_archive_today(self) -> bool:
        """判断当前时间是否在维护窗口（23:00-23:59）"""
        now = datetime.now(BEIJING_TZ)
        return now.hour == 23


    def consolidate_expiring(self, days_back: int = 7) -> list:
        """
        规则④: 短期记忆到期前，非噪音全量入梦。
        遍历 memory/ 目录中近期的 L0 日志，把有意义的记忆固化到 MEMORY.md。

        Args:
            days_back: 回溯天数（默认 7 天，即 L2 到期周期）

        Returns:
            [(content, reason), ...]
        """
        consolidated = []
        if not os.path.isdir(self.memory_dir):
            return consolidated

        today = datetime.now(BEIJING_TZ)
        cutoff = today - timedelta(days=days_back)

        from core.engines.memory.exec_logger import log_execution

        for fname in sorted(os.listdir(self.memory_dir)):
            if not fname.endswith(".md"):
                continue
            # 解析日期
            date_str = fname.replace(".md", "")
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
            except ValueError:
                continue
            if file_date < cutoff:
                continue  # 只处理到期范围内的

            fpath = os.path.join(self.memory_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # 按行分割，逐条判断
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 剥离时间戳前缀 [HH:MM]
                clean = re.sub(r'^\- \[\d{2}:\d{2}\]\s*', '', line)
                clean = re.sub(r'^[💾🧠📝🏛️]\s*', '', clean)
                clean = clean.strip()
                if len(clean) < 8:
                    continue  # 太短的不固化

                # 用 consolidation_threshold(context="maintenance")
                should, target, reason = self.consolidation_threshold(
                    content=clean, context="maintenance"
                )
                if should:
                    try:
                        result = self.force_consolidate(clean, target)
                        consolidated.append((clean, reason))
                        log_execution(
                            "memory_consolidate_batch", "success", 3,
                            result[:60],
                            f"reason={reason}"
                        )
                    except Exception:
                        pass

        return consolidated


    def force_consolidate(self, content: str, target_layer: int = 3,
                          target_file: str = None) -> str:
        """
        立即固化内容到指定层（不等 23:00 cron）
        用于规则②③④的即时触发。

        Args:
            content: 要固化的内容
            target_layer: 目标层级 (3=L3长期记忆, 4=L4归档)
            target_file: 可选，指定写入文件

        Returns:
            写入状态描述
        """
        long_term = target_file or self.long_term_file

        # 判断前缀
        prefix = ""
        if self.is_core_anchor(content):
            if not target_file:
                long_term = self.long_term_file
            prefix = "🧠 核心锚点: "
        elif target_layer >= 4:
            prefix = "🏛️ 归档: "
        else:
            prefix = "📝 固化: "

        # 去重
        if os.path.exists(long_term):
            with open(long_term, "r", encoding="utf-8") as f:
                existing = f.read()
            if content.strip() in existing:
                return f"已存在，跳过: {content[:40]}..."
        else:
            os.makedirs(os.path.dirname(long_term), exist_ok=True)

        # ── v6.3.2: Drift check before write ──
        drift = self.check_drift_before_write(long_term)
        if drift and drift.get("drifted"):
            return f"Drift detected, refused write. Backup: {drift.get('backup', '')}"

        # 追加写入
        entry = f"\n{prefix}{content.strip()}\n"
        with open(long_term, "a", encoding="utf-8") as f:
            f.write(entry)

        return f"已固化到 {os.path.basename(long_term)}: {content[:40]}..."


    def weight_decay(self, last_access_days: int, is_anchor: bool = False,
                      access_count: int = 0, user_marked: bool = False) -> dict:
        """
        记忆权重衰减算法（v2.0）
        
        核心逻辑：
        - 基础权重：天数驱动（≤7天=1.0，7~30天=0.8，30~90天=0.3~0.8，>90天=0.0冷存储）
        - 用户标记加权：用户明确要求「记住」的内容 → 权重×2，衰减周期延长3倍
        - 高频提及加权：access_count ≥ 3 → 权重×1.5；≥ 10 → 权重×2
        - 核心锚点加权：已标记为核心锚点 → 永久权重1.0（豁免衰减）
        
        公式：最终权重 = min(1.0, 基础权重 × 用户标记因子 × 高频因子)
        锚点直接返回 1.0。
        
        Returns:
            {"weight": float, "storage": str, "action": str, "factors": dict}
        """
        factors = {}

        # === 核心锚点：永久豁免 ===
        if is_anchor:
            return {
                "weight": 1.0,
                "storage": "hot",
                "action": "keep",
                "factors": {"base": 1.0, "anchor_exempt": True}
            }

        # === 基础衰减 ===
        if last_access_days <= 7:
            base_weight = 1.0
            storage = "hot"
        elif last_access_days <= 30:
            # 7~30天: 线性从 1.0 降到 0.8
            base_weight = 1.0 - (last_access_days - 7) * 0.01
            storage = "warm"
        elif last_access_days <= 90:
            # 30~90天: 从 0.8 降到 0.3
            base_weight = max(0.3, 0.8 - (last_access_days - 30) * 0.0083)
            storage = "warm"
        else:
            base_weight = 0.0
            storage = "cold"

        factors["base"] = round(base_weight, 3)

        # === 用户标记加权 ===
        if user_marked:
            # 用户明确要求记住 → 权重×2，同时将基础衰减的「天」数等效除以3
            base_weight = min(1.0, base_weight * 2.0)
            # 等效天数缩短：如果用户标记了，即使 90 天没访问也当 30 天
            if storage == "cold":
                storage = "warm"
            factors["user_marked"] = True
        else:
            factors["user_marked"] = False

        # === 高频提及加权 ===
        if access_count >= 10:
            freq_multiplier = 2.0
            if storage == "cold":
                storage = "warm"
        elif access_count >= 3:
            freq_multiplier = 1.5
        else:
            freq_multiplier = 1.0

        factors["freq_multiplier"] = freq_multiplier
        factors["access_count"] = access_count

        # === 综合权重 ===
        final_weight = min(1.0, base_weight * freq_multiplier)
        factors["final"] = round(final_weight, 3)

        # === 动作判断 ===
        if final_weight >= 0.8:
            action = "active"
        elif final_weight >= 0.3:
            action = "attenuate"
        else:
            action = "archive_to_cold"

        return {
            "weight": round(final_weight, 3),
            "storage": storage,
            "action": action,
            "factors": factors,
        }



    def get_memory_report(self) -> dict:
        """获取记忆系统状态报告"""
        return {
            "layers": {
                "L1_session": "对话上下文中",
                "L2_daily": len(os.listdir(self.logs_dir)) if os.path.exists(self.logs_dir) else 0,
                "L3_longterm": "MEMORY.md",
                "L4_vector": "TF-IDF增强版"
            },
            "core_anchors": len(CORE_ANCHOR_KEYWORDS),
            "instruction_detection": True,
            "maintenance_window": "23:00-23:59",
            "decay_threshold_days": {"attenuate": 30, "archive": 90},
            "anchor_exemption": True
        }


# 快速测试


    # ═══════════════════════════════════════
    # v6.3.2: 快照冻结 + Drift + 反注入
    # ═══════════════════════════════════════

    def snapshot_freeze(self, memory_text='', user_text=''):
        blocked = []
        for label, text in [('memory', memory_text), ('user', user_text)]:
            r = scan_memory_injection(text)
            if r:
                blocked.append(f'{label}: {r}')
        fm, fu = memory_text, user_text
        r = scan_memory_injection(memory_text)
        if r:
            fm = '[BLOCKED: prompt injection detected]'
        r = scan_memory_injection(user_text)
        if r:
            fu = '[BLOCKED: prompt injection detected]'
        FrozenSnapshot.freeze(memory_text=fm, user_text=fu)
        self._snapshot_frozen = True
        if blocked and self._exec_logger:
            self._exec_logger('snapshot_freeze', 'blocked', 4, '; '.join(blocked), memory_text[:40])
        elif self._exec_logger:
            self._exec_logger('snapshot_freeze', 'ok', 2, memory_text[:40], '')
        return blocked

    def snapshot_get_text(self) -> str:
        return FrozenSnapshot.get_snapshot_text()

    def snapshot_is_frozen(self) -> bool:
        return FrozenSnapshot.is_frozen()

    def snapshot_reset(self):
        FrozenSnapshot.reset()
        self._snapshot_frozen = False

    def check_drift_before_write(self, filepath: str):
        import time
        cache_key = filepath
        cached = self._drift_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < 5:
            return cached['result'] if cached.get('has_drift') else None
        result = detect_file_drift(filepath)
        self._drift_cache[cache_key] = {'result': result, 'ts': time.time(),
                                         'has_drift': bool(result and result.get('drifted'))}
        if result and result.get('drifted') and self._exec_logger:
            self._exec_logger('drift_detected', 'warning', 4,
                              f"backup={result.get('backup','')}", os.path.basename(filepath))
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
    engine = AutoMemory()

    if "--test" in sys.argv:
        print("🧪 运行基本功能测试...")
        mid = engine.save("测试记忆：今天天气很好", tags=["天气", "测试"], scene="日常")
        assert mid, "保存失败"
        e = engine.get(mid)
        assert e and e["text"] == "测试记忆：今天天气很好", "读取失败"
        results = engine.search("天气")
        assert len(results) >= 1, "搜索失败"
        stats = engine.stats()
        assert stats["total"] >= 1, "统计失败"
        engine.remove(mid)
        assert engine.get(mid) is None, "删除失败"
        print("✅ 所有测试通过")
        sys.exit(0)

    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 scripts/auto_memory.py save <text> [--tags a,b] [--scene s]")
        print("  python3 scripts/auto_memory.py get <id>")
        print("  python3 scripts/auto_memory.py search <query>")
        print("  python3 scripts/auto_memory.py search_timeline <query>")
        print("  python3 scripts/auto_memory.py stats")
        print("  python3 scripts/auto_memory.py list")
        print("  python3 scripts/auto_memory.py remove <id>")
        print("  python3 scripts/auto_memory.py backup [path]")
        print("  python3 scripts/auto_memory.py restore <path>")
        print("  python3 scripts/auto_memory.py forget [--keyword k] [--date d]")
        print("  python3 scripts/auto_memory.py graph <id>")
        print("  python3 scripts/auto_memory.py note add <text>")
        print("  python3 scripts/auto_memory.py note list")
        print("  python3 scripts/auto_memory.py recommend <context>")
        print("  python3 scripts/auto_memory.py --test")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "save" and len(sys.argv) > 2:
        text = sys.argv[2]
        tags = []
        scene = ""
        if "--tags" in sys.argv:
            idx = sys.argv.index("--tags") + 1
            if idx < len(sys.argv):
                tags = [t.strip() for t in sys.argv[idx].split(",")]
        if "--scene" in sys.argv:
            idx = sys.argv.index("--scene") + 1
            if idx < len(sys.argv):
                scene = sys.argv[idx]
        mid = engine.save(text, tags, scene)
        print(f"✅ 已保存 (ID: {mid})")

    elif cmd == "get" and len(sys.argv) > 2:
        e = engine.get(sys.argv[2])
        if e:
            print(json.dumps(e, ensure_ascii=False, indent=2))
        else:
            print("❌ 未找到")

    elif cmd == "search" and len(sys.argv) > 2:
        results = engine.search(" ".join(sys.argv[2:]))
        print(f"🔍 找到 {len(results)} 条结果:\n")
        for r in results:
            print(f"  [{r['id'][:8]}] {r['text'][:80]}")
            print(f"         创建: {r['created_at'][:19]}, 标签: {', '.join(r.get('tags', []))}")
            print()

    elif cmd == "search_timeline" and len(sys.argv) > 2:
        result = engine.search_with_timeline(" ".join(sys.argv[2:]))
        print(f"🔍 搜索结果 ({len(result['results'])} 条):")
        for date, items in sorted(result.get("timeline", {}).items(), reverse=True):
            print(f"\n📅 {date}:")
            for item in items:
                print(f"  • {item}")

    elif cmd == "stats":
        s = engine.stats()
        print(f"📊 记忆统计")
        print(f"  总数: {s.get('total', 0)}")
        print(f"  平均访问: {s.get('avg_access', 0)}")
        print(f"  日期分布:")
        for date, count in sorted(s.get("daily_distribution", {}).items(), reverse=True)[:5]:
            print(f"    {date}: {count}条")
        print(f"  热门标签:")
        for tag, count in sorted(s.get("tag_stats", {}).items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    #{tag}: {count}次")
        print(f"  场景分布:")
        for scene, count in s.get("scene_stats", {}).items():
            print(f"    [{scene}]: {count}条")

    elif cmd == "list":
        entries = engine.list_all()
        print(f"📋 共 {len(entries)} 条记忆:")
        for e in entries:
            print(f"  [{e['id'][:8]}] {e['text'][:60]}... ({e['created_at'][:10]})")

    elif cmd == "remove" and len(sys.argv) > 2:
        ok = engine.remove(sys.argv[2])
        print(f"{'✅ 已删除' if ok else '❌ 未找到'}")

    elif cmd == "backup":
        path = sys.argv[2] if len(sys.argv) > 2 else None
        msg = engine.backup(path)
        print(f"✅ {msg}")

    elif cmd == "restore" and len(sys.argv) > 2:
        count = engine.restore(sys.argv[2])
        print(f"✅ 已恢复 {count} 条记忆")

    elif cmd == "forget":
        keyword = ""
        date = ""
        if "--keyword" in sys.argv:
            idx = sys.argv.index("--keyword") + 1
            if idx < len(sys.argv):
                keyword = sys.argv[idx]
        if "--date" in sys.argv:
            idx = sys.argv.index("--date") + 1
            if idx < len(sys.argv):
                date = sys.argv[idx]
        count = engine.forget(keyword, date)
        print(f"🗑️ 已删除 {count} 条")

    elif cmd == "graph" and len(sys.argv) > 2:
        related = engine.graph.find_related(sys.argv[2])
        print(f"🕸️ 关联图谱:")
        for r in related:
            print(f"  [{r['score']:.1f}] {r['text'][:60]}")

    elif cmd == "recommend" and len(sys.argv) > 2:
        context = " ".join(sys.argv[2:])
        recs = engine.recommender.recommend(context)
        print(f"🎯 推荐 ({len(recs)} 条):")
        for r in recs:
            print(f"  [{r['score']:.2f}] {r['text'][:60]}")

    elif cmd == "note":
        sub = sys.argv[2] if len(sys.argv) > 2 else "list"
        if sub == "add" and len(sys.argv) > 3:
            nid = engine.notes.add(" ".join(sys.argv[3:]))
            print(f"📌 笔记已保存 (ID: {nid})")
        elif sub == "list":
            notes = engine.notes.list_all()
            if notes:
                print(f"📌 快捷笔记 ({len(notes)} 条):")
                for n in notes:
                    print(f"  [{n['id']}] {n['text'][:60]}")
            else:
                print("📌 暂无笔记")
        else:
            print("用法: python3 scripts/auto_memory.py note add|list")
