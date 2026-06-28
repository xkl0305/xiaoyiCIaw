---
name: xiaoyi-ocr-text-recognition  
description: 使用OCR API进行图像文本识别，获取文本内容及坐标信息  

---

# OCR文本识别 Skill

## 简介  
通过OCR API对图像中的文字进行智能识别，返回文本内容、坐标信息及语言类型。支持JPG/PNG/BMP格式，可选择多语言识别和坐标类型。

## 特性  
- ✅ **双输入支持** - 同时支持Base64和公网URL输入  
- ✅ **多语言自动识别** - 支持21种语言（中文、英文等），无需指定语言，自动识别 
- ✅ **坐标信息** - 返回文本位置坐标  
- ✅ **错误反馈** - 详细错误码和描述信息  
- ✅ **结果结构化** - 返回文本内容、置信度、语言类型  

## 文件结构  
```
xiaoyi-ocr-text-recognition/
├── SKILL.md                # 使用说明（本文档）  
├── scripts                 # 程序文件夹  
│ ├── ocr_recognition.py    # 主程序（OCR识别）  
├── _meta.json              # Skill 元数据  
└── package.json            # 项目配置  
```

## 使用方法  

### OCR识别（直接使用Base64或URL）  
```bash
# 进入 skill 目录  
cd /home/sandbox/.openclaw/workspace/skills/xiaoyi-ocr-text-recognition  

# 基本使用（Base64输入）  
python ./scripts/ocr_recognition.py --imgBase64 "base64字符串"  

# 使用公网URL输入  
python ./scripts/ocr_recognition.py --url "https://example.com/image.jpg"  

```

### Python代码调用示例  
```python
from scripts.ocr_recognition import recognize_text  

# URL输入示例  
result = recognize_text(  
    url="https://example.com/image.jpg" 
)  
print(result)  
```

## API 信息

| 项目         | 值                                                                         |
|------------|---------------------------------------------------------------------------|
| 图片翻译地址 | `https://hag-drcn.op.dbankcloud.com/celia-claw/v1/http-api/skill/execute` |
| 鉴权方式 | 从 `.xiaoyienv` 读取 API Key 和 UID，'.xiaoyienv文件默认存在，无需用户自行创建输入' |
| 响应格式       | JSON                                                                      |

### 配置说明

在 `/home/sandbox/.openclaw/.xiaoyienv` 文件中配置以下参数：

```bash
PERSONAL-API-KEY=你的API密钥
PERSONAL-UID=你的用户ID
```

**注意**：
- 图像理解 API 和文件上传服务地址均已固化在代码中，无需配置
- 只需配置 `PERSONAL-API-KEY` 和 `PERSONAL-UID` 即可

## 输入参数  

| 参数       | 类型         | 必填 | 默认值 | 说明                                                                 |
|------------|--------------|------|--------|----------------------------------------------------------------------|
| url        | String       | Y/N  | -      | 公网图片地址                                  |

### 支持语言及编码对照表

| 语言         | 语言编码   | 说明         |
|------------|--------|------------|
| 中文（简体）     | zh-CHS | 默认支持     |
| 中文（繁体）     | zh-CHT | 默认支持     |
| 英文         | en     | 默认支持     |
| 日文         | ja     | 默认支持     |
| 韩文         | ko     | 默认支持     |
| 俄语         | ru     | 默认支持     |
| 西班牙语       | es     | 默认支持     |
| 法语         | fr     | 默认支持     |
| 德语         | de     | 默认支持     |
| 意大利语       | it     | 默认支持     |
| 葡萄牙语       | pt     | 默认支持     |
| 菲律宾语       | tl     | 默认支持     |
| 泰语         | th     | 默认支持     |
| 土耳其语       | tr     | 默认支持     |
| 阿拉伯语       | ar     | 默认支持     |
| 波兰语        | pl     | 默认支持     |
| 马来语        | ms     | 默认支持     |
| 印尼语（印度尼西亚） | id     | 默认支持     |
| 希腊语（现代）    | el     | 默认支持     |
| 捷克语（捷克共和国） | cs     | 默认支持     |
| 荷兰语        | nl     | 默认支持     |
| 越南语        | vi     | 默认支持     |

