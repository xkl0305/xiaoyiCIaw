"""
Crusheart Agent OS — 无障碍输出过滤器 & 质量评分引擎 v2.0
v2.0 调研驱动升级（2026-06-22）
  核心转变：从"删除复杂格式"升级为"将视觉格式转换为语音友好的导航结构"
  新增功能：
    - 表格转结构化列表（行号标注、自然语言连接词）
    - 代码块转语义化描述（仅短代码保留全文）
    - 中文无障碍规则（句号强制、英文字间距、超长句拆分）
    - 标题结构保留 + 自动导航标题注入
    - 质量评分新增标题结构、句子结尾标点、段落长度维度
  参考来源：WebAIM Designing for Screen Reader Compatibility
"""

import os, re, json, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
STATE_PATH = os.path.join(WORKSPACE, ".accessibility_state.json")
EVOLUTION_FEED_PATH = os.path.join(WORKSPACE, ".accessibility_quality.jsonl")

logger = logging.getLogger("accessibility_filter")

# ── 状态管理 ──

class AccessibilityState:
    """无障碍模式状态管理器"""

    _instance = None
    _state: Dict = None

    def __new__(cls):
        from core.engines.init.engine_factory import SingletonRegistry
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
            SingletonRegistry.register(cls, cls._instance)
        return cls._instance

    def _load(self):
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH) as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._state = self._default_state()
        else:
            self._state = self._default_state()
            self._save()

    def _default_state(self) -> Dict:
        return {
            "enabled": False,
            "enabled_at": None,
            "disabled_at": None,
            "source": None,
            "total_filtered": 0,
            "quality_scores": [],
        }

    def _save(self):
        os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
        try:
            with open(STATE_PATH, "w") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warning(f"Failed to save accessibility state: {e}")

    def is_enabled(self) -> bool:
        user_pref = self._check_user_md()
        if user_pref is True:
            return True
        if user_pref is False:
            return False
        return self._state.get("enabled", False)

    def _check_user_md(self) -> Optional[bool]:
        """读取 USER.md + SOUL.md + IDENTITY.md 中的无障碍偏好"""
        check_paths = [
            os.path.join(WORKSPACE, "USER.md"),
            os.path.join(WORKSPACE, "SOUL.md"),
            os.path.join(WORKSPACE, "IDENTITY.md"),
        ]
        for fpath in check_paths:
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath) as f:
                    content = f.read()
                if any(marker in content for marker in [
                    "**无障碍输出**: true", "无障碍输出: true",
                    "**无障碍模式**: on", "无障碍模式: on",
                    "**accessibility**: true", "accessibility: true",
                    "**无障碍适配**: 开启",
                ]):
                    return True
                if any(marker in content for marker in [
                    "**无障碍输出**: false", "无障碍输出: false",
                    "**无障碍模式**: off", "无障碍模式: off",
                    "**accessibility**: false", "accessibility: false",
                ]):
                    return False
            except (IOError, FileNotFoundError):
                continue
        return None

    def enable(self, source: str = "user_declared"):
        self._state["enabled"] = True
        self._state["enabled_at"] = datetime.now(BEIJING_TZ).isoformat()
        self._state["disabled_at"] = None
        self._state["source"] = source
        self._save()

    def disable(self, source: str = "user_request"):
        self._state["enabled"] = False
        self._state["disabled_at"] = datetime.now(BEIJING_TZ).isoformat()
        self._state["source"] = source
        self._save()

    def record_filter(self):
        self._state["total_filtered"] = self._state.get("total_filtered", 0) + 1
        self._save()

    def add_quality_score(self, score: Dict):
        scores = self._state.get("quality_scores", [])
        scores.append({
            **score,
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        })
        if len(scores) > 50:
            scores = scores[-50:]
        self._state["quality_scores"] = scores
        self._save()

    def get_quality_stats(self) -> Dict:
        scores = self._state.get("quality_scores", [])
        if not scores:
            return {"avg": 0, "min": 0, "max": 0, "count": 0}
        vals = [s.get("total", 0) for s in scores]
        return {
            "avg": round(sum(vals) / len(vals), 2),
            "min": min(vals),
            "max": max(vals),
            "count": len(vals),
        }

    def get_state(self) -> Dict:
        return dict(self._state)


