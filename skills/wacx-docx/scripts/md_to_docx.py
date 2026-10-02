#!/usr/bin/env python3
r"""
md_to_docx.py — 通用 Markdown 转 DOCX 格式化转换器（v3.1.0）

格式规范（与用户DOCX基准一致）：
- 全文宋体小四(12pt)，左对齐
- 小说名/卷/章名加粗（章名前后分页）
- 全文首行缩进2字符(304800 EMU)，空行不缩进
- 行间距1.5倍（乘数模式）
- 段前段后间距均为0
- 每章末尾插入空段落+br type=page分页符（首章前无分页）
- 标点规范化（正文/标题）：ASCII 引号/标点 → 中文全角
- 代码块保留原样（不规范化、不缩进）
- MD 段落按空行分段，单换行合并（强制换行 \\ 或行尾两空格 保留为行内 <w:br/>）

MD 语法映射：
- # H1 / ## H2 / ### H3         → 标题段落（章名/卷名 加粗，章名匹配时加分页）
- 普通段落（空行分隔）           → 正文段落（首行缩进）
- 连续行（单换行）               → 合并为同一段落（行内 <w:br/> 仅在强制换行时插入）
- **bold** / *italic* / `code`   → 文本内 run 样式
- ~~strike~~                    → 文本内删除线 run
- - / * / 1. 列表                → 列表段落
- ```code``` 代码块              → 等宽字体段落块（不缩进、不规范化）
- > 引用                         → 缩进引用段落
- --- 分隔线                     → 空段落
- ![](url) 图片                  → 占位文字【图片】（DOCX不嵌入）
- [text](url) 链接                → 显示文字（DOCX不保留超链接）

用法:
    python md_to_docx.py input.md -o output.docx
    python md_to_docx.py input.md --title "书名"
    python md_to_docx.py input.md --no-punct-norm   # 关闭标点规范化
"""

import argparse
import re
import sys
from pathlib import Path

# 依赖守护：mystune/python-docx 缺失时给出友好提示，避免裸崩溃
try:
    import mistune
except ImportError:
    print("✗ 缺少依赖 mistune，请先执行：pip install mistune")
    sys.exit(4)
try:
    from docx import Document
    from docx.shared import Pt, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml.ns import qn, nsdecls
    from docx.oxml import parse_xml
except ImportError:
    print("✗ 缺少依赖 python-docx，请先执行：pip install python-docx")
    sys.exit(4)


# ── 格式配置（匹配用户DOCX基准）──
FONT_NAME_ZH = "宋体"
FONT_NAME_MONO = "Courier New"
FONT_SIZE_PT = 12
LINE_SPACING_MULTIPLIER = 1.5
FIRST_INDENT_EMU = Emu(304800)
ALIGNMENT = WD_ALIGN_PARAGRAPH.LEFT

# ── 章节标题检测 ──
CHAPTER_PATTERNS = [
    r"^第[一二三四五六七八九十百千万零\d]+[章节回].*$",
    r"^第[一二三四五六七八九十百千万零\d]+\s*[卷册编].*$",
    r"^[春夏秋冬]之幕.*$",
    r"^[第][一二三四五六七八九十百千万]+[季度].*$",
]

# 书名检测软提示
TITLE_HINT_WORDS = {
    "记", "录", "传", "志", "志异",
    "之", "缘", "梦", "行", "事",
}


# ═══════════════════════════════════════════════════════════════
# 标点规范化模块（核心：覆盖 GB/T 15834 标点规范）
# ═══════════════════════════════════════════════════════════════

# ASCII → 中文全角 字符映射
PUNCT_MAP = {
    ",": "，",
    ".": "。",
    ";:": "；",   # 占位，下面会单独处理
    ";": "；",
    ":": "：",
    "?": "？",
    "!": "！",
    "(": "（",
    ")": "）",
    "[": "【",
    "]": "】",
    "~": "～",
}


