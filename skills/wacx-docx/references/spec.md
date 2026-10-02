# wacx-docx - 格式规格参考（v3.0 MD→DOCX）

## 用户级永久记忆要求

- **字体**: 宋体 小四(12pt)；代码块 Courier New 11pt
- **对齐**: 左对齐
- **行距**: 1.5倍（乘数模式）
- **段前后**: 0
- **首行缩进**: 304800 EMU（约2字符）；空行/代码块/分页段不缩进
- **标题格式**: 小说名/卷/章名加粗；H1=16pt, H2=14pt, H3=13pt, H4+=12pt
- **分页符**: 每章前插空段+`br type=page`（首章前无分页）
- **引号**: ASCII `"` `'` → 中文全角 `""` `''`（toggle 状态机）
- **标点**: ASCII `, . ; : ? ! ( )` → 中文全角（仅 CJK 上下文，含跨 token 上下文）
- **破折号/省略号**: `--` → `——`；`...` → `……`
- **编码**: 自动识别 UTF-8 BOM / UTF-8 / GBK / GB2312 / latin-1

## python-docx 关键设置

```python
from docx import Document
from docx.shared import Pt, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

# 字体
font.name = "宋体"
rFonts = run._element.makeelement(qn("w:rFonts"), {
    qn("w:eastAsia"): "宋体",
    qn("w:ascii"): "宋体",
    qn("w:hAnsi"): "宋体",
})

# 字号
font.size = Pt(12)

# 行距（乘数模式）
pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
pf.line_spacing = 1.5

# 首行缩进（标题行也有缩进）
pf.first_line_indent = Emu(304800)

# 分页符（空段落+br type=page）
para = doc.add_paragraph()
run = para.add_run("")
br_elem = parse_xml('<w:br w:type="page"/>')
run._element.append(br_elem)
```

## MD 解析（mistune 3.x）

```python
import mistune
md = mistune.create_markdown(renderer=None, plugins=["strikethrough", "table"])
tokens = md(text)
# token 结构（AST 模式）：
# - heading { level, children: [text, strong, ...] }
# - paragraph { children: [...] }
# - list { ordered, start, children: [list_item, ...] }
# - list_item { children: [block_text, ...] }   ← 注意：3.x 是 block_text 不是 paragraph
# - block_code { info, raw }
# - block_quote { children: [paragraph, ...] }
# - blank_line { }
# - thematic_break { }
# - strikethrough { children: [...] }           ← 需要 plugins=["strikethrough"]
```

### MD 语法 → DOCX 映射表

| MD 节点 | DOCX 段类型 | 字体/缩进 | 标点规范化 |
|---------|------------|----------|----------|
| `heading` (level 1) | 加粗段 16pt | 首行缩进 | ✅ |
| `heading` (level 2) | 加粗段 14pt | 首行缩进 | ✅ |
| `heading` (level 3) | 加粗段 13pt | 首行缩进 + 章名匹配加分页 | ✅ |
| `heading` (level 4+) | 加粗段 12pt | 首行缩进 | ✅ |
| `paragraph` | 正文段 12pt | 首行缩进 | ✅ |
| `list` (无序) | `· item` 段 12pt，递归嵌套缩进 | 首行缩进 | ✅ |
| `list` (任务) | `☐`/`☑` item 段 | 首行缩进 | ✅ |
| `list` (有序) | `1. item` 段 12pt | 首行缩进 | ✅ |
| `table` | 带边框表格 Table Grid（表头加粗） | — | ✅（表内） |
| `block_code` | 多段 11pt Courier New | 不缩进 | ❌ 保留 ASCII |
| `block_quote` | 引用段 12pt | left_indent 1 字符 | ✅ |
| `thematic_break` | 空段 | 不缩进 | — |
| `blank_line` | （不生成段） | — | — |
| inline `text` | run | 宋体 12pt | ✅（含跨 token 上下文） |
| inline `strong` | run | bold=True | ✅ |
| inline `emphasis` | run | italic=True | ✅ |
| inline `strikethrough` | run | strike=True | ✅ |
| inline `codespan` | run | Courier New 等宽 | ❌ |
| inline `link` | run（仅显示文字） | 宋体 | ✅ |
| inline `image` | run（`【图片：alt】`） | 宋体 | — |
| inline `linebreak` | `<w:br/>` 行内 | — | — |
| inline `softbreak` | 空格 | — | — |

