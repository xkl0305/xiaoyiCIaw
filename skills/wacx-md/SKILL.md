---
name: wacx-md
description: "使用微软 MarkItDown 库/CLI 把 PDF/Word/PPT/Excel/图片（OCR）/音频（转写）/HTML/YouTube/URL 等文档转换为 Markdown。适用于用户要把文件或网址转成 Markdown、从 PDF/图片提取文字、转录音视频或批量转换文档的场景。"
---

# 文档转 Markdown 工具（MarkItDown）

基于微软 [MarkItDown](https://github.com/microsoft/markitdown) 库实现的文档转 Markdown 工具。实际转换由通过 pip 安装的 `markitdown` 命令行工具完成，本技能提供说明文档和批量转换脚本。

## 适用场景

- 📄 把文档（README、API 文档、网页）抓取为 Markdown
- 📝 文档分析（PDF、Word、PPT、Excel）
- 🖼️ 图片文字提取（OCR + EXIF 元数据）
- 🎤 音频/视频转写
- 🎬 YouTube 视频字幕提取

## 快速上手

```bash
# 转换本地文件
markitdown document.pdf -o output.md

# 转换网址
markitdown https://example.com/docs -o docs.md

# 从标准输入读
cat document.pdf | markitdown > output.md
```

## 支持的格式

| 格式         | 特性                                    |
|--------------|------------------------------------------|
| PDF          | 文本提取、文档结构                       |
| Word         | 标题、列表、表格（.docx）                 |
| PowerPoint   | 幻灯片文本（.pptx）                       |
| Excel        | 表格、多工作表（.xlsx）                   |
| 图片         | OCR + EXIF 元数据（需 Tesseract）         |
| 音频         | 语音转写（需安装 [audio] 扩展）           |
| HTML         | 保留文档结构                              |
| YouTube      | 视频转写（需安装 [youtube] 扩展）         |
| ZIP          | 遍历压缩包内每个文件分别转换              |

## 安装

```bash
# 全量安装（所有格式扩展）
pip install 'markitdown[all]'

# 只装需要的格式
pip install 'markitdown[pdf,docx,pptx]'

# OCR 依赖（Ubuntu/Debian）
sudo apt-get install tesseract-ocr
# macOS: brew install tesseract
```

音频转写需要：`pip install 'markitdown[audio-transcription]'`。
YouTube 转写需要：`pip install 'markitdown[youtube-transcription]'`。

## 常用模式

### 抓取 GitHub README 或网页文档
```bash
markitdown https://raw.githubusercontent.com/user/repo/main/README.md -o readme.md
```

### 转换 PDF（复杂排版建议用 Azure 文档智能）
```bash
markitdown document.pdf -o document.md
markitdown complex.pdf -d -e "<endpoint>" -o out.md
```

### 批量转换一个目录的文件
```bash
# 用本技能自带的脚本
python scripts/batch_convert.py docs/*.pdf -o markdown/ -v

# 或纯 shell 循环
for file in docs/*.pdf; do
  markitdown "$file" -o "${file%.pdf}.md"
done
```

### 用 Python API
```python
from markitdown import MarkItDown
md = MarkItDown()
result = md.convert("document.pdf")
print(result.text_content)
```

### 用 LLM 给图片生成描述（可选）
```python
from markitdown import MarkItDown
from openai import OpenAI
md = MarkItDown(llm_client=OpenAI(), llm_model="gpt-4o",
                llm_prompt="Describe this image in detail")
result = md.convert("image.jpg")
```

## 高级选项

```bash
markitdown --use-plugins file.pdf   # 启用已注册的插件
markitdown --list-plugins           # 列出可用插件
```

## 常见问题排查

| 现象                                   | 解决办法                                                |
|----------------------------------------|---------------------------------------------------------|
| `markitdown: command not found`        | 执行 `pip install 'markitdown[all]'`                    |
| OCR 识别为空或报错                      | 装 Tesseract（见上文安装一节）                           |
| 复杂 PDF 排版错乱                       | 用 `-d -e "<endpoint>"` 走 Azure 文档智能                |
| 报缺少依赖的错误                        | 通过 pip 装对应 `[xxx]` 扩展                             |

## 本技能提供的资源

- `markitdown` 命令行工具和 Python API — 通过 `pip install 'markitdown[all]'` 安装
- `scripts/batch_convert.py` — 本技能自带，按目录级别批量转换
- 说明文档 — `references/USAGE-GUIDE.md`、`references/reference.md`