def normalize_punctuation(text: str, preserve_english: bool = False,
                           prev_char: str = "", next_char: str = "") -> str:
    """
    规范化正文/标题中的 ASCII 标点为中文全角标点。

    规则（GB/T 15834 合规）：
    - ASCII 引号（" 和 '）→ 中文全角（"" 和 ''），用 toggle 状态机处理嵌套
    - ASCII 标点（,. ; : ? ! ( ) [ ]）→ 中文全角（，。；：？！（））
    - 连续 2 个 ASCII 短横（--）→ 中文破折号（——）
    - 连续 3 个英文点（...）→ 中文省略号（……）
    - 邮箱、URL、CJK 字符相邻时不替换

    Args:
        text: 原文
        preserve_english: True 时跳过标点替换（仅替换引号），用于英文段落保护
        prev_char: 上一个 token 的最后一个字符（用于跨 token CJK 上下文判断）
        next_char: 下一个 token 的第一个字符（同上）
    """
    if not text:
        return text

    # 1. 引号 toggle 处理（先做，避免被标点 map 误判）
    text = _normalize_quotes_toggle(text)

    if preserve_english:
        return text

    # 2. 邮箱/URL 保护（避免替换 URL 中的冒号等）
    protected = []
    last_end = 0
    for m in re.finditer(r"[a-zA-Z][\w.+-]*@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+|https?://\S+", text):
        protected.append(text[last_end:m.start()])
        protected.append("\x00" + m.group() + "\x00")
        last_end = m.end()
    protected.append(text[last_end:])
    text = "".join(protected)

    # 3. 破折号 / 省略号先做（避免被字符级映射破坏）
    text = re.sub(r"(?<!-)-{2}(?!-)", "——", text)
    text = re.sub(r"\.{3,}", "……", text)
    text = re.sub(
        r"([\u4e00-\u9fff，。！？：；、])\s*-\s*([\u4e00-\u9fff])",
        r"\1——\2",
        text,
    )

    # 4. 字符级 ASCII 标点 → 中文全角（含跨 token CJK 上下文）
    out = []
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch in PUNCT_MAP and _has_cjk_neighbor_ext(chars, i, prev_char, next_char):
            out.append(PUNCT_MAP[ch])
        else:
            out.append(ch)
    text = "".join(out)

    # 5. 还原 URL/邮箱占位符
    text = text.replace("\x00", "")

    return text


def _normalize_quotes_toggle(text: str) -> str:
    """ASCII " 和 ' → 中文全角，toggle 状态机。"""
    result = []
    in_double = False
    in_single = False
    for ch in text:
        if ch == '"':
            result.append("\u201d" if in_double else "\u201c")
            in_double = not in_double
        elif ch == "'":
            result.append("\u2019" if in_single else "\u2018")
            in_single = not in_single
        else:
            result.append(ch)
    return "".join(result)


def _has_cjk_neighbor_ext(chars: list, i: int, prev_char: str = "", next_char: str = "") -> bool:
    """检查 chars[i] 是否在 CJK 上下文中（含跨 token 上下文）。"""
    neighbors = [prev_char, next_char]
    if i > 0:
        neighbors.append(chars[i - 1])
    if i + 1 < len(chars):
        neighbors.append(chars[i + 1])
    for c in neighbors:
        if c and (_is_cjk(c) or _is_cjk_punct(c)):
            return True
    return False


def _is_cjk(c: str) -> bool:
    return "\u4e00" <= c <= "\u9fff"


def _is_cjk_punct(c: str) -> bool:
    """CJK 符号和标点区段（U+3000-U+303F）+ 全角 ASCII（U+FF00-U+FFEF）。"""
    return "\u3000" <= c <= "\u303f" or "\uff00" <= c <= "\uffef"


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def read_text_with_fallback(path: str) -> tuple:
    """多编码读取：UTF-8 BOM → UTF-8 → GBK → GB2312 → latin-1。"""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        f"无法用任何编码读取 {path}（已尝试 utf-8-sig/utf-8/gbk/gb2312/latin-1）"
    )


