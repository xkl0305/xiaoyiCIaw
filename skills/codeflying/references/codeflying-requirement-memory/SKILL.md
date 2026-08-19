---
name: codeflying-requirement-memory
description: 获取需求的对话记录（AI 交互历史）
---

# 获取对话记录

## Description
获取指定需求的 AI 对话记录，包括用户输入和 AI 回复的完整历史。

## When to use
- 用户说："查看对话记录"
- 用户说："之前聊了什么"
- 需要了解需求开发过程时

## How to use
```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-memory/requirement_memory.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" --id 123
```

### 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| --id | 是 | 需求 ID |

## Edge cases
- 需求不存在：提示 ID 无效
- 无对话记录：返回空列表
