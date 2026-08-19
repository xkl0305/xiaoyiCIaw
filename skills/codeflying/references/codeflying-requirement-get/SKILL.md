---
name: codeflying-requirement-get
description: 获取单个需求的详细信息
---

# 获取需求详情

## Description
获取指定需求的详细信息，包括原始需求、澄清后的需求、状态等。

## When to use
- 用户说："查看需求详情"
- 用户说："这个需求的具体内容"
- 需要了解需求详细信息时

## How to use
```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-get/requirement_get.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" --id 123
```

### 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| --id | 是 | 需求 ID |

> **注意**: `/requirement/get_one` 接口必须带 `page` 和 `page_size` 参数，否则会报 `int() argument must be a string...` 错误。脚本已内置默认值 page=1, page_size=10。

## Edge cases
- 需求不存在：提示 ID 无效