def strip_md_prefix(text: str) -> str:
    """去掉行首 markdown 标题前缀。"""
    return re.sub(r"^\s*#+\s*", "", text).strip()


def is_chapter_title(text: str) -> bool:
    """检查是否为章节标题。"""
    if not text:
        return False
    cleaned = text.strip().lstrip("-").strip().rstrip("-").strip()
    cleaned = strip_md_prefix(cleaned)
    if not cleaned:
        return False
    return any(re.match(p, cleaned) for p in CHAPTER_PATTERNS)


# ═══════════════════════════════════════════════════════════════
# DOCX 段落/字体底层
# ═══════════════════════════════════════════════════════════════

def make_rfonts_xml(font_name: str = FONT_NAME_ZH):
    return parse_xml(
        f'<w:rFonts {nsdecls("w")} w:eastAsia="{font_name}" w:ascii="{font_name}" w:hAnsi="{font_name}"/>'
    )


def make_mono_rfonts_xml():
    return parse_xml(
        f'<w:rFonts {nsdecls("w")} w:ascii="{FONT_NAME_MONO}" w:hAnsi="{FONT_NAME_MONO}"/>'
    )


def set_run_font(run, mono: bool = False, bold: bool = False, italic: bool = False,
                 strike: bool = False, size_pt: int = FONT_SIZE_PT):
    """统一设置 run 的字体属性。"""
    run.font.name = FONT_NAME_MONO if mono else FONT_NAME_ZH
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if strike:
        run.font.strike = True
    run._element.append(make_mono_rfonts_xml() if mono else make_rfonts_xml())


def apply_para_format(para, indent: bool = True):
    pf = para.paragraph_format
    pf.alignment = ALIGNMENT
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = LINE_SPACING_MULTIPLIER
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.first_line_indent = FIRST_INDENT_EMU if indent else Emu(0)


def add_para_with_text(doc, text: str, bold: bool = False, indent: bool = True,
                       normalize: bool = True, mono: bool = False, italic: bool = False):
    if normalize:
        text = normalize_punctuation(text)
    para = doc.add_paragraph()
    run = para.add_run(text)
    set_run_font(run, mono=mono, bold=bold, italic=italic)
    apply_para_format(para, indent=indent)
    return para


def add_empty_para(doc, indent: bool = False):
    para = doc.add_paragraph()
    apply_para_format(para, indent=indent)
    return para


def add_pagebreak_para(doc):
    para = doc.add_paragraph()
    apply_para_format(para, indent=False)
    run = para.add_run("")
    br_elem = parse_xml(f'<w:br {nsdecls("w")} w:type="page"/>')
    run._element.append(br_elem)
    return para


def add_linebreak_run(para):
    run = para.add_run("")
    br_elem = parse_xml(f'<w:br {nsdecls("w")}/>')
    run._element.append(br_elem)


# ═══════════════════════════════════════════════════════════════
# MD 节点 → DOCX 渲染
# ═══════════════════════════════════════════════════════════════

def _leaf_raw(tok):
    """获取 token 的扁平化 raw 字符串（递归到嵌套 children）。"""
    if not isinstance(tok, dict):
        return ""
    t = tok.get("type")
    if t in ("text", "codespan"):
        return tok.get("raw", "")
    if t in ("strong", "emphasis", "strikethrough", "link", "image"):
        return "".join(_leaf_raw(c) for c in tok.get("children", []))
    if t in ("linebreak", "softbreak"):
        return " "
    return ""


