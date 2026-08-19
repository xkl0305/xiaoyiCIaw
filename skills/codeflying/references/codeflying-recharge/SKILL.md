---
name: codeflying-recharge
description: 处理积分不足、积分即将不足、免费额度用完等情况，引导用户充值或升级会员。用户主动询问积分余额、如何充值、如何升级会员时也使用此技能。
---

# 积分查询与充值引导

## When to use
- 用户说："积分不够了"、"积分用完了"、"没有积分了"、"积分耗尽"
- 用户说："免费次数用完了"、"今日额度用完"、"免费额度不够"
- 用户说："怎么充值"、"如何购买积分"、"买积分"
- 用户说："升级会员"、"开通会员"、"会员怎么买"
- 用户说："还有多少积分"、"查看积分"、"剩余积分"

---

## 执行步骤

### 第一步：查询当前积分

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying_common/quota.py \
  --sender_id "[sender_id]"
```

### 第二步：根据输出回复

**输出包含 `QUOTA_CARD_SENT`**（wechatoa 渠道，卡片已直接发出）：
⛔ 直接结束，不再发任何消息。

**输出包含 `QUOTA_CARD_START`**（积分已用完，非 wechatoa 渠道）：

> 😅 您的开发积分已用完，升级会员或充值积分即可继续开发～
>
> [立即充值 / 升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query])

**输出包含 `LOW_POINTS_WARNING_SENT`**（wechatoa，低积分预警卡片已发）：
⛔ 直接结束，不再发任何消息。

**输出包含 `LOW_POINTS_WARNING:`**（积分即将不足，非 wechatoa）：
提取 `LOW_POINTS_WARNING:` 后面的数字作为剩余积分数：

> ⚠️ 您的积分余额即将不足（剩余 **[N]** 分），建议及时充值，避免开发中断。
>
> [立即充值 / 升级会员](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query])

**输出包含 `QUOTA_OK`（积分充足）**：
调用 user_info 获取详细积分后回复：

```bash
python3 ~/.nanobot-xiaofeifei/workspace/skills/codeflying/references/codeflying-user-info/user_info.py \
  --sender_id "[sender_id]"
```

根据输出中的积分数据自然回复，例如：

> 您目前还有 **[合计可用]** 积分，随时可以开发～
>
> 如需充值或升级会员：[点击这里](https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team&[auth_query])

---

## 充值 / 升级会员入口（固定链接）

| 场景 | 链接 |
|------|------|
| 充值积分 / 升级会员 | https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/team |
| 管理应用 | https://www.codeflying.net/codeflying_h5?login_wx=/pages/team/apps |
