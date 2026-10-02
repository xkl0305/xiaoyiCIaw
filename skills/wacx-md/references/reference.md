# MarkItDown API 参考

## MarkItDown 类

### 构造函数

```python
class MarkItDown:
    def __init__(
        self,
        enable_plugins: bool = False,
        llm_client = None,
        llm_model: str = None,
        llm_prompt: str = None,
        docintel_endpoint: str = None
    )
```

**参数：**

- `enable_plugins`（bool）：是否启用第三方插件（默认 False）
- `llm_client`：OpenAI 兼容的客户端，用于图片描述
- `llm_model`（str）：图片描述所用模型名（如 `gpt-4o`）
- `llm_prompt`（str）：自定义图片描述提示词
- `docintel_endpoint`（str）：Azure 文档智能服务端点

**示例：**

```python
from markitdown import MarkItDown

# 基础用法
md = MarkItDown()

# 启用插件
md = MarkItDown(enable_plugins=True)

# 用 LLM 给图片生成描述
from openai import OpenAI
client = OpenAI()
md = MarkItDown(llm_client=client, llm_model="gpt-4o")

# 接入 Azure 文档智能
md = MarkItDown(docintel_endpoint="https://your-endpoint.cognitiveservices.azure.com/")
```

### convert() 方法

```python
def convert(
    self,
    source: str | Path | bytes | BinaryIO
) -> ConversionResult
```

**参数：**

- `source`：文件路径（str/Path）、字节内容、文件句柄（二进制模式）

**返回：**

- `ConversionResult` 对象，含 `text_content` 属性

**示例：**

```python
# 从文件路径
result = md.convert("document.pdf")

# 从字节内容
with open("document.pdf", "rb") as f:
    result = md.convert(f.read())

# 从文件句柄
with open("document.pdf", "rb") as f:
    result = md.convert(f)

print(result.text_content)
```

### convert_stream() 方法

```python
def convert_stream(
    self,
    stream: BinaryIO,
    file_extension: str = None
) -> ConversionResult
```

**参数：**

- `stream`（BinaryIO）：二进制文件句柄（如 `open()`、`io.BytesIO`）
- `file_extension`（str）：可选文件扩展名提示

**返回：**

- `ConversionResult` 对象

**示例：**

```python
import io

# 从 BytesIO
data = io.BytesIO(pdf_bytes)
result = md.convert_stream(data, file_extension=".pdf")
```

## ConversionResult

```python
class ConversionResult:
    text_content: str  # Markdown 输出
```

**属性：**

- `text_content`（str）：转换得到的 Markdown 内容

## 命令行用法

### 基础命令

```bash
# 输出到标准输出
markitdown <file>

# 输出到文件
markitdown <file> -o <output.md>

# 管线输入
cat <file> | markitdown
```

### 选项

```bash
markitdown --help
markitdown --list-plugins
markitdown --use-plugins <file>
markitdown <file> -d -e <endpoint>  # Azure 文档智能
```

## 各格式细节

### PDF

- **适用场景**：文本型 PDF
- **限制**：复杂排版可能需要 Azure 文档智能
- **依赖**：`pip install 'markitdown[pdf]'`

### PowerPoint（.pptx）

- **提取内容**：幻灯片文本、文档结构
- **增强方式**：LLM 图片描述
- **依赖**：`pip install 'markitdown[pptx]'`

### Word（.docx）

- **保留元素**：标题、列表、表格、链接
- **依赖**：`pip install 'markitdown[docx]'`

### Excel（.xlsx、.xls）

- **提取内容**：表格、多工作表
- **输出格式**：Markdown 表格
- **依赖**：`pip install 'markitdown[xlsx]'` 或 `'markitdown[xls]'`

### 图片（jpg、png 等）

- **提取内容**：EXIF 元数据 + OCR 文本
- **前置依赖**：系统装 Tesseract OCR
- **增强方式**：LLM 描述

### 音频（wav、mp3）

- **提取内容**：EXIF 元数据 + 语音转写
- **依赖**：`pip install 'markitdown[audio-transcription]'`
- **注意**：可能需要系统音频库

### YouTube

- **提取内容**：视频转写（如有字幕）
- **依赖**：`pip install 'markitdown[youtube-transcription]'`
- **用法**：`markitdown "https://youtube.com/watch?v=VIDEO_ID"`