def render_inline(para, tokens, normalize: bool = True):
    """把 inline token 流渲染到已有段落中。"""
    tokens = tokens or []
    n = len(tokens)
    raws = [_leaf_raw(t) for t in tokens]

    for idx, tok in enumerate(tokens):
        t = tok.get("type") if isinstance(tok, dict) else None
        prev_char = raws[idx - 1][-1] if idx > 0 and raws[idx - 1] else ""
        next_char = raws[idx + 1][0] if idx + 1 < n and raws[idx + 1] else ""

        if t == "text":
            txt = tok.get("raw", "")
            if normalize:
                txt = normalize_punctuation(txt, prev_char=prev_char, next_char=next_char)
            run = para.add_run(txt)
            set_run_font(run)
        elif t == "strong":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, bold=True, normalize=normalize)
        elif t == "emphasis":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, italic=True, normalize=normalize)
        elif t == "strikethrough":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, strike=True, normalize=normalize)
        elif t == "codespan":
            txt = tok.get("raw", "")
            run = para.add_run(txt)
            set_run_font(run, mono=True)
        elif t == "link":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, normalize=normalize)
        elif t == "image":
            alt = tok.get("children", [{}])[0].get("raw", "图片") if tok.get("children") else "图片"
            run = para.add_run(f"【图片：{alt}】")
            set_run_font(run)
        elif t == "linebreak":
            add_linebreak_run(para)
        elif t == "softbreak":
            run = para.add_run(" ")
            set_run_font(run)
        else:
            txt = tok.get("raw", "")
            if txt:
                if normalize:
                    txt = normalize_punctuation(txt, prev_char=prev_char, next_char=next_char)
                run = para.add_run(txt)
                set_run_font(run)


def _render_inline_with_style(para, tokens, bold: bool = False, italic: bool = False,
                              strike: bool = False, normalize: bool = True):
    """递归渲染 inline tokens，应用指定 bold/italic/strike 样式。"""
    tokens = tokens or []
    n = len(tokens)
    raws = [_leaf_raw(t) for t in tokens]

    for idx, tok in enumerate(tokens):
        t = tok.get("type") if isinstance(tok, dict) else None
        prev_char = raws[idx - 1][-1] if idx > 0 and raws[idx - 1] else ""
        next_char = raws[idx + 1][0] if idx + 1 < n and raws[idx + 1] else ""

        if t == "text":
            txt = tok.get("raw", "")
            if normalize:
                txt = normalize_punctuation(txt, prev_char=prev_char, next_char=next_char)
            run = para.add_run(txt)
            set_run_font(run, bold=bold, italic=italic, strike=strike)
        elif t == "strong":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, bold=True, italic=italic, strike=strike, normalize=normalize)
        elif t == "emphasis":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, bold=bold, italic=True, strike=strike, normalize=normalize)
        elif t == "strikethrough":
            inner = tok.get("children", [])
            _render_inline_with_style(para, inner, bold=bold, italic=italic, strike=True, normalize=normalize)
        elif t == "codespan":
            run = para.add_run(tok.get("raw", ""))
            set_run_font(run, mono=True, bold=bold, italic=italic, strike=strike)
        elif t == "softbreak":
            run = para.add_run(" ")
            set_run_font(run, bold=bold, italic=italic, strike=strike)
        elif t == "linebreak":
            add_linebreak_run(para)
        else:
            txt = tok.get("raw", "")
            if txt:
                if normalize:
                    txt = normalize_punctuation(txt, prev_char=prev_char, next_char=next_char)
                run = para.add_run(txt)
                set_run_font(run, bold=bold, italic=italic, strike=strike)


def render_table(doc, node, normalize: bool = True):
    """把 mistune table token 渲染为带边框的 DOCX 表格。

    结构：table.children = [ table_head{children:[table_cell...]}, table_body{children:[table_row{children:[table_cell...]}, ...]} ]
    规则：表头行加粗；单元格宋体小四；左对齐；1.5 倍行距。
    """
    children = node.get("children", []) if isinstance(node, dict) else []
    head_cells = []
    body_rows = []
    for child in children:
        ctype = child.get("type")
        if ctype == "table_head":
            head_cells = child.get("children", [])
        elif ctype == "table_body":
            for row in child.get("children", []):
                if row.get("type") == "table_row":
                    body_rows.append(row.get("children", []))

    ncols = max(len(head_cells), *[len(r) for r in body_rows]) if (head_cells or body_rows) else 1
    table = doc.add_table(rows=1 + len(body_rows), cols=ncols)
    table.style = "Table Grid"
    table.autofit = True

    def _fill(row_idx, cells, bold=False):
        for ci, cell_tok in enumerate(cells):
            if ci >= ncols:
                break
            cell = table.cell(row_idx, ci)
            cell.paragraphs[0].text = ""
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.alignment = ALIGNMENT
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing = LINE_SPACING_MULTIPLIER
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.first_line_indent = Emu(0)
            render_inline(p, cell_tok.get("children", []), normalize=normalize)
            for r in p.runs:
                if bold:
                    r.bold = True

    if head_cells:
        _fill(0, head_cells, bold=True)
    else:
        for ci in range(ncols):
            table.cell(0, ci).paragraphs[0].text = ""
    for ri, row in enumerate(body_rows, start=1):
        _fill(ri, row, bold=False)