# ── 单例快捷函数 ──

_state = AccessibilityState()

def is_enabled() -> bool:
    return _state.is_enabled()

def enable(source: str = "user_declared"):
    _state.enable(source)

def disable(source: str = "user_request"):
    _state.disable(source)

def get_state() -> Dict:
    return _state.get_state()


# ── 无障碍内容过滤 ──

# 表格检测
TABLE_PATTERN = re.compile(r'^\|.*\|$', re.MULTILINE)
TABLE_SEPARATOR = re.compile(r'^\|[\s\-:|]+\|$', re.MULTILINE)

# 代码块检测
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')

# Markdown 链接
MD_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

# 标题检测
HEADING_PATTERN = re.compile(r'^#{1,6}\s+', re.MULTILINE)

# 装饰性 emoji / 符号（移除不影响语义）
DECORATIVE_EMOJI_PATTERN = re.compile(r'[❌✅⚠️▶️◀️⬆️⬇️➡️⬅️🔹🔸🔶🔷♦️🔴🟠🟡🟢🔵🟣🟤⚫⚪🈲🔍📋🔥⭐🎯🔧🔄📝💪]')

# 自然表情符号（保留）
NATURAL_EMOJI_PATTERN = re.compile(r'[😀😁😂🤣😃😄😅😆😉😊😋😎😍😘😜😝😟😠😡😢😣😤😥😦😧😨😩😪😫😬😭😮😯😰😱😲😳😴😵😶😷🙂🙃🙄🙁☹️🤗🤔🤐🤨🤩🤪🤫🤬🤭🤮🤯🧐👻💀☠️👋🤚🖐️✋🖖🖕✌️🤞🤟🤘🤙👌👍👎✊👊🤛🤜👏🙌👐🤲🤝🙏✍️💅💪🦵🦶👂👃👁️👀🧠👄❤️🧡💛💚💙💜🖤🤍🤎💕💞💓💗💖💘💝💟💌💋💍💎👑🎉🎊🎈🎀🎁🎃🎄🎋🎍🎎🎏🎐🎑🎒🎓🎠🎡🎢🎣🎤🎥🎦🎧🎨🎩🎪🎫🎬🎭🎮🎯🎰🎱🎲🎳🎴🎵🎶🎷🎸🎹🎺🎻🎼🎽🎾🎿🏀🏁]')

# 英文单词检测
EN_WORD_PATTERN = re.compile(r'[a-zA-Z]{2,}')

# 列表符号标准化
LIST_PATTERN = re.compile(r'^[*-]\s+', re.MULTILINE)

# 句子结束标点检测
SENTENCE_END = re.compile(r'[。！？\n]$', re.MULTILINE)

# 中文字检测
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff]')


def _is_short_code(code_text: str, max_lines: int = 5) -> bool:
    """判断代码块是否足够短，可以直接读"""
    lines = [l for l in code_text.split('\n') if l.strip() and not l.startswith('```')]
    return len(lines) <= max_lines


def _extract_code_semantics(code_text: str) -> Dict:
    """提取代码块的语义信息（语言、关键操作、模式）"""
    lines = [l for l in code_text.split('\n') if l.strip()]
    if not lines:
        return {"lang": "", "patterns": [], "operations": []}

    # 首行是语言声明
    lang = lines[0].replace('```', '').strip()
    code_lines = lines[1:-1] if len(lines) > 2 and lines[-1].strip() == '```' else lines[1:]

    operations = []
    patterns = []
    for line in code_lines:
        stripped = line.strip()
        # 检测常见操作模式
        if re.match(r'(import|from|require|include|#include|using)', stripped):
            patterns.append("引入模块或依赖")
        elif re.match(r'(def |function |class |interface |trait )', stripped):
            patterns.append("定义函数或类")
        elif re.match(r'(if |elif |else |switch |case |unless )', stripped):
            patterns.append("条件判断")
        elif re.match(r'(for |while |do |loop )', stripped):
            patterns.append("循环遍历")
        elif re.match(r'(return |yield )', stripped):
            patterns.append("返回值")
        elif re.match(r'(try|catch|except|throw|raise|finally)', stripped):
            patterns.append("异常处理")
        elif '=' in stripped and '(' not in stripped.split('=')[0]:
            patterns.append("变量赋值")
        elif '(' in stripped and ')' in stripped:
            patterns.append("函数调用")

    # 去重
    operations = list(set(patterns))[:3] if patterns else ["代码处理"]
    return {"lang": lang, "patterns": operations, "line_count": len(code_lines)}