### HTML

- **保留元素**：文档结构
- **无需额外依赖**

### CSV / JSON / XML

- **转换目标**：可读的 Markdown 格式
- **无需额外依赖**

### ZIP

- **行为**：遍历压缩包内所有文件分别转换
- **无需额外依赖**

### EPUB

- **提取内容**：电子书正文
- **无需额外依赖**

## 环境要求

### Python 版本

- **必需**：Python 3.10 或更高
- **推荐**：Python 3.12

### 虚拟环境（推荐）

```bash
# 标准 Python
python -m venv .venv
source .venv/bin/activate

# uv
uv venv --python=3.12 .venv
source .venv/bin/activate

# Conda
conda create -n markitdown python=3.12
conda activate markitdown
```

### 系统依赖

**Tesseract OCR**（用于图片文字提取）：

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# 从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装包
```

**音频库**（用于音频转写）：

- `speech_recognition` 库需要平台特定的依赖
- 参考：https://github.com/Uberi/speech_recognition

## Azure 文档智能

用于复杂排版 PDF 的高质量转换：

### 准备

1. 创建 Azure 文档智能资源
2. 拿到 endpoint 和 API key
3. 设置环境变量：`AZURE_DOCUMENT_INTELLIGENCE_KEY=<your-key>`

### 用法

**命令行：**

```bash
markitdown document.pdf -d -e "<endpoint>" -o output.md
```

**Python：**

```python
md = MarkItDown(docintel_endpoint="<endpoint>")
result = md.convert("document.pdf")
```

### 更多信息

https://learn.microsoft.com/zh-cn/azure/ai-services/document-intelligence/

## 插件系统

### 查找插件

在 GitHub 上搜索 `#markitdown-plugin`

### 使用插件

**命令行：**

```bash
markitdown --list-plugins
markitdown --use-plugins file.pdf
```

**Python：**

```python
md = MarkItDown(enable_plugins=True)
```

### 开发插件

参考仓库中的 `packages/markitdown-sample-plugin`

## 错误处理

### 常见问题

**缺少依赖：**

```python
try:
    result = md.convert("file.pdf")
except ImportError as e:
    print(f"缺少依赖：{e}")
    print("安装方式：pip install 'markitdown[pdf]'")
```

**文件格式不支持：**

```python
try:
    result = md.convert("file.unknown")
except ValueError as e:
    print(f"不支持的格式：{e}")
```

**转换错误：**

```python
try:
    result = md.convert("file.pdf")
except Exception as e:
    print(f"转换失败：{e}")
```

## 性能建议

1. **批量处理**：复用同一个 MarkItDown 实例
2. **大文件**：考虑分块或流式处理
3. **OCR**：如果更看重速度，可降低图片分辨率
4. **音频**：转写速度大致接近实时或更慢
5. **Azure 文档智能**：最适合复杂排版 PDF，但要付费

## 输出格式说明

- **目标**：面向 LLM 友好的 Markdown，不是像素级还原
- **结构**：保留标题、列表、表格、链接
- **图片**：转为 Markdown 图片语法
- **表格**：转为 Markdown 表格（可能丢失复杂格式）
- **样式**：尽量保留粗体、斜体
- **排版**：线性文档结构（不保留多栏）

## 集成示例

### LangChain 文档加载器

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

### LlamaIndex 文档

```python
from markitdown import MarkItDown
from llama_index import Document

md = MarkItDown()

def create_llama_doc(file_path):
    result = md.convert(file_path)
    return Document(text=result.text_content)
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

## 破坏性变更（v0.0.1 → v0.1.0）

1. **依赖**：现按功能分组
   - 兼容老版本用 `pip install 'markitdown[all]'`

2. **convert_stream()**：现在要求二进制文件句柄
   - 从文本流（`io.StringIO`）改为二进制流（`io.BytesIO`）

3. **DocumentConverter**：接口从路径改为流
   - 不再创建临时文件
   - 插件作者需要更新代码

## 资源链接

- **GitHub**：https://github.com/microsoft/markitdown
- **PyPI**：https://pypi.org/project/markitdown/
- **Issues**：https://github.com/microsoft/markitdown/issues
- **贡献指南**：见仓库中的 CONTRIBUTING.md