## 标点规范化规则（v3.0 核心）

```python
def normalize_punctuation(text, preserve_english=False, prev_char="", next_char=""):
    # 1. 引号 toggle：ASCII " → ""（先左后右，状态机）
    # 2. URL/邮箱保护：包裹 \x00 占位
    # 3. 破折号优先：-- → ——；CJK 上下文单 - → ——
    # 4. 省略号：... → ……
    # 5. 字符级 ASCII 标点 → 中文全角（仅 CJK 上下文，含跨 token 上下文）
    # 6. 还原 URL/邮箱占位符
```

### 字符级映射表

| ASCII | 中文全角 | 触发条件 |
|-------|---------|---------|
| `,` | `，` | CJK 上下文 |
| `.` | `。` | CJK 上下文 |
| `;` | `；` | CJK 上下文 |
| `:` | `：` | CJK 上下文 |
| `?` | `？` | CJK 上下文 |
| `!` | `！` | CJK 上下文 |
| `(` | `（` | CJK 上下文 |
| `)` | `）` | CJK 上下文 |
| `[` | `【` | CJK 上下文 |
| `]` | `】` | CJK 上下文 |
| `"` | `""` | 全部（toggle 状态机） |
| `'` | `''` | 全部（toggle 状态机） |
| `--` | `——` | 全部（不依赖上下文） |
| `...` | `……` | 全部（不依赖上下文） |

### 保护规则

1. **代码块 / 行内代码**：完全不规范化（避免破坏代码语法）
2. **URL / 邮箱**：占位符包裹，规范化后还原
3. **英文段落保护**：标点前后 1 字符内无 CJK 时不替换（`_has_cjk_neighbor_ext`）
4. **跨 token 上下文**：标点位于单字符 text token 内时，借助兄弟 token 的首尾字符判断 CJK 上下文
5. **嵌套引号**：由 mistune AST 决定归属，toggle 状态机处理

## 分段策略

```python
# mistune 解析的 token 流中：
# - paragraph = 一个 MD 段落（以空行分隔）
# - blank_line = 段落间的空行（不生成 DOCX 段）
# - 单换行（在 MD 中 = softbreak）= 渲染为段落内空格

# 例：
#   "第一行\n第二行\n\n第三行"  →  段 1: "第一行 第二行"  段 2: "第三行"
#   "第一行  \n第二行"  →  段 1: "第一行<w:br/>第二行"（行尾两空格 = 强制换行）
#   "第一行\\\n第二行"  →  段 1: "第一行<w:br/>第二行"（\\ 结尾 = 强制换行）
```

## 章节标题识别

| 模式 | 正则 | 示例 |
|------|------|------|
| 章名 | `^第[一二三四五六七八九十百千万零\d]+[章节回].*$` | 第一章、第1章 |
| 卷名 | `^第[一二三四五六七八九十百千万零\d]+\s*[卷册编].*$` | 第一卷 |
| 幕名 | `^[春夏秋冬]之幕.*$` | 春之幕 |
| 季名 | `^[第][一二三四五六七八九十百千万]+[季度].*$` | 第一季 |

匹配规则后：从第 2 次匹配起，前置分页符；第 1 次匹配前无分页。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 文件不存在/参数错误 |
| 2 | 编码无法识别 |
| 3 | 权限/磁盘错误 |
| 4 | 缺少依赖（mistune/python-docx） |
| 5 | 文件内容为空 |
| 6 | Markdown 解析失败 |