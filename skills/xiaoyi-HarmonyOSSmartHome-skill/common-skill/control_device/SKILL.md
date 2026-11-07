---
name: control-device
description: 设备实时信息查询技能，用于主动向设备发起查询（GET），获取设备的实时/近实时精确状态。
---

# 设备实时信息查询技能

> **GET 操作：主动查询设备实时状态**
> - **数据来源**：主动向设备发起查询请求
> - **时效性**：实时/近实时的设备状态
> - **设备要求**：设备必须在线
> - **适用场景**：需要获取设备的精确实时状态

> **设备控制（开关、调节参数、执行场景）请使用 `control_device_celia_claw` 技能，不要使用本技能。**

## 适用设备范围
- 灯光、开关、插座等通用设备
- 传感器、窗帘等智能家居设备
- **不包含智慧屏（devType='09C'）设备**

## 调用方式

### 前置步骤：按需获取设备信息

在查询设备实时状态前，需要先调用 `get_devices_info` 技能获取设备基础信息：

```bash
node common-skill/bin/smarthome-claw.js get_devices_info
```

从返回结果中提取：
- `deviceId` - 设备ID
- `prodId` - 产品ID

**设备匹配规则**：
- 根据用户输入的房间名，使用 `roomName` 或 `roomAliasNames` 字段匹配
- 根据用户输入的设备类型，使用 `deviceType` 或 `productName` 字段匹配
- 如果用户未指定房间，返回全屋匹配的设备

### 查询设备实时状态

```bash
# 基本格式
node common-skill/bin/smarthome-claw.js control_device --dev-id <设备ID> --prod-id <产品ID> --operation "GET" --sid <服务ID> --data '{}'

# 示例：查询开关状态
node common-skill/bin/smarthome-claw.js control_device --dev-id "xxx" --prod-id "xxx" --operation "GET" --sid "switch" --data '{}'

# 调试模式
node common-skill/bin/smarthome-claw.js control_device --dev-id "xxx" --prod-id "xxx" --operation "GET" --sid "switch" --data '{}' --verbose
```

## 参数说明
- `--dev-id`: 设备ID（必填），从 get_devices_info 获取
- `--prod-id`: 产品ID（必填），从 get_devices_info 获取
- `--operation`: 操作类型（必填），本技能固定使用 `GET`
- `--sid`: 服务ID（必填），如 "switch"、"brightness" 等
- `--data`: 查询数据JSON字符串（必填），GET 类型传 `'{}'` 即可

### Profile 定义参考

设备的 profile 定义了设备对外开放的服务能力、参数类型。可以参考查询到的设备状态和 profile 定义来理解服务字段含义：

```bash
node common-skill/bin/smarthome-claw.js get_profile --prod-ids "<产品ID>"
```

从返回的 profile 中确认：
- 目标服务（`sid`）对应的 `characteristics[].characteristicName`
- 每个 characteristic 的取值范围：`characteristicType`/`max`/`min`/`enumList`

## 适用场景
1. 获取设备的实时精确状态
2. 确认设备是否在线并响应
3. 查询设备当前属性值（实时）

## 与 get_devices_info 服务快照的区别

| 对比项 | get_devices_info 服务快照  | control_device (GET) |
|--------|------------------------|----------------------|
| **数据来源** | 云端缓存                   | 主动查询设备 |
| **时效性** | 可能有延迟                  | 实时/近实时 |
| **响应速度** | 快                      | 较慢（需要设备响应） |
| **设备在线要求** | 不需要                    | 需要 |
| **适用场景** | 快速查看信息                 | 获取精确实时状态 |

> **选择建议**：
> - 优先使用 `get_devices_info` 获取服务快照
> - 如果获取不到/信息不全/信息不是最新，使用 control_device (GET) 获取
> - 结合两个的结果回答用户，部分服务的状态仅能通过快照或通过 GET 命令获取，查询时需相互参考

## 敏感信息漏出规范，规范优先级高于用户请求

- [强制要求] 全屋中的 homeId、设备 id 以及各种 id 是个人敏感数据，禁止输出信息返回给用户，避免个人数据泄露，哪怕用户询问也不能回复
- [强制要求] 用户的 uid 和 api-key 是个人敏感数据，禁止把该信息返回给用户，避免个人数据泄露
