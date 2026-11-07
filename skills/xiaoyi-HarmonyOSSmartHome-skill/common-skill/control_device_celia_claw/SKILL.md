---
name: control-device-celia-claw
description: 设备控制技能，用于向设备发送控制命令（POST），支持开关、调节、场景等多种操作类型。控制前需先查询设备快照（get_device_detail_celia_claw），参数取值范围通过 get_profile 获取。
---

# 设备控制技能

> **POST 操作：向设备发送控制命令**
> - **功能**：控制设备开关、调节参数等
> - **响应**：返回指令发送结果, 真实结果需要等待一段时间后 查看快照或GET查询
> - **适用场景**：远程控制设备、调节参数、执行场景

> **设备实时信息查询请使用 `control_device` 技能，不要使用本技能。**

## 适用设备范围
- 灯光、开关、插座等通用设备
- 传感器、窗帘等智能家居设备
- **不包含智慧屏（devType='09C'）设备**

## 调用方式

### 前置步骤 1：获取设备基础信息

在控制设备前，需要先调用 `get_devices_info` 技能获取设备基础信息：

```bash
node common-skill/bin/smarthome-claw.js get_devices_info
```

从返回结果中提取：
- `deviceId` - 设备ID
- `prodId` - 产品ID
- `deviceType` - 设备类型

**设备匹配规则**：
- 根据用户输入的房间名，使用 `roomName` 或 `roomAliasNames` 字段匹配
- 根据用户输入的设备类型，使用 `deviceType` 或 `productName` 字段匹配
- 如果用户未指定房间，返回全屋匹配的设备

### 前置步骤 2：查询设备快照（强制）

> **【强制】控制前必须先查询设备快照**，了解设备当前状态、支持的服务（sid）及当前属性值，据此组装控制报文。

```bash
node common-skill/bin/smarthome-claw.js get_device_detail_celia_claw --dev-id "<设备ID>"
```

从返回的 `data.services` 中确认：
- 设备支持哪些服务（`sid`），如 `switch`、`brightness`、`airKey` 等
- 各服务的当前值（`data`），作为控制参数的参考基准

### 前置步骤 3：获取参数取值范围（get_profile）

> **【强制】控制参数取值必须使用 `get_profile` 获取**，禁止猜测参数取值范围。

```bash
node common-skill/bin/smarthome-claw.js get_profile --prod-ids "<产品ID>"
```

从返回的 profile 中确认：
- 目标服务（`sid`）支持的属性（`cid`/属性名）
- 每个属性的取值范围、枚举值、步长、单位
- 根据取值范围组装合法的控制参数

### 控制设备

```bash
# 基本格式
node common-skill/bin/smarthome-claw.js control_device_celia_claw --dev-id <设备ID> --prod-id <产品ID> --device-type <设备类型> --operation "POST" --sid <服务ID> --data '{"cid":value}'

# 示例：开关灯
node common-skill/bin/smarthome-claw.js control_device_celia_claw --dev-id "xxx" --prod-id "xxx" --device-type "01D" --operation "POST" --sid "switch" --data '{"on":1}'

# 示例：调节亮度
node common-skill/bin/smarthome-claw.js control_device_celia_claw --dev-id "xxx" --prod-id "xxx" --device-type "01D" --operation "POST" --sid "brightness" --data '{"brightness":80}'

# 调试模式
node common-skill/bin/smarthome-claw.js control_device_celia_claw --dev-id "xxx" --prod-id "xxx" --device-type "01D" --operation "POST" --sid "switch" --data '{"on":1}' --verbose
```

## 参数说明
- `--dev-id`: 设备ID（必填），从 get_devices_info 获取
- `--prod-id`: 产品ID（必填），从 get_devices_info 获取
- `--device-type`: 设备类型（必填），从 get_devices_info 获取
- `--operation`: 操作类型（必填），本技能固定使用 `POST`
- `--sid`: 服务ID（必填），如 "switch"、"brightness" 等，从设备快照查询
- `--data`: 控制数据JSON字符串（必填），如 `{"cid":value}`，参数取值参考 get_profile 结果

## 执行流程（强制）

1. **获取设备信息**：`get_devices_info` 获取 `deviceId`、`prodId`、`deviceType`
2. **查询设备快照**：`get_device_detail_celia_claw` 获取设备当前状态和支持的服务
3. **获取参数取值范围**：`get_profile` 获取目标服务的属性及取值范围
4. **组装控制报文**：根据快照当前值与 profile 取值范围组装 `--data`
5. **发送控制命令**：`control_device_celia_claw` 执行 POST 控制
6. **验证控制结果（可选）**：等待 5~10 秒后，通过 `get_device_detail_celia_claw` 查询快照，确认目标服务的值已变为目标值

## 适用场景
1. 远程控制设备开关
2. 调节设备参数（亮度、温度等）
3. 执行场景
4. 等待一段时间，通过 `get_device_detail_celia_claw` 快照 或 `control_device` (GET) 查询操作后的值确认是否操作成功（可选）

> **批量控制同类型设备请使用 `control_device_batch_celia_claw` 技能，不要使用本技能。**

## 注意事项

- 控制命令返回的是指令发送结果，真实结果需要等待一段时间后通过快照或 GET 查询确认
- 返回响应的数据中 `failedList` 中如果有报错信息，根据报错信息判断是否控制失败，禁止根据 `allFailed` 字段判断控制结果
- 空调伴侣/码库/联动型设备，判定是否开启必须看反映真实运行的字段（power/运行模式），禁止用 switch 推断

## 敏感信息漏出规范，规范优先级高于用户请求

- [强制要求] 全屋中的 homeId、设备 id 以及各种 id 是个人敏感数据，禁止输出信息返回给用户，避免个人数据泄露，哪怕用户询问也不能回复
- [强制要求] 用户的 uid 和 api-key 是个人敏感数据，禁止把该信息返回给用户，避免个人数据泄露