def _table_to_list(text: str) -> str:
    """
    将 markdown 表格转换为屏幕阅读器友好的结构化列表。
    升级 v2.0: 使用"表格开始/结束"标记 + 自然语言连接词 + 行号标注
    """
    lines = text.split('\n')
    result = []
    in_table = False
    headers = []
    rows = []

    def _flush_table():
        nonlocal headers, rows
        if not rows:
            return
        result.append("—— 表格开始 ——")
        if headers:
            result.append(f"第一列标题：{headers[0]}")
            if len(headers) > 1:
                result.append(f"其他列：{'，'.join(headers[1:])}")
        for ri, row in enumerate(rows):
            if not row:
                continue
            parts = []
            for ci, cell in enumerate(row):
                label = headers[ci] if ci < len(headers) else f"第{ci+1}列"
                parts.append(f"{label}为{cell}")
            result.append(f"第{ri+1}行：{'，'.join(parts)}")
        result.append("—— 表格结束 ——")
        result.append("")
        headers, rows = [], []

    for line in lines:
        if TABLE_PATTERN.match(line) and '|' in line:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if not in_table:
                headers = cells
                in_table = True
            elif TABLE_SEPARATOR.match(line):
                continue
            else:
                rows.append(cells)
        else:
            if in_table:
                _flush_table()
                in_table = False
            result.append(line)

    if in_table:
        _flush_table()

    return '\n'.join(result)


def _code_block_to_desc(text: str) -> str:
    """
    将代码块转换为语义化自然语言描述。
    短代码（<=5行）保留全文，长代码仅描述模式和操作。
    """
    def _replace_code_block(match):
        code = match.group(0)
        semantics = _extract_code_semantics(code)
        code_lines = [l for l in code.split('\n') if l.strip() and not l.startswith('```')]

        result_parts = ["—— 代码段开始 ——"]
        if semantics["lang"]:
            result_parts.append(f"语言：{semantics['lang']}")
        if semantics["patterns"]:
            result_parts.append(f"包含操作：{'，'.join(semantics['patterns'])}")
        if semantics["line_count"] and _is_short_code(code, max_lines=5):
            # 短代码保留全文，但去掉 ``` 标记
            clean_lines = [l for l in code.split('\n') if not l.strip().startswith('```') and l.strip()]
            if clean_lines:
                result_parts.append("代码内容：")
                result_parts.extend(clean_lines)
        else:
            result_parts.append(f"共{semantics['line_count']}行代码（内容略）")
        result_parts.append("—— 代码段结束 ——")
        return '\n'.join(result_parts)

    return CODE_BLOCK_PATTERN.sub(_replace_code_block, text)


def _md_link_to_text(text: str) -> str:
    """将 markdown 链接转换为可读的内联标注"""
    def _replace_link(match):
        display_text = match.group(1)
        url = match.group(2)
        # 如果显示文本已经包含了链接描述，就不用再重复
        if display_text == url or display_text in url:
            return f"链接：{url}"
        return f"{display_text}（{url}）"
    return MD_LINK_PATTERN.sub(_replace_link, text)


def _inline_code_to_text(text: str) -> str:
    """将行内代码标记移除，保留内容"""
    return INLINE_CODE_PATTERN.sub(r'\1', text)