def _render_list_item(doc, item_children, ordered, index, depth, normalize):
    """渲染一个 list_item 及其嵌套子节点。支持任务列表（- [ ] / - [x]）与嵌套列表。"""
    # 提取该 item 的直接文本子节点（block_text / paragraph），用于拼出前缀后的首行
    text_tokens = []
    nested_blocks = []
    for sub in item_children:
        st = sub.get("type")
        if st in ("block_text", "paragraph"):
            text_tokens.extend(sub.get("children", []))
        else:
            nested_blocks.append(sub)

    # 任务列表检测：文本 token 首个 text 以 [ ] / [x] / [X] 开头
    task_marker = None
    if ordered is False and text_tokens:
        first_text = text_tokens[0].get("raw", "") if text_tokens[0].get("type") == "text" else ""
        m = re.match(r"^\s*\[( |x|X)\]\s*", first_text)
        if m:
            checked = m.group(1).lower() == "x"
            task_marker = "☑" if checked else "☐"
            # 移除标记，剩余文本保留（含前导空格）
            remaining = re.sub(r"^\s*\[( |x|X)\]\s*", "", first_text, count=1)
            # 重建 text token 流：替换首个 text 的 raw
            text_tokens = _replace_first_text(token_list=text_tokens, replacement=remaining)

    prefix = f"{index}. " if ordered else ("· " if task_marker is None else f"{task_marker} ")

    para = doc.add_paragraph()
    pf = para.paragraph_format
    pf.alignment = ALIGNMENT
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = LINE_SPACING_MULTIPLIER
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if depth:
        pf.left_indent = Emu(int(FIRST_INDENT_EMU) + depth * int(FIRST_INDENT_EMU))
    pf.first_line_indent = FIRST_INDENT_EMU if depth == 0 else Emu(0)
    pre_run = para.add_run(prefix)
    set_run_font(pre_run)
    render_inline(para, text_tokens, normalize=normalize)

    # 嵌套块级（嵌套列表 / 引用 / 代码块）
    for nb in nested_blocks:
        ntype = nb.get("type")
        if ntype == "list":
            sub_ordered = nb.get("attrs", {}).get("ordered", False)
            sub_start = nb.get("attrs", {}).get("start", 1)
            for sitem in nb.get("children", []):
                if sitem.get("type") == "list_item":
                    _render_list_item(doc, sitem.get("children", []),
                                      ordered=sub_ordered, index=sub_start,
                                      depth=depth + 1, normalize=normalize)
                    sub_start += 1
        elif ntype in ("block_code", "block_quote"):
            render_block(doc, nb, {"chapter_index": 0, "last_was_chapter": False},
                         normalize=normalize, depth=depth + 1)
        elif ntype == "paragraph":
            p2 = doc.add_paragraph()
            apply_para_format(p2, indent=True)
            render_inline(p2, nb.get("children", []), normalize=normalize)


def _replace_first_text(token_list, replacement):
    """替换 token 列表中第一个 text 节点的 raw；若 replacement 为空则移除该 token。"""
    out = []
    replaced = False
    for tok in token_list:
        if not replaced and tok.get("type") == "text":
            if replacement:
                tok = dict(tok, raw=replacement)
                out.append(tok)
            replaced = True
            continue
        out.append(tok)
    return out


