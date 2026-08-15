---
name: pet-status
description: 宠物状态查询技能。当用户询问宠物状态、宠物怎么样、猫砂盆用了多少次、喂食器今天出了几次粮等与宠物生活状态相关的话题时使用此技能。
---

# 宠物状态查询

## 技能说明

本技能用于查询宠物的综合生活状态，包括：
- 猫砂盆使用次数和最后使用时间
- 喂食器出粮次数和最后出粮时间
- 室内温度和湿度
- 宠物大致位置

---

## 功能一：宠物状态全景查询

### 功能说明

获取家中所有宠物相关设备的综合状态，一键查询全面了解宠物独自在家的情况。

### 执行命令

```bash
node default-spec-skill/pet-care/bin/pet-care-claw.js get_pet_status
```

### 返回字段说明

| 字段 | 说明 |
|------|------|
| code | 状态码（SUCCESS/DEVICE_OFFLINE/PARTIAL_OFFLINE） |
| message | 状态消息 |
| catLitter.useCount | 猫砂盆今日使用次数 |
| catLitter.lastUseTime | 最后使用时间 |
| catLitter.online | 猫砂盆是否在线 |
| feeder.feedCount | 喂食器今日出粮次数 |
| feeder.lastFeedTime | 最后出粮时间 |
| feeder.portionSize | 每次出粮量（克） |
| feeder.online | 喂食器是否在线 |
| temperature.value | 当前温度（°C） |
| temperature.humidity | 当前湿度（%） |
| temperature.isAbnormal | 温度是否异常（>26°C） |
| temperature.shouldTurnOnAc | 是否建议开空调 |
| petLocation.location | 宠物位置 |
| petLocation.source | 数据来源 |

### 错误码说明

| 错误码 | 说明 |
|--------|------|
| SUCCESS | 查询成功 |
| DEVICE_OFFLINE | 所有宠物设备离线 |
| PARTIAL_OFFLINE | 部分设备离线 |
| TEMP_UNAVAILABLE | 温度数据不可用 |

---

## 功能二：宠物设备列表查询

### 功能说明

获取家中所有宠物相关设备的列表（已按类型分类）。

### 执行命令

```bash
node default-spec-skill/pet-care/bin/pet-care-claw.js get_pet_devices
```

### 返回字段说明

| 字段 | 说明 |
|------|------|
| catLitter | 猫砂盆设备列表 |
| feeder | 喂食器设备列表 |
| petTracker | 宠物定位器列表 |
| tempHumiditySensor | 温湿度传感器列表 |
| airConditioner | 空调设备列表 |
| camera | 摄像头设备列表 |
| totalCount | 宠物相关设备总数 |

---

## 触发示例

- "宠物怎么样"
- "猫砂盆用了多少次"
- "喂食器今天出了几次粮"
- "家里温度多少"
- "猫在哪"

---

## 回复示例

```
【宠物状态】

🐱 猫砂盆：今日使用3次，最后使用14:30
🍽️ 喂食器：今日已喂食2次，最后喂食08:00
🌡️ 温度：28.5°C ⚠️ 温度偏高，湿度65%
📍 位置：客厅沙发（摄像头）
💡 建议开启客厅空调降温
```