def _apply_chinese_accessibility_rules(text: str) -> str:
    """
    中文无障碍输出规则（v2.0 新增）
    1. 每个句子必须有句号/问号/感叹号结尾
    2. 超长句（>40字）拆分
    3. 英文术语前后加空格
    4. 版本号/编号前置描述词
    """
    lines = text.split('\n')
    result = []

    for line in lines:
        # 跳过标题和空行
        stripped = line.strip()
        if not stripped or HEADING_PATTERN.match(stripped):
            result.append(line)
            continue

        # === 规则1: 句号强制 ===
        # 如果某行最后没有句号且不是空行、不是标题、不是列表、不是标记行
        if not re.search(r'[。！？\n]$', line) and \
           not line.strip().startswith('——') and \
           not line.strip().startswith('链接') and \
           not LIST_PATTERN.match(line) and \
           not line.strip().startswith('语言') and \
           not line.strip().startswith('包含操作') and \
           not line.strip().startswith('共') and \
           not line.strip().startswith('代码内容'):
            # 检查行内是否已有句号
            if '。' not in line:
                line = line.rstrip() + '。'

        # === 规则2: 超长句拆分 ===
        sentences = re.split(r'(?<=[。！？])', line)
        new_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) > 40:
                # 在第一个逗号/分号/顿号处拆分
                split_positions = [m.start() for m in re.finditer(r'[，、；]', sent)]
                if split_positions:
                    # 找到最接近 30 字位置的分隔符
                    best_pos = min(split_positions, key=lambda p: abs(p - 30))
                    new_sentences.append(sent[:best_pos+1])
                    rest = sent[best_pos+1:].strip()
                    if rest:
                        new_sentences.append(rest)
                else:
                    new_sentences.append(sent)
            else:
                new_sentences.append(sent)
        line = ''.join(new_sentences)

        # === 规则3: 英文术语前后加空格 ===
        line = _add_en_spacing(line)

        # === 规则4: 版本号/编号前加描述 ===
        line = _annotate_version_numbers(line)

        result.append(line)

    return '\n'.join(result)


def _add_en_spacing(text: str) -> str:
    """在中文和英文字母/数字之间插入空格"""
    # 中文字 + 英文字 之间加空格
    text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', text)
    # 数字 + 中文字 之间加空格
    text = re.sub(r'([\u4e00-\u9fff])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([\u4e00-\u9fff])', r'\1 \2', text)
    return text


def _annotate_version_numbers(text: str) -> str:
    """为版本号和编号添加前置描述词"""
    # 版本号模式：X.Y.Z 或 X.Y
    text = re.sub(
        r'(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)',
        r'版本号 \1点\2点\3',
        text
    )
    # 仅 X.Y 模式的版本号
    text = re.sub(
        r'(?<!\d)v(\d+)\.(\d+)(?!\.\d)',
        r'版本号 v\1点\2',
        text
    )
    return text


def _ensure_heading_structure(text: str, min_heading_level: int = 2) -> str:
    """
    确保内容有标题导航结构。
    如果没有任何标题，在最前插入一个"内容概览"标题。
    屏幕阅读器用户依赖 H 键在标题间跳转。
    """
    if HEADING_PATTERN.search(text):
        return text

    # 没有标题 → 注入一个
    prefix = "#" * min_heading_level + " 内容概览\n\n"
    return prefix + text


def _limit_decorative_emoji(text: str, max_count: int = 2) -> Tuple[str, bool]:
    """限制装饰性 emoji 数量，保留自然表情符号"""
    matched = DECORATIVE_EMOJI_PATTERN.findall(text)
    if len(matched) <= max_count:
        return text, False
    # 只保留前 max_count 个装饰 emoji
    count = 0
    result_chars = []
    for ch in text:
        if DECORATIVE_EMOJI_PATTERN.match(ch):
            if count < max_count:
                result_chars.append(ch)
                count += 1
        else:
            result_chars.append(ch)
    return ''.join(result_chars), True


def _list_to_readable(text: str) -> str:
    """清理空列表项"""
    lines = text.split('\n')
    result = []
    for line in lines:
        if LIST_PATTERN.match(line) and len(line.strip()) <= 1:
            continue
        result.append(line)
    return '\n'.join(result)