def render_block(doc, node, state, normalize: bool = True, depth: int = 0):
    """把一个 MD 块级 token 渲染到 doc。depth 表示列表嵌套层级（用于缩进）。"""
    t = node.get("type") if isinstance(node, dict) else None
    children = node.get("children", []) if isinstance(node, dict) else []

    if t == "heading":
        level = node.get("attrs", {}).get("level", 1) if node.get("attrs") else 1
        plain = _extract_plain_text(children)
        is_chap = is_chapter_title(plain)
        if is_chap and state["chapter_index"] > 0:
            add_pagebreak_para(doc)
        if is_chap:
            state["chapter_index"] += 1
        para = doc.add_paragraph()
        apply_para_format(para, indent=True)
        size = {1: 16, 2: 14, 3: 13}.get(level, FONT_SIZE_PT)
        _render_inline_with_style(para, children, bold=True, normalize=normalize)
        for run in para.runs:
            run.font.size = Pt(size)
        state["last_was_chapter"] = is_chap
        return

    if t == "paragraph":
        if state.get("last_was_chapter"):
            state["last_was_chapter"] = False
        plain = _extract_plain_text(children).strip()
        if not plain:
            return
        para = doc.add_paragraph()
        apply_para_format(para, indent=True)
        render_inline(para, children, normalize=normalize)
        return

    if t == "block_code":
        info = node.get("attrs", {}).get("info", "") if node.get("attrs") else ""
        raw = node.get("raw", "")
        for line in raw.split("\n"):
            para = doc.add_paragraph()
            apply_para_format(para, indent=False)
            run = para.add_run(line if line else " ")
            set_run_font(run, mono=True, size_pt=11)
        return

    if t == "block_quote":
        for child in children:
            if child.get("type") == "paragraph":
                plain = _extract_plain_text(child.get("children", [])).strip()
                if not plain:
                    continue
                para = doc.add_paragraph()
                pf = para.paragraph_format
                pf.alignment = ALIGNMENT
                pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
                pf.line_spacing = LINE_SPACING_MULTIPLIER
                pf.space_before = Pt(0)
                pf.space_after = Pt(0)
                pf.left_indent = Emu(304800)
                pf.first_line_indent = Emu(0)
                render_inline(para, child.get("children", []), normalize=normalize)
        return

    if t == "list":
        ordered = node.get("attrs", {}).get("ordered", False) if node.get("attrs") else False
        start = node.get("attrs", {}).get("start", 1) if node.get("attrs") else 1
        for item in children:
            if item.get("type") != "list_item":
                continue
            item_children = item.get("children", [])
            _render_list_item(doc, item_children, ordered=ordered, index=start, depth=depth, normalize=normalize)
            start += 1
        return

    if t == "table":
        render_table(doc, node, normalize=normalize)
        return

    if t == "thematic_break":
        add_empty_para(doc)
        return

    if t == "blank_line":
        return

    return


