---
name: codeflying-user-info
description: 获取 CodeFlying 当前登录用户信息，包括用户名、租户、会员状态等
---

# 获取当前用户信息

## Description
获取 CodeFlying 平台当前登录用户的详细信息，包括用户基本信息、租户信息、会员状态等。

## When to use
- 用户说："我的账号信息"
- 用户说："查看我的会员状态"
- 用户说："我是谁"
- 用户说："查看积分"、"还有多少积分"、"剩余积分"
- 需要获取当前用户 ID 或租户 ID 时

## ⚠️ 关键规则：积分数据必须每次重新查询
- **积分是实时变化的**（应用开发消耗、充值、会员续期等都会改变积分余额）。
- **严禁使用历史对话中缓存的旧积分数据**。即使之前的对话中已经查询过积分，也必须重新执行此脚本获取最新数据。
- 用户每次要求查看积分时，都要运行 `python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-user-info/user_info.py`，不得跳过。

## How to use
```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-user-info/user_info.py --sender_id "xxx_xxxx。必填，对话传入的发送者ID"
```

### 输出示例
```json
{
  "user_info": {
    "user_id": 1,
    "username": "test@example.com",
    "show_name": "测试用户"
  },
  "tenant_info": {
    "tenant_id": 1,
    "billing_type": "free_monthly"
  }
}
```

## Edge cases
- Token 过期：提示用户重新登录
- 网络异常：提示稍后重试