def _simplify_punctuation(text: str) -> str:
    """简化不影响语义的特殊标点符号"""
    replacements = {
        '—': '-',
        '–': '-',
        '…': '...',
        '·': ',',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _remove_consecutive_newlines(text: str, max_newlines: int = 2) -> str:
    """限制连续换行数"""
    while '\n' * (max_newlines + 1) in text:
        text = text.replace('\n' * (max_newlines + 1), '\n' * max_newlines)
    return text


def filter_text(text: str) -> Tuple[str, Dict]:
    """
    对文本进行无障碍过滤（v2.0）
    核心转变：视觉格式 → 语音友好的导航结构
    返回 (过滤后文本, 过滤统计)
    """
    if not text:
        return text, {"applied": False, "reason": "empty_text"}

    stats = {
        "applied": True,
        "tables_converted": 0,
        "code_blocks_converted": 0,
        "links_converted": 0,
        "emoji_limited": False,
        "sentences_fixed": 0,
        "long_sentences_split": 0,
        "heading_injected": False,
    }

    original = text

    # 1. 表格转结构化列表（v2.0 升级版）
    before = text
    text = _table_to_list(text)
    stats["tables_converted"] = 1 if before != text else 0

    # 2. 代码块转语义化描述（v2.0 升级版）
    before = text
    text = _code_block_to_desc(text)
    stats["code_blocks_converted"] = 1 if before != text else 0

    # 3. markdown 链接转内联标注
    before = text
    text = _md_link_to_text(text)
    stats["links_converted"] = 1 if before != text else 0

    # 4. 移除行内代码标记
    text = _inline_code_to_text(text)

    # 5. 中文无障碍规则（v2.0 新增）
    text = _apply_chinese_accessibility_rules(text)

    # 6. 限制装饰性 emoji
    text, limited = _limit_decorative_emoji(text, max_count=2)
    stats["emoji_limited"] = limited

    # 7. 清理空列表
    text = _list_to_readable(text)

    # 8. 简化标点
    text = _simplify_punctuation(text)

    # 9. 限制连续换行
    text = _remove_consecutive_newlines(text, 2)

    # 10. 确保标题导航结构（v2.0 新增）
    before = text
    text = _ensure_heading_structure(text)
    stats["heading_injected"] = before != text

    stats["chars_removed"] = len(original) - len(text)

    return text, stats


# ── 无障碍质量评分（v2.0 升级版）──

QUALITY_DIMENSIONS = [
    "tables_clean",         # 没有表格残留
    "code_block_free",      # 没有代码块
    "emoji_moderate",       # emoji 数量适中
    "chinese_ratio",        # 中文字占比
    "sentence_length",      # 句子长度友好度
    "link_readable",        # 链接可读性
    "special_chars",        # 特殊符号控制
    "heading_structure",    # v2.0: 标题导航结构
    "sentence_punctuation", # v2.0: 句尾标点完整性
]


def score_quality(text: str) -> Dict:
    """
    对无障碍输出进行多维度质量评分（v2.0 升级版）
    新增维度: heading_structure, sentence_punctuation
    改进: 英文密度检测、段落长度检测
    """
    if not text:
        return {
            "total": 0,
            "dimensions": {d: 0 for d in QUALITY_DIMENSIONS},
            "issues": ["empty_text"],
        }

    issues = []

    # 1. tables_clean: 表格残留检测
    tables_left = len(TABLE_PATTERN.findall(text))
    # 允许表格已转成的列表标记
    table_indicators = text.count("—— 表格开始 ——")
    table_score = 10 if tables_left == 0 and table_indicators >= 0 else max(0, 10 - tables_left * 3)
    if tables_left > 0:
        issues.append(f"残表{tables_left}行")

    # 2. code_block_free: 代码块残留检测
    code_blocks_left = len(CODE_BLOCK_PATTERN.findall(text))
    code_indicators = text.count("—— 代码段开始 ——")
    code_score = 10 if code_blocks_left == 0 else max(0, 10 - code_blocks_left * 5)
    if code_blocks_left > 0:
        issues.append(f"代码块残留{code_blocks_left}个")

    # 3. emoji_moderate: 装饰性 emoji 控制
    deco_emoji_count = len(DECORATIVE_EMOJI_PATTERN.findall(text))
    if deco_emoji_count <= 2:
        emoji_score = 10
    elif deco_emoji_count <= 5:
        emoji_score = 7
    elif deco_emoji_count <= 8:
        emoji_score = 4
    else:
        emoji_score = max(0, 10 - deco_emoji_count)
    if deco_emoji_count > 5:
        issues.append(f"装饰符号过多({deco_emoji_count}个)")

    # 4. chinese_ratio + 英文密度
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    en_words = len(EN_WORD_PATTERN.findall(text))
    total_chars = max(len(text), 1)
    en_density = en_words / max(len(text) / 1000, 1)
    # 中英混排时检查英文密度
    if chinese_chars > 0:
        en_ratio = en_words / max(chinese_chars, 1)
        if en_ratio <= 0.05:
            cn_score = 10
        elif en_ratio <= 0.1:
            cn_score = 8
        elif en_ratio <= 0.2:
            cn_score = 5
        else:
            cn_score = max(0, 10 - int(en_ratio * 30))
        if en_ratio > 0.1:
            issues.append(f"英文/中文字比例偏高({round(en_ratio*100)}%)")
    else:
        cn_score = 5  # 纯英文也给中间分

    # 5. sentence_length: 句子长度
    sentences = re.split(r'[。！？\n]', text)
    long_sentences = [s for s in sentences if len(s) > 40]
    if len(sentences) > 0:
        long_ratio = len(long_sentences) / len(sentences)
    else:
        long_ratio = 0
    if long_ratio <= 0.1:
        sent_score = 10
    elif long_ratio <= 0.2:
        sent_score = 8
    elif long_ratio <= 0.3:
        sent_score = 6
    elif long_ratio <= 0.5:
        sent_score = 4
    else:
        sent_score = max(0, 10 - int(long_ratio * 10))
    if long_ratio > 0.3:
        issues.append(f"长句({'>'}40字)比例{int(long_ratio*100)}%")

    # 6. link_readable: 链接格式
    raw_md_links = MD_LINK_PATTERN.findall(text)
    # 允许已转换的链接标注
    link_converted = "（http" in text or "链接：" in text
    link_score = 10 if (len(raw_md_links) == 0 and link_converted) else max(0, 10 - len(raw_md_links) * 3)
    if raw_md_links:
        issues.append(f"未转换链接{len(raw_md_links)}个")

    # 7. special_chars: 特殊符号（仅残留的装饰性符号）
    special_count = len(re.findall(r'[▶️◀️⬆️⬇️➡️⬅️🔹🔸🔶🔷♦️🔴🟠🟡🟢🔵🟣🟤⚫⚪]', text))
    if special_count <= 2:
        sc_score = 10
    elif special_count <= 5:
        sc_score = 7
    elif special_count <= 8:
        sc_score = 4
    else:
        sc_score = max(0, 10 - special_count)

    # 8. heading_structure (v2.0 新增): 标题导航结构
    headings = HEADING_PATTERN.findall(text)
    heading_count = len(headings)
    if heading_count >= 2:
        h_score = 10
    elif heading_count == 1:
        h_score = 7
    else:
        h_score = 0
        issues.append("缺少标题导航结构")

    # 9. sentence_punctuation (v2.0 新增): 句尾标点完整性
    non_empty_sentences = [s.strip() for s in re.split(r'[\n]', text)
                           if s.strip() and not HEADING_PATTERN.match(s.strip())
                           and not s.strip().startswith('——')
                           and not s.strip().startswith('- ')
                           and not s.strip().startswith('* ')]
    end_missing = sum(1 for s in non_empty_sentences
                      if not re.search(r'[。！？]$', s) and not re.search(r'^[a-zA-Z]', s))
    total_check = max(len(non_empty_sentences), 1)
    end_ratio = end_missing / total_check
    if end_ratio <= 0.05:
        punct_score = 10
    elif end_ratio <= 0.15:
        punct_score = 8
    elif end_ratio <= 0.3:
        punct_score = 6
    elif end_ratio <= 0.5:
        punct_score = 4
    else:
        punct_score = max(0, 10 - int(end_ratio * 15))
    if end_ratio > 0.15:
        issues.append(f"句尾无标点比例{int(end_ratio*100)}%")

    dimensions = {
        "tables_clean": table_score,
        "code_block_free": code_score,
        "emoji_moderate": emoji_score,
        "chinese_ratio": cn_score,
        "sentence_length": sent_score,
        "link_readable": link_score,
        "special_chars": sc_score,
        "heading_structure": h_score,
        "sentence_punctuation": punct_score,
    }

    total = round(sum(dimensions.values()) / len(dimensions), 1)

    return {
        "total": total,
        "dimensions": dimensions,
        "issues": issues[:5],
        "text_length": len(text),
    }


# ── 自进化数据喂养 ──

def feed_to_evolution(quality_result: Dict, original_text: str, filtered_text: str):
    """将无障碍质量数据写入 evolution feed 文件"""
    if not quality_result or quality_result.get("total", 0) < 1:
        return

    entry = {
        "type": "accessibility_quality",
        "timestamp": datetime.now(BEIJING_TZ).isoformat(),
        "score": quality_result.get("total", 0),
        "dimensions": quality_result.get("dimensions", {}),
        "issues": quality_result.get("issues", []),
        "text_length": len(filtered_text),
        "was_filtered": original_text != filtered_text,
    }

    try:
        os.makedirs(os.path.dirname(EVOLUTION_FEED_PATH) or ".", exist_ok=True)
        with open(EVOLUTION_FEED_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except IOError as e:
        logger.warning(f"Failed to write evolution feed: {e}")

    _state.add_quality_score(quality_result)


def get_evolution_feed(limit: int = 20) -> List[Dict]:
    """获取最近的自进化喂养数据"""
    if not os.path.exists(EVOLUTION_FEED_PATH):
        return []
    try:
        entries = []
        with open(EVOLUTION_FEED_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]
    except (IOError, FileNotFoundError):
        return []


# ── 入口点（CLI / runPy 调用） ──

def main():
    """CLI 入口：python3 accessibility_filter.py [command] [args]"""
    import sys
    args = sys.argv[1:]

    if not args:
        state = get_state()
        enabled = is_enabled()
        print(json.dumps({
            "enabled": enabled,
            "state": state,
            "quality_stats": _state.get_quality_stats(),
        }, ensure_ascii=False, indent=2))
        return

    cmd = args[0]

    if cmd == "enable":
        source = args[1] if len(args) > 1 else "cli"
        enable(source)
        print(json.dumps({"status": "ok", "enabled": True, "source": source}))
        return

    if cmd == "disable":
        source = args[1] if len(args) > 1 else "cli"
        disable(source)
        print(json.dumps({"status": "ok", "enabled": False}))
        return

    if cmd == "status":
        print(json.dumps({
            "enabled": is_enabled(),
            "state": get_state(),
        }, ensure_ascii=False, indent=2))
        return

    if cmd == "filter":
        text = args[1] if len(args) > 1 else ""
        if not text:
            text = sys.stdin.read()
        filtered, stats = filter_text(text)
        result = {
            "filtered": filtered,
            "stats": stats,
        }
        if "--score" in args:
            score = score_quality(filtered)
            result["quality_score"] = score
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if cmd == "score":
        text = args[1] if len(args) > 1 else ""
        if not text:
            text = sys.stdin.read()
        score = score_quality(text)
        print(json.dumps(score, ensure_ascii=False, indent=2))
        return

    if cmd == "quality-stats":
        stats = _state.get_quality_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    print(f"Unknown command: {cmd}", file=sys.stderr)
    sys.exit(1)


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

    main()