## 输出参数  

| 字段       | 类型         | 说明                                                                 |
|------------|--------------|----------------------------------------------------------------------|
| texts      | Text[]       | 检测到的文本信息（第一个元素为汇总信息，后续为每行信息）             |
| requestId  | String       | 唯一请求ID                                                           |
| retCode    | String       | 响应码（0-成功，1001-系统错误等）                                    |
| retMsg     | String       | 响应信息                                                             |

### Text对象结构  
| 字段       | 类型         | 说明                                                                 |
|------------|--------------|----------------------------------------------------------------------|
| text       | String       | 识别的文本内容                                                       |
| confidence | Double       | 置信度（0-1）                                                        |
| coords     | Coord[]      | 文本坐标信息                                                         |
| language   | String       | 文本语种                                                             |

### Coord对象结构  
| 字段 | 类型  | 说明         |
|------|-------|--------------|
| x    | Int   | X坐标        |
| y    | Int   | Y坐标        |

## 何时使用  

### ✅ 适合场景  
1. 需要**提取图片中的文字内容**时（如文档数字化）  
2. 需要**获取文本位置坐标**时（如图像标注）  
3. 用户**明确要求多语言识别**时（如多语种文档处理）  

### ❌ 不适合场景  
1. **纯图像处理需求**（如图片美化）  
2. **视频内容识别**（当前仅支持静态图像）  
3. **非文本图像识别**（如图表、照片）  

## 输出示例  

```bash
$ python ./scripts/ocr_recognition.py --imgBase64 "base64字符串"  

✅ .xiaoyienv 文件解析成功
✅ key "PERSONAL-API-KEY" 存在：SK-XXXXXXXXXXXXXXXX
✅ key "PERSONAL-UID" 存在：420086000107623357
✅ 请求 URL：https://lfhagmirror.hwcloudtest.cn:18449/celia-claw/v1/rest-api/skill/execute 

🔍 OCR结果  
================================================================================  

📝 返回结果:  
{  
  "retCode": "0",  
  "retMsg": "Success",  
  "texts": [  
    {  
      "text": "Hello World",  
      "confidence": 0.98,  
      "coords": [{"x": 100, "y": 200}, {"x": 150, "y": 200}, {"x": 150, "y": 250}, {"x": 100, "y": 250}],  
      "language": "en"  
    }  
  ]  
}  
```

## 返回格式  

```json
{  
  "retCode": "0",  
  "retMsg": "Success",  
  "texts": [  
    {  
      "text": "识别文本内容",  
      "confidence": 0.95,  
      "coords": [{"x": 50, "y": 60}, {"x": 100, "y": 60}, {"x": 100, "y": 80}, {"x": 50, "y": 80}],  
      "language": "zh"  
    }  
  ]  
}  
```

## 注意事项  

1. **输入限制**：  
   - Base64输入大小不超过4M（原图3M）  
   - URL必须可公开访问  
   - 支持格式：JPG/PNG/BMP  

2. **语言限制**：  
   - 指定语言必须为支持的21种之一（如zh、en、ja等）  

3. **坐标类型**：  
   - 返回四点坐标 

## 错误码说明  

| 错误码 | 描述                       | 解决方案            |
|--------|--------------------------|-----------------|
| 0      | 成功                       | 无需处理            |
| 1001   | 系统内部错误                | 联系技术支持          |
| 2001   | 鉴权失败                    | 检查API密钥和UID      |
| 2005   | 图片无法识别                | 更换清晰图片输入      |

## 总结  

当需要OCR文本识别时：  
1. ✅ 准备图片（Base64或URL）  
2. ✅ 设置语言和坐标类型（可选）  
3. ✅ 调用OCR API  
4. ✅ 解析返回结果  
5. ✅ 处理可能的错误码  

记住：OCR识别可同时获取文本内容和坐标信息，请确保输入格式和大小符合要求。✅  
