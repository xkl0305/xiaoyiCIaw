---
name: codeflying-requirement-list
description: 获取 CodeFlying 需求列表
---

# 获取需求列表

## Description
获取当前租户下的所有开发需求列表。每个应用可以有多个需求（多次迭代开发）。

## When to use
- 用户说："查看需求列表"
- 用户说："有哪些开发需求"
- 需要获取 requirement_id 时

## How to use
```bash
# 获取所有需求
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-list/requirement_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID"

# 按应用筛选
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-list/requirement_list.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID" --app-id 123
```

### 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| --app-id | 否 | 按应用 ID 筛选 |

## Edge cases
- 无需求：返回空列表
