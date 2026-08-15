---
name: pet-feeder
description: 宠物喂食控制技能。当用户说"喂一下猫"、"手动喂食"、"远程喂食"等与喂食控制相关的话题时使用此技能。
---

# 宠物喂食控制

## 技能说明

本技能用于远程控制智能喂食器，支持：
- 手动触发喂食器出粮
- 指定出粮量
- 获取喂食器当前状态

---

## 功能一：手动喂食

### 功能说明

远程触发喂食器出粮，适合主人不在家时需要临时喂食的场景。

### 执行命令

```bash
# 默认出粮量（20克）
node default-spec-skill/pet-care/bin/pet-care-claw.js control_feeder

# 指定出粮量
node default-spec-skill/pet-care/bin/pet-care-claw.js control_feeder --portion 30

# 指定设备ID
node default-spec-skill/pet-care/bin/pet-care-claw.js control_feeder --device-id xxxxx --portion 25
```

### 返回字段说明

| 字段 | 说明 |
|------|------|
| code | 状态码 |
| message | 状态消息 |
| deviceId | 设备ID |
| deviceName | 设备名称 |
| roomName | 房间名称 |
| success | 是否成功 |
| feedTime | 喂食时间 |
| portionSize | 出粮量（克） |
| online | 设备是否在线 |

### 错误码说明

| 错误码 | 说明 |
|--------|------|
| SUCCESS | 喂食成功 |
| DEVICE_OFFLINE | 喂食器离线 |
| NO_FEEDER | 未找到喂食器设备 |
| CONTROL_FAILED | 控制命令执行失败 |
| TIMEOUT | 命令执行超时 |

---

## 触发示例

- "喂一下猫"
- "手动喂食"
- "远程喂食"
- "给猫加点粮"
- "出粮30克"

---

## 回复示例

成功：
```
✅ 喂食成功
设备：智能喂食器（餐厅）
出粮量：20克
时间：15:00
```

失败（设备离线）：
```
❌ 喂食失败
设备：智能喂食器（餐厅）
原因：喂食器当前离线，请检查设备连接
```

---

## 注意事项

1. 喂食器必须在线才能执行控制命令
2. 不同品牌的喂食器可能使用不同的服务ID，系统会自动尝试多种组合
3. 如果喂食失败，建议检查设备电源和网络连接
4. 频繁喂食可能对宠物健康不利，建议合理安排喂食计划