def _extract_plain_text(tokens) -> str:
    """递归提取 inline token 流中的纯文本。"""
    if not tokens:
        return ""
    parts = []
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        t = tok.get("type")
        if t == "text":
            parts.append(tok.get("raw", ""))
        elif t in ("strong", "emphasis", "link", "codespan", "strikethrough"):
            parts.append(_extract_plain_text(tok.get("children", [])))
        elif t == "image":
            inner = tok.get("children", [])
            if inner:
                parts.append(_extract_plain_text(inner))
            else:
                parts.append("")
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def format_document(input_path: str, output_path: str, title: str = None,
                    normalize_punct: bool = True):
    """将 MD 文件转换为格式化的 DOCX。"""
    doc = Document()

    # 1. 设置 Normal 默认样式
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME_ZH
    style.font.size = Pt(FONT_SIZE_PT)
    style.font.element.append(make_rfonts_xml())

    spf = style.paragraph_format
    spf.alignment = ALIGNMENT
    spf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    spf.line_spacing = LINE_SPACING_MULTIPLIER
    spf.space_before = Pt(0)
    spf.space_after = Pt(0)
    spf.first_line_indent = FIRST_INDENT_EMU

    # 2. 读取原文
    try:
        text, used_encoding = read_text_with_fallback(input_path)
    except UnicodeDecodeError as e:
        print(f"✗ 编码错误：{e}")
        sys.exit(2)

    # 2.5 鲁棒性检查：空文件 / 超大文件
    if not text.strip():
        print("✗ 文件内容为空，未生成 DOCX")
        sys.exit(5)
    char_count = len(text)
    if char_count > 500000:
        print(f"  ⚠ 文件较大（约 {char_count} 字），建议分批处理以节省时间")
    print(f"  编码检测：{used_encoding}")

    # 3. 解析 MD
    try:
        md = mistune.create_markdown(renderer=None, plugins=["strikethrough", "table"])
        tokens = md(text)
    except Exception as e:
        print(f"✗ 解析失败：{e}（请检查 Markdown 语法）")
        sys.exit(6)
    print(f"  MD 节点数：{len(tokens)}")

    # 4. 检测并插入书名
    state = {"chapter_index": 0, "last_was_chapter": False}
    start_idx = 0

    if title:
        add_para_with_text(doc, title, bold=True, indent=True, normalize=normalize_punct)
        add_empty_para(doc)
        if tokens and tokens[0].get("type") == "heading":
            start_idx = 1
    else:
        if tokens and tokens[0].get("type") == "heading":
            first_plain = _extract_plain_text(tokens[0].get("children", [])).strip()
            first_plain_stripped = strip_md_prefix(first_plain)
            if first_plain_stripped and not is_chapter_title(first_plain_stripped):
                add_para_with_text(doc, first_plain_stripped, bold=True, indent=True, normalize=normalize_punct)
                add_empty_para(doc)
                start_idx = 1
                detected_title = first_plain_stripped

    # 5. 遍历 token 渲染
    for node in tokens[start_idx:]:
        render_block(doc, node, state, normalize=normalize_punct)

    # 6. 保存
    try:
        doc.save(output_path)
    except PermissionError:
        print(f"✗ 权限错误：无法写入 {output_path}（文件被占用或目录无写权限）")
        sys.exit(3)
    except OSError as e:
        print(f"✗ 保存失败：{e}")
        sys.exit(3)
    print(f"[OK] Generated: {output_path}")
    _print_summary(doc, title or (first_plain_stripped if not title and start_idx == 1 else None))


def _print_summary(doc, title):
    """打印文档概要。"""
    para_count = len(doc.paragraphs)
    bold_count = sum(
        1 for p in doc.paragraphs
        if p.text.strip() and any(r.bold for r in p.runs if r.bold)
    )
    page_break_count = 0
    for p in doc.paragraphs:
        for br in p._element.findall(
            './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br'
        ):
            if (
                br.get(
                    '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type'
                )
                == 'page'
            ):
                page_break_count += 1
    print(f"  书名: {title or '(未检测到)'}")
    print(f"  总段落: {para_count}")
    print(f"  标题(加粗): {bold_count}")
    print(f"  分页符: {page_break_count}")


def main():
    parser = argparse.ArgumentParser(description="Markdown 转 DOCX 格式化转换器")
    parser.add_argument("input", help="输入的 Markdown 文件路径")
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出的 DOCX 文件路径（默认：输入名.docx）"
    )
    parser.add_argument(
        "--title", default=None,
        help="小说标题（可选，默认从首段 H1 自动检测）"
    )
    parser.add_argument(
        "--no-punct-norm", action="store_true",
        help="关闭标点规范化（保留 ASCII 标点）"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ 错误：找不到文件 {args.input}")
        sys.exit(1)

    output_path = (
        Path(args.output) if args.output
        else input_path.with_suffix(".docx")
    )

    format_document(
        str(input_path),
        str(output_path),
        args.title,
        normalize_punct=not args.no_punct_norm,
    )


if __name__ == "__main__":
    main()