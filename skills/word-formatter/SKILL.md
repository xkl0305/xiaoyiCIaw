---
name: word-formatter
description: "word-formatter: Word 智能排版助手，支持格式化、美化、整理 Word 文档，按公文/国标规范输出。"
title: "Word 智能排版助手 - SKILL.md"
summary: "Word 智能排版 Skill 完整文档 v2.0"
author: "周博远"
version: "2.0.0"
skill_id: "word-formatter"
triggers:
  - intent: ["排版", "格式化", "美化", "整理 Word", "套模板", "公文排版", "国标排版"]
  - explicit: ["@Word 排版", "@word-formatter"]
inputs:
  - name: "source_file"
    type: "file"
    required: true
    description: "待排版的 Word 文档（.docx/.doc/.md）"
  - name: "template_id"
    type: "string"
    required: false
    default: "business_default"
    description: "模板 ID（如 gov_tongzhi/biz_white_paper/simple_minimal）"
  - name: "gov_doctype"
    type: "enum"
    enum: ["通知", "报告", "请示", "批复", "纪要", "函", "意见", "通报", "公告", "决定"]
    required: false
    description: "公文类型（template_id 以 gov_ 开头时生效）"
  - name: "format_options"
    type: "object"
    required: false
    description: "格式选项（scope/keep_content/gov_check/generate_diff_report）"
outputs:
  - name: "formatted_file"
    type: "file_link"
    description: "排版后的 Word 文档"
  - name: "diff_report"
    type: "file_link"
    description: "排版差异对比报告（Markdown）"
  - name: "gov_check_report"
    type: "file_link"
    description: "公文国标校验报告（仅公文模板）"
  - name: "summary"
    type: "string"
    description: "排版操作摘要"
  - name: "md_archive_path"
    type: "string"
    description: "Markdown 归档路径"
---

# 📘 Word 智能排版助手 v2.0

> 上传 Word → 自动识别结构 → 套用模板 → 智能美化 → 输出规范化 Word + 排版对比报告 + MD 归档

---

## 👥 受众说明

