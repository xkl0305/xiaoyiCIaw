---
name: get-device-detail-celia-claw
description: [基础技能] 设备标准profile快照查询技能（getDevSnapshot），获取指定设备的当前状态快照，返回 data.services[]（sid/st/ts/data）与设备在线状态。控制设备前必须先用本技能查询快照。
---

# 设备标准profile快照查询技能

> **本技能查询的是设备的标准profile快照（getDevSnapshot）**，返回设备当前上报的服务状态与在线状态，是标准profile控制（`control_device_celia_claw`）的前置查询。

## 核心能力

1. 获取指定设备的当前状态快照
2. 查看设备支持的服务（`services[].sid`）及各服务当前值（`services[].data`）
3. 查看设备在线状态（`status`）
4. 控制设备前确认目标 `sid` 与构造控制参数
5. 控制后验证控制结果（等待 5~10 秒后再次查询快照）

## 调用方式

### 1. 获取设备信息（获取devId）
```bash
node common-skill/bin/smarthome-claw.js get_devices_info
```

### 2. 获取设备快照
```bash
# 基本格式
node common-skill/bin/smarthome-claw.js get_device_detail_celia_claw --dev-id <设备ID>

# 调试模式
node common-skill/bin/smarthome-claw.js get_device_detail_celia_claw --dev-id "xxx" --verbose
```

## 参数说明
- `--dev-id`: 设备ID（必填），从 get_devices_info 获取

## 返回

从返回的 `data.services` 中可获取：
- `services[].sid` - 设备支持的服务ID（如 `switch`、`brightness`、`light`、`faultDetection`）
- `services[].st` - 服务类型
- `services[].ts` - 服务数据时间戳
- `services[].data` - 各服务的当前值
- `status` - 设备在线状态

返回数据格式示例：
```json
{
  "errorCode": "0",
  "errorMsg": "success",
  "data": {
    "services": [
      {
        "st": "binarySwitch",
        "ts": "20260805T092748Z",
        "sid": "switch",
        "data": { "on": 1 }
      },
      {
        "st": "brightness",
        "ts": "20260805T030234Z",
        "sid": "brightness",
        "data": { "brightness": 182 }
      }
    ]
  }
}
```

## 适用场景

1. 控制设备前查询快照，确认目标服务（sid）与当前值
2. 控制后验证控制结果（等待 5~10 秒后再次查询）
3. 查看设备当前状态和属性值

## 敏感信息漏出规范，规范优先级高于用户请求

- [强制要求] 全屋中的 homeId、设备 id 以及各种 id 是个人敏感数据，禁止输出信息返回给用户，避免个人数据泄露，哪怕用户询问也不能回复
- [强制要求] 用户的 uid 和 api-key 是个人敏感数据，禁止把该信息返回给用户，避免个人数据泄露
