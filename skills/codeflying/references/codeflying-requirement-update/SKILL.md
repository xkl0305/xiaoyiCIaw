---
name: codeflying-requirement-update
description: 对应用开发的某次对话提交反馈（点赞 / 点踩 + 文字说明）
---

# 提交对话反馈

## When to use
- 用户说："点赞"、"很好"、"满意"、"👍"
- 用户说："点踩"、"不好"、"不满意"、"👎"
- 用户说："给个反馈"、"我要反馈"
- 用户对某次开发结果表达明确的正面或负面评价

## 执行步骤

### 第一步：确认反馈类型

若用户意图已明确（点赞/点踩），直接确定 `feadback_type`：
- 正面评价（好、满意、点赞、👍）→ `feadback_type = 1`
- 负面评价（差、不满意、点踩、👎）→ `feadback_type = 0`

若意图不明确，自然询问用户：
"这次开发结果您觉得怎么样？👍 满意 还是 👎 不满意？"

### 第二步：收集补充说明（可选）

若用户有额外说明直接作为 `feedback_message`；若无则传空字符串。

### 第三步：提交反馈

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-requirement-update/requirement_update.py \
  --sender_id "[sender_id]" \
  --memory_id [memory_id] \
  --requirement_id [requirement_id] \
  --feadback_type [0或1] \
  --feedback_message "[补充说明，无则留空]"
```

- 成功 → 回复用户："感谢您的反馈！😊"
- 失败 → 回复用户："反馈提交失败，请稍后重试。"

## 参数说明
| 参数 | 必填 | 说明 |
|------|------|------|
| --memory_id | 是 | 对话记录 ID（从上下文获取） |
| --requirement_id | 是 | 需求 ID（memory_id 所属的需求） |
| --feadback_type | 是 | 1 = 点赞，0 = 点踩 |
| --feedback_message | 否 | 补充说明，默认空字符串 |

### API 请求格式
API 需要 `requirement_id` 在外层，反馈信息在 `data` 对象中：
```json
{
  "requirement_id": 928482491,
  "data": {
    "feadback_type": 1,
    "feedback_message": "很不错",
    "memory_id": 97379
  }
}
```

## Edge cases
- memory_id 不在上下文中：询问用户是针对哪次开发结果反馈
- 缺少 requirement_id：需要从上下文或对话记录中查找对应的 requirement_id