| 用户类型 | 使用方式 | 推荐模板 |
|---------|---------|----------|
| **个人用户** | 日常文档排版，上传即可自动排版 | simple_minimal / simple_modern |
| **政府/事业单位** | 公文排版，严格遵循国标 | gov_tongzhi / gov_baogao 等 |
| **企业用户** | 商务文档排版，专业报告 | biz_report / biz_white_paper |
| **学术研究者** | 论文排版，符合学术规范 | acad_paper_cn / acad_thesis |
| **团队协作** | 团队共用，自定义模板统一风格 | custom/* (用户自定义) |

> 如果你是第一次使用，从"新手 30 秒上手"开始。如果你是公文用户，直接跳到"公文排版深度支持"。

## 🛠️ 定制化使用指南

### 用户偏好设置
在 `config/user_profile.md` 中配置个人偏好，Skill 会在每次排版时自动应用：
```yaml
# 示例：用户偏好配置
user_name: "张三"
company: "XX公司"
default_template: "biz_report"  # 默认模板
preferred_font: "微软雅黑"      # 偏好字体
keep_history_days: 30            # 保留历史天数
```

### 自定义模板上传
```bash
# 1. 上传参考文档作为模板基准
"以这份文档的风格为模板，命名为 my_style，保存到 custom/"
# 2. 基于自定义模板排版
@skill:word-formatter source_file="新文档.docx" template_id="my_style"
```

### 场景参数传递
```bash
# 完整参数示例
@skill:word-formatter source_file="报告.docx" template_id="biz_report" format_options='{"scope":"full", "keep_tables":true, "auto_toc":true}'
```

## 🚀 新手 30 秒上手

```markdown
# 场景 1：普通文档排版
"把 项目报告.docx 排成商务风格"

# 场景 2：公文排版（自动识别公文类型）
"把 省政府通知.docx 按公文国标排版"

# 场景 3：多模板对比
"把 AI行业报告.docx 同时输出商务、极简、创意三种风格"

# 场景 4：自定义模板
"上传 我的模板参考.docx， based on 这个风格帮我排版 新文档.docx"
```

**AI 会自动：**
1. 解析文档结构（标题/段落/表格/图片）
2. 匹配最佳模板
3. 应用排版规则（字体/字号/行距/段距）
4. 生成差异对比报告
5. Markdown 归档

---

## 📋 能力边界（重要！）

| 类别 | 支持 | 不支持 |
|------|------|--------|
| **输入格式** | ✅ .docx / .doc / .md | ❌ .pdf / .pages / .wps |
| **输出格式** | ✅ .docx | ❌ .pdf / .html（规划中） |
| **公文标准** | ✅ GB/T 9704-2012 完整支持 | ❌ 地方政府特殊格式（需自定义） |
| **模板数量** | ✅ 28+ 套（6 大类） | ❌ 无限自定义（需手动上传参考稿） |
| **字体处理** | ✅ 自动替换缺失字体 | ❌ 自动安装字体（需手动安装） |
| **表格美化** | ✅ 自动调整列宽/边框/底纹 | ❌ 复杂合并单元格逻辑（保留原样） |
| **图片处理** | ✅ 调整大小/位置/环绕方式 | ❌ 图片内容识别/裁剪/滤镜 |
| **多语言** | ✅ 中文/英文/中英混排 | ❌ 从右到左语言（阿拉伯语等） |
| **批量处理** | ✅ 同一模板批量处理多文档 | ❌ 不同模板批量处理（需多次调用） |

---

## 🏛️ 公文排版深度支持（v2.0 核心）

### 适用国家标准
- **GB/T 9704-2012** 党政机关公文格式（核心）
- **GB/T 9704-1999** 旧版国家行政机关公文格式（兼容）
- **中办发〔2012〕14 号** 党政机关公文处理工作条例
- **GB/T 7714-2015** 参考文献著录规则

### 支持的文种（15 种）
| 文种 | 用途 | 优先级 | 模板 ID |
|------|------|--------|----------|
| 决议 | 重大决策 | P0 | gov_juey |
| 决定 | 重要事项决定 | P0 | gov_jueding |
| 命令（令） | 强制性措施 | P0 | gov_mingling |
| 公报 | 重要决定公开发布 | P0 | gov_gongbao |
| 公告 | 法定事项告知 | P0 | gov_gonggao |
| 通告 | 应遵守事项 | P0 | gov_tonggao |
| 意见 | 见解/处理办法 | P0 | gov_yijian |
| **通知** | **转发/部署/任免** | **P0** | **gov_tongzhi** |
| **通报** | **表彰/批评/情况** | **P0** | **gov_tongbao** |
| **报告** | **汇报工作/反映情况** | **P0** | **gov_baogao** |
| **请示** | **请求批准** | **P0** | **gov_qingshi** |
| **批复** | **答复下级请示** | **P0** | **gov_pifu** |
| **议案** | **提请审议** | **P0** | **gov_yian** |
| **函** | **不相隶属机关商洽** | **P0** | **gov_han** |
| **纪要** | **会议议定事项** | **P0** | **gov_jiyao** |

> ⭐ 标记为最高频文种，MVP 必交付

### GB/T 9704-2012 版式规范（核心规则）

```yaml
# 页面设置
paper: A4 (210mm × 297mm)
margin:
  top: 37mm    # 上 3.7cm（白边）
  bottom: 35mm # 下 3.5cm
  left: 28mm   # 左 2.8cm（订口）
  right: 26mm  # 右 2.6cm
header_distance: 0
footer_distance: 0

# 版心
content_area: 156mm × 225mm

# 行字数
chars_per_line: 28  # 每行 28 字
lines_per_page: 22  # 每页 22 行

# 字体规范
fonts:
  份号: "宋体 4 号"
  密级和保密期限: "黑体 3 号"
  紧急程度: "黑体 3 号"
  发文机关标志: "方正小标宋简体 红色"
  发文字号: "仿宋_GB2312 3 号"
  签发人: "仿宋_GB2312 3 号 + 黑体 3 号(姓名)"
  标题: "方正小标宋简体 2 号"
  主送机关: "仿宋_GB2312 3 号"
  正文: "仿宋_GB2312 3 号"
  一级标题: "黑体 3 号"
  二级标题: "楷体_GB2312 3 号"
  三级标题: "仿宋_GB2312 3 号 加粗"
  四级标题: "仿宋_GB2312 3 号"
  附件说明: "仿宋_GB2312 3 号"
  发文机关署名: "仿宋_GB2312 3 号"
  成文日期: "仿宋_GB2312 3 号"
  印章: "红色"
  附注: "仿宋_GB2312 3 号"
  抄送机关: "仿宋_GB2312 4 号"
  印发机关和日期: "仿宋_GB2312 4 号"
  页码: "阿拉伯数字 4 号半角宋体"

# 段落
paragraph:
  line_spacing: 28pt 固定值
  first_line_indent: 2 字符
  alignment: justify

# 红头
red_header:
  separator_line:
    color: 红色
    width: 0.35mm  # 武文线
    length: 156mm  # 等于版心宽度
    position: 发文字号下空一行

# 页码
page_number:
  position: 版心下边缘之下一行
  alignment_odd: 右空一字
  alignment_even: 左空一字
  format: "— 1 —"  # 数字两侧加一字线
  blank_page: 

---

> 注：完整 Skill 规范与触发配置见 references/ 与 inputs/ 详情，超长内容已省略。
