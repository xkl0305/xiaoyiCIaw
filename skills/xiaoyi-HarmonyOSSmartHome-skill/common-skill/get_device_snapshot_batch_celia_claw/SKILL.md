---
name: get-device-snapshot-batch-celia-claw
description: 批量获取设备快照技能（标准profile），对多台设备同时查询快照时使用，payload 仅含 deviceIds 数组（operation: GET）。
---

# 批量获取设备快照技能

> **batchGetDevSnapshot：批量查询设备快照**
> - **功能**：对多台设备批量查询设备快照
> - **接口**：batchGetDevSnapshot（标准profile）
> - **operation**：`GET`
> - **payload**：仅含一个字段 `deviceIds`（数组，取 devId，至少 1 个）

## 适用设备范围
- 灯光、开关、插座等通用设备
- 传感器、窗帘等智能家居设备
- **不包含智慧屏（devType='09C'）设备**

## 调用方式

### 前置步骤：获取设备信息

在批量查询快照前，需要先调用 `get_devices_info` 技能获取设备基础信息：

```bash
node common-skill/bin/smarthome-claw.js get_devices_info
```

从返回结果中提取 `deviceId`（devId）列表。

### 批量获取设备快照

```bash
# 基本格式
node common-skill/bin/smarthome-claw.js get_device_snapshot_batch_celia_claw --device-ids "id1,id2,id3"

# 调试模式
node common-skill/bin/smarthome-claw.js get_device_snapshot_batch_celia_claw --device-ids "id1,id2,id3" --verbose
```

## 参数说明
- `--device-ids`: 设备ID数组（逗号分隔，至少 1 个），取 devId

## 返回

返回每个设备的快照数据，从返回结果中可获取：
- `services[].sid` - 设备支持的服务ID（如 `light`、`switch`、`faultDetection`）
- `services[].data` - 各服务的当前值
- `status` - 设备在线状态

该结果可用于批量控制时确认目标 `sid` 与构造 `data`。

## 适用场景
1. 批量查询多台设备的当前状态和属性值
2. 批量控制前确认设备支持的服务（sid）与当前值
3. 批量控制后验证控制结果（等待 5~10 秒后再次查询）

## 与 get_device_service_snapshot 的区别

| 对比项 | get_device_service_snapshot | get_device_snapshot_batch_celia_claw |
|--------|---------------------------|--------------------------------------|
| **接口** | getDevDynamicData（旧接口） | batchGetDevSnapshot（标准profile批量接口） |
| **返回结构** | 快照列表 | 快照列表 |
| **适用场景** | 批量查询快照（通用） | 批量查询快照（标准profile，配合 batchDevCommand 使用） |

## 敏感信息漏出规范，规范优先级高于用户请求

- [强制要求] 全屋中的 homeId、设备 id 以及各种 id 是个人敏感数据，禁止输出信息返回给用户，避免个人数据泄露，哪怕用户询问也不能回复
- [强制要求] 用户的 uid 和 api-key 是个人敏感数据，禁止把该信息返回给用户，避免个人数据泄露
