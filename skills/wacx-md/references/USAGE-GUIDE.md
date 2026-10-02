# MarkItDown 使用指南

文档转换的详细示例与模式。

## 命令行用法

### 基础转换

```bash
# 输出到标准输出
markitdown document.pdf

# 输出到文件
markitdown document.pdf -o output.md

# 从标准输入读
cat document.pdf | markitdown > output.md
```

### 网页内容

```bash
# 抓取并转换网址
markitdown https://example.com/docs -o docs.md

# GitHub README
markitdown https://raw.githubusercontent.com/user/repo/main/README.md
```

### 批量处理

```bash
# 转换目录下所有 PDF
for file in *.pdf; do
  markitdown "$file" -o "${file%.pdf}.md"
done

# 用本技能自带的脚本
python scripts/batch_convert.py docs/*.pdf -o markdown/ -v
```

### 高级选项

```bash
# 启用插件
markitdown --use-plugins file.pdf

# 列出插件
markitdown --list-plugins

# Azure 文档智能（复杂排版 PDF）
markitdown file.pdf -d -e "<endpoint>" -o output.md
```

---

## Python API

### 基础用法

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("document.pdf")
print(result.text_content)
```

### 用 LLM 给图片生成描述

```python
from markitdown import MarkItDown
from openai import OpenAI

client = OpenAI()
md = MarkItDown(
    llm_client=client,
    llm_model="gpt-4o",
    llm_prompt="Describe this image in detail"
)
result = md.convert("image.jpg")
print(result.text_content)
```

### Azure 文档智能

```python
from markitdown import MarkItDown

md = MarkItDown(docintel_endpoint="https://your-endpoint.cognitiveservices.azure.com/")
result = md.convert("complex-layout.pdf")
print(result.text_content)
```

### 批量处理

```python
from markitdown import MarkItDown
from pathlib import Path

md = MarkItDown()

for pdf_file in Path("docs/").glob("*.pdf"):
    result = md.convert(str(pdf_file))
    output_path = pdf_file.with_suffix(".md")
    output_path.write_text(result.text_content)
```

### 错误处理

```python
from markitdown import MarkItDown

md = MarkItDown()

try:
    result = md.convert("file.pdf")
    print(result.text_content)
except ImportError as e:
    print(f"缺少依赖：{e}")
    print("安装方式：pip install 'markitdown[pdf]'")
except Exception as e:
    print(f"转换失败：{e}")
```

---

## 各格式的示例

### PDF 文档

```bash
# 简单提取
markitdown document.pdf -o document.md

# 复杂排版（走 Azure）
markitdown document.pdf -d -e "<endpoint>" -o document.md
```

### PPT 演示文稿

```bash
markitdown presentation.pptx -o slides.md
```

```python
# 配合 LLM 给图片生成描述
from openai import OpenAI
md = MarkItDown(llm_client=OpenAI(), llm_model="gpt-4o")
result = md.convert("presentation.pptx")
```

### Excel 表格

```bash
markitdown spreadsheet.xlsx -o data.md
```

输出格式：

```markdown
## Sheet1

| Column A | Column B | Column C |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
```

### 图片（OCR）

```bash
# 需先装 Tesseract OCR
markitdown scanned-document.jpg -o extracted.md
```

### 音频转写

```bash
pip install 'markitdown[audio-transcription]'
markitdown recording.mp3 -o transcript.md
```

### YouTube 视频

```bash
pip install 'markitdown[youtube-transcription]'
markitdown "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md
```

### ZIP 压缩包

```bash
# 遍历压缩包内每个文件分别转换
markitdown archive.zip -o contents.md
```

---

## 集成模式

### LLM 文档分析

```python
from markitdown import MarkItDown
from openai import OpenAI

md = MarkItDown()
client = OpenAI()

# 转换文档
result = md.convert("contract.pdf")

# 用 LLM 分析
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "分析这份合同的关键条款"},
        {"role": "user", "content": result.text_content}
    ]
)
print(response.choices[0].message.content)
```

### RAG 流水线

```python
from markitdown import MarkItDown

md = MarkItDown()

# 转换知识库
documents = []
for file in ["doc1.pdf", "doc2.docx", "doc3.pptx"]:
    result = md.convert(file)
    documents.append({
        "source": file,
        "content": result.text_content
    })

# 灌入向量数据库...
```

### LangChain 集成

```python
from markitdown import MarkItDown
from langchain.docstore.document import Document

md = MarkItDown()

def load_document(file_path):
    result = md.convert(file_path)
    return Document(
        page_content=result.text_content,
        metadata={"source": file_path}
    )
```

### FastAPI 接口

```python
from fastapi import FastAPI, UploadFile
from markitdown import MarkItDown

app = FastAPI()
md = MarkItDown()

@app.post("/convert")
async def convert_file(file: UploadFile):
    content = await file.read()
    result = md.convert(content)
    return {"markdown": result.text_content}
```

---

## 性能建议

1. **复用 MarkItDown 实例**：批量处理时只创建一次
2. **降低图片分辨率**：如果更看重 OCR 速度
3. **复杂 PDF 排版**：用 Azure 文档智能
4. **音频转写**：速度大致接近实时

## 输出格式

MarkItDown 会保留以下元素：

- 标题（H1-H6）
- 列表（有序/无序）
- 表格
- 链接
- 代码块
- 图片（用 Markdown 语法）

**注意**：为 LLM 阅读优化，不是像素级还原原版式。
