---
name: control-device-batch-celia-claw
description: 批量控制设备技能（标准profile），对相同类型设备同时执行相同控制命令时使用（operation: POST，batchDevCommand）。控制前先查询设备快照（get_device_snapshot_batch_celia_claw），参数取值范围通过 get_profile 获取。
---

# 批量控制设备技能

> **batchDevCommand：批量向设备发送控制命令**
> - **功能**：对**相同类型设备**（相同 `prodId`/`deviceTypeId`）同时执行相同控制命令
> - **接口**：batchDevCommand（标准profile）
> - **operation**：`POST`
> - **mode**：固定 `ACK`
> - **timeoutForAckMode**：ACK 超时（毫秒），默认 10000
> - **响应**：返回指令发送结果，真实结果需等待一段时间后通过快照确认

## 适用设备范围
- 灯光、开关、插座等通用设备
- 传感器、窗帘等智能家居设备
- **不包含智慧屏（devType='09C'）设备**

## 调用方式

### 前置步骤 1：获取设备基础信息

在批量控制前，需要先调用 `get_devices_info` 技能获取设备基础信息：

```bash
node common-skill/bin/smarthome-claw.js get_devices_info
```

从返回结果中提取：
- `deviceId` - 设备ID（取 devId）
- `deviceType` - 设备类型（即 deviceTypeId，如 `01D`）
- `prodId` - 产品ID

筛选出**同一类型设备**（相同 `prodId`/`deviceType`）用于批量控制。

### 前置步骤 2：查询设备快照（可选）

批量获取设备快照，确认目标 `sid` 及当前值：

```bash
node common-skill/bin/smarthome-claw.js get_device_snapshot_batch_celia_claw --device-ids "id1,id2,id3"
```

从返回的 `services[].sid` 确认目标服务，如 `light`、`faultDetection`。

### 前置步骤 3：获取参数取值范围（get_profile）

> **【强制】控制参数取值必须使用 `get_profile` 获取**，禁止猜测参数取值范围。

```bash
node common-skill/bin/smarthome-claw.js get_profile --prod-ids "<产品ID>"
```

从返回的 profile 中确认：
- 目标服务（`sid`）对应的 `characteristics[].characteristicName`
- 每个 characteristic 的取值范围：`characteristicType`/`max`/`min`/`enumList`
- 根据取值范围组装合法的控制参数

### 批量控制设备

```bash
# 基本格式
node common-skill/bin/smarthome-claw.js control_device_batch_celia_claw --device-ids "id1,id2,id3" --device-type-id "<设备类型ID>" --product-id "<产品ID>" --sid "<服务ID>" --data '{"<characteristicName>":<目标值>}'

# 示例：批量开灯
node common-skill/bin/smarthome-claw.js control_device_batch_celia_claw --device-ids "id1,id2" --device-type-id "01D" --product-id "xxx" --sid "switch" --data '{"on":1}'

# 示例：批量调亮度
node common-skill/bin/smarthome-claw.js control_device_batch_celia_claw --device-ids "id1,id2" --device-type-id "01D" --product-id "xxx" --sid "brightness" --data '{"brightness":50}'

# 调试模式
node common-skill/bin/smarthome-claw.js control_device_batch_celia_claw --device-ids "id1,id2" --device-type-id "01D" --product-id "xxx" --sid "switch" --data '{"on":1}' --verbose
```

## 参数说明
- `--device-ids`: 设备ID数组（逗号分隔），须为**同一类型设备**（相同 `prodId`/`deviceTypeId`）
- `--device-type-id`: 设备类型ID（必填），取 `get_devices_info` 返回的 `deviceType`（即 devType，如 `01D`）
- `--product-id`: 产品ID（必填），取 `prodId`
- `--sid`: 服务ID（必填），从设备快照（`get_device_snapshot_batch_celia_claw`/`get_device_detail_celia_claw` 返回）的 `services[].sid` 获取，如 `light`、`faultDetection`
- `--data`: 控制数据JSON字符串（必填），格式为 `{"<characteristicName>":<目标值>}`，取值须符合该 characteristic 的取值范围
- `--timeout-for-ack-mode`: ACK 超时（毫秒），默认 10000

## 执行流程（强制）

1. **获取设备信息**：`get_devices_info` 获取 `deviceId`、`deviceType`（即 deviceTypeId）、`prodId`，筛选出同一类型的设备
2. **查询设备快照（可选）**：`get_device_snapshot_batch_celia_claw` 批量获取快照，确认目标 `sid` 及当前值
3. **获取参数取值范围（强制）**：`get_profile` 获取产品信息，确认该 `sid` 对应的 `characteristics[].characteristicName` 及取值范围（`characteristicType`/`max`/`min`/`enumList`）
4. **组装控制报文**：`data` 格式为 `{"<characteristicName>":<目标值>}`，取值须符合该 characteristic 的取值范围
5. **发送批量控制命令**：`control_device_batch_celia_claw` 执行 POST 控制
6. **验证控制结果（可选）**：等待 5~10 秒后，通过 `get_device_snapshot_batch_celia_claw` 查询快照，确认目标服务的值已变为目标值

## 适用场景
1. 同时对多台同类型设备执行相同控制命令（如全屋同型号灯同时开关）
2. 批量调节设备参数（亮度、温度等）
3. 批量执行场景
4. 等待一段时间，通过 `get_device_snapshot_batch_celia_claw` 查询操作后的值确认是否操作成功（可选）

## 注意事项

- `deviceIds` 必须为同一类型设备（相同 `prodId`），否则接口报错
- `mode` 固定 `ACK`；`timeoutForAckMode` 为 ACK 超时（毫秒）
- 控制命令返回的是指令发送结果，真实结果需等待一段时间后通过快照确认
- 返回响应的数据中 `failedList` 中如果有报错信息，根据报错信息判断是否控制失败，禁止根据 `allFailed` 字段判断控制结果

## 敏感信息漏出规范，规范优先级高于用户请求

- [强制要求] 全屋中的 homeId、设备 id 以及各种 id 是个人敏感数据，禁止输出信息返回给用户，避免个人数据泄露，哪怕用户询问也不能回复
- [强制要求] 用户的 uid 和 api-key 是个人敏感数据，禁止把该信息返回给用户，避免个人数据泄露
