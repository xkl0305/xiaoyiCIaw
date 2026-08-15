---
name: lock-cateye
description: "智能门锁猫眼设置技能。用于设置智慧猫眼相关功能，包括猫眼开关、逗留抓拍、实时视频、畸变矫正等。"
---

# 门锁猫眼设置功能Skill

## 1. 必读项

本技能用于**控制**门锁的猫眼相关设置，包括猫眼开关、逗留抓拍、实时视频、畸变矫正等。。

### 服务ID（sid）
- **sid**: `catEyeSetting`

## 2. 触发关键字

当用户提到以下关键词时，应加载本技能：
- 猫眼
- 抓拍
- 逗留
- 实时视频
- 畸变矫正
- 按门铃亮屏
- 内屏
- 逗留录像

## 3. 用户语料示例

- "打开猫眼开关"
- "关闭猫眼"
- "打开逗留抓拍"
- "关闭逗留抓拍"
- "打开实时视频"
- "关闭实时视频"
- "打开畸变矫正"
- "关闭畸变矫正"
- "按门铃亮内屏"
- "设置逗留录像时长"

## 4. 调用示例

### 4.1 猫眼开关设置

#### 打开猫眼开关
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"peepholeEnableSwitch": 1}' \
  --verbose
```

#### 关闭猫眼开关
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"peepholeEnableSwitch": 0}' \
  --verbose
```

### 4.2 逗留抓拍设置

#### 打开逗留抓拍
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"staySnapshotSwitch": 1}' \
  --verbose
```

#### 关闭逗留抓拍
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"staySnapshotSwitch": 0}' \
  --verbose
```

### 4.3 实时视频设置

#### 打开实时视频
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"liveVideoSwitch": 1, "liveVideoDuration":0, "callValidPeriod":	0}' \
  --verbose
```

#### 关闭实时视频
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"liveVideoSwitch": 2}' \
  --verbose
```

### 4.4 畸变矫正设置

#### 打开畸变矫正
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"distortionCorrectionSwitch": 1}' \
  --verbose
```

#### 关闭畸变矫正
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"distortionCorrectionSwitch": 0}' \
  --verbose
```

### 4.5 按门铃亮内屏设置

#### 打开按门铃亮内屏开关
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"autoPowerScreen": 1}' \
  --verbose
```

#### 关闭按门铃亮内屏开关
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"autoPowerScreen": 0}' \
  --verbose
```

### 4.6 逗留时长设置

#### ⚠️ 逗留时长参数映射（关键规则）

the `stayDuration` 参数值与实际秒数不是一一对应的，必须使用以下映射表进行转换：

| 参数值 | 实际时长 |
|--------|----------|
| 0      | 立即录像 |
| 1      | 3 秒     |
| 3      | 6 秒     |
| 6      | 9 秒     |
| 12     | 15 秒    |
| 17     | 20 秒    |
| 27     | 30 秒    |
| 57     | 60 秒    |

**转换规则：**
1. **设置时**：用户说"设置逗留时长为 X 秒" → 查表找到对应的 **参数值** 传入 `stayDuration`
2. **查询时**：API 返回 `stayDuration: 12` → 查表转换为 **实际秒数** 告诉用户（如"逗留时长为15秒"）
3. **禁止直接使用用户说的秒数作为参数值**，必须通过映射表转换

#### 设置逗留时长为15秒（参数值12）
```bash
node common-skill/bin/smarthome-claw.js control_device \
  --dev-id "xxx" \
  --prod-id "xxx" \
  --operation "POST" \
  --sid "catEyeSetting" \
  --data '{"stayDuration": 12}' \
  --verbose
```

## 5. 注意事项

- 本技能仅支持控制，不支持查询操作
- **不支持查询逗留视频、查询按门铃抓拍等操作**
