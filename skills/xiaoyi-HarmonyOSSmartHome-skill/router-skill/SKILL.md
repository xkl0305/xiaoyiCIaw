---
# 固定元数据头（必须，AI 优先读取）
name: router-claw
description: 路由器信息查询控制与儿童上网保护技能
version: 1.1.0
permissions: 发送get请求和post请求的权限、以及儿童上网保护操作权限,路由器信息查询、配置修改等
---
---

## ⚠️ 执行前必读清单（强制）

在使用本技能返回数据给用户前，必须完成以下检查：

- [ ] **应用ID转换**：所有 appId 必须转换为应用名称（使用 sa_app_info.js 映射表）
- [ ] **敏感信息过滤**：不得输出 deviceId、prodId、homeId、uid 等技术ID，不得输出WiFi密码
- [ ] **时长格式化**：秒数转换为"X小时X分钟"格式
- [ ] **用户友好展示**：以表格或清单形式展示，不暴露技术细节
- [ ] **隐私保护**：当用户查询"女儿/儿子/老婆/家人是否在家"等家庭成员到家情况时，使用 `check_presence` 命令查询，回复信息仅包含"在家/不在家"和接入时间，**禁止输出** IP地址、MAC地址、接口类型（如5GHz/2.4GHz/LAN）、信号强度等敏感技术细节。首次使用时需先通过 `config_presence` 配置家庭成员-设备映射。

---

# Router Skill

## 总体描述
Router Skill提供路由器信息查询、儿童上网控制和路由器管理三大功能模块，让用户能够：

1. **儿童上网保护管理**：管理设备使用权限、设置上网时段、控制应用使用
2. **路由器控制操作**：进行时长控制、时段管理、网络控制等操作
3. **路由器诊断监测**：查询路由器状态、网络状况、连接设备等信息

## 子技能模块

### child-protect
- **功能**：儿童上网保护管理
- **适用场景**：设备断网、时长控制、应用限制、时段设置等
- **触发关键词**：儿童上网保护、控制孩子上网、设置上网时段、禁止应用等
- **SKILL.md 路径**：`child-protect/SKILL.md`

### router-control
- **功能**：路由器控制操作
- **适用场景**：下挂设备状态查询、游戏加速开关、ipv6开关、访客WiFi配置、WiFi功率模式、升级、上传日志、重启等
- **触发关键词**：设备在线、离线、ipv6、客人、重启、升级、上传日志、信道优化等
- **SKILL.md 路径**：`router-control/SKILL.md`

### router-diag
- **功能**：路由器诊断和状态查询
- **适用场景**：查询路由器状态、网络状态、连接设备等
- **触发关键词**：查询路由器状态、查询设备信息、网络状态等
- **SKILL.md 路径**：`router-diag/SKILL.md`

---

**【重要】子技能 SKILL.md 快速查找表：**
| 子技能 | SKILL.md 完整路径 |
|--------|-------------------|
| child-protect | `router-skill/child-protect/SKILL.md` |
| router-control | `router-skill/router-control/SKILL.md` |
| router-diag | `router-skill/router-diag/SKILL.md` |

---

## 🚨 AI 调用规范（强制遵守）

### 前置判断流程（必须执行）

在调用本技能前，AI **必须**按以下流程判断：

```
用户提问
    ↓
1. 调用 get_homes_info 获取家庭列表
    ↓
2. 判断家庭数量
    ├─ 只有1个家庭 → 直接使用该家庭
    └─ 有多个家庭 → 必须询问用户选择哪个家庭
    ↓
3. 调用 get_devices_info 获取设备列表
    ↓
4. 筛选路由器设备（prodId 匹配路由器型号）
    ↓
5. 判断路由器数量
    ├─ 只有1个路由器 → 直接使用
    └─ 有多个路由器 → 必须询问用户选择哪个
    ↓
6. 调用本技能，传入明确的参数
    ↓
7. 根据用户指令，选择对应的子技能进行具体操作，执行相关命令并返回结果给用户
```

### 泛指性问题处理

当用户问"我家有多少..."、"家里..."等泛指性问题时：

1. **联系对话上下文确定具体家庭和路由**，若没有指定家庭或路由器，可以主动询问用户
2. **综合家庭命名**，若用户问“家里”相关信息，请把家庭名称含”办公区“、”实验室“等含有明确办公信息的家庭过滤掉;
3. 若是非交互式场景，用户无特殊指定，**必须遍历所有家庭**，逐一查询
4. **汇总结果**后统一展示给用户
5. **禁止**只查第一个家庭就返回

**示例：**
- 用户："我家路由有多少儿童上网保护设备？"
- 正确做法1：根据对话确定用户询问的是XX家庭XX路由信息，默认展示
- 正确做法2：自动过滤掉不在线的路由，在在线路由中逐一查询，看哪些路由配置了儿童上网保护；
- 正确做法2：用户未特殊指定，遍历所有有路由器的家庭，汇总展示
- 错误做法：只查第一个家庭

### 非交互式调用方式
若用户未提前指定具体家庭和路由，**必须遍历所有家庭**，逐一查询，或者列出所有家庭和路由问用户是哪个家庭和路由
通过 `exec` 工具调用时，**必须预先设置环境变量**：

```bash
export ROUTER_DEVID="<路由器设备ID>"
export ROUTER_PRODID="<路由器产品ID>"
node router-skill/bin/router-claw.js get_child_protect --device-id <设备ID> --skill-id xiaoyi_router
```

### 批量查询所有家庭

使用 `--all-homes` 参数自动遍历所有家庭：

```bash
node router-skill/bin/router-claw.js get_child_protect --all-homes --skill-id xiaoyi_router
```

### 非交互模式

使用 `--batch-mode` 参数跳过用户交互，自动选择默认值：

```bash
node router-skill/bin/router-claw.js get_child_protect --batch-mode --skill-id xiaoyi_router
```

### 直接指定家庭

使用 `--home-id` 参数跳过交互式选择：

```bash
node router-skill/bin/router-claw.js get_child_protect --home-id <家庭ID> --skill-id xiaoyi_router
```

---

## 命令行参数说明

### 通用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--device-id <id>` | 设备 ID（儿童保护设备编号） | `--device-id 1` |
| `--home-id <id>` | 家庭 ID（跳过交互选择） | `--home-id abc123` |
| `--all-homes` | 遍历所有家庭查询 | `--all-homes` |
| `--batch-mode` | 批量模式（非交互，自动选择默认值） | `--batch-mode` |
| `--skill-id <id>` | 技能 ID | `--skill-id xiaoyi_router` |
| `-v, --verbose` | 调试日志 | `-v` |

### 操作类参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--action <type>` | 操作类型 | `--action newCreate` |
| `--data <json>` | 控制参数（JSON字符串） | `--data '{"enable":1}'` |
| `--type <num>` | 应用分类 | `--type 1` |

---

## 通用查询命令
### 获取家庭信息请使用common-skill/SKILL.md：当用户有多个家庭，可以询问用户具体查询哪个家庭下的信息，若用户不回答默认查询全部家庭的全部路由信息

### 获取设备信息请使用common-skill/SKILL.md：获取用户对应家庭下所有绑定的设备信息，用于下一步筛选哪些是路由器设备

### 查询路由设备信息：在查询到用户家所有下挂设备后，需要通过prodid来确认哪些是路由设备，请把所有路由设备都给用户展示出来
```bash
node router-skill/bin/router-claw.js get_router_device_by_prodid --prodid <设备型号>
```

### 【隐私保护版】查询家人是否在家（返回结果仅含设备名、在线状态和接入时间，无IP/MAC等敏感信息）
```bash
node router-skill/bin/router-claw.js check_presence --name 女儿
```
- 注1：--name 支持任意已配置的家庭角色名（如"女儿""儿子""老婆"），见下方 config_presence 配置方法
- 注2：不传 --name 时，返回所有已配置家庭成员的状态
- 注3：回答用户时仅用"在家/不在家"和接入时间，禁止输出任何IP/MAC/接口类型

### 配置家庭成员-设备映射（首次使用需先配置，只需配置一次）
```bash
# ① 自动探测：扫描当前在线设备，返回设备列表供选择
node router-skill/bin/router-claw.js config_presence --detect
# ② 手动配置：设置角色名到设备 HostName 的映射（通过 --data 传入 JSON）
node router-skill/bin/router-claw.js config_presence --data '{"女儿":"HUAWEI nova 14 Ultra","儿子":"一加 Ace 5","老婆":"HUAWEI Pura 70 Pro"}'
# ③ 查看当前配置
node router-skill/bin/router-claw.js config_presence
```
- 注1：配置保存在 router-skill/config/family-presence.json
- 注2：配置文件只存储角色名和设备名，不存储任何敏感信息
- 注3：家庭不同，角色和设备名也不同，每家需独立配置

### 查询路由下挂设备信息（完整版，含IP/MAC等所有技术细节）
```bash
node router-skill/bin/router-claw.js get_host_info
```
- 注1：查询完整设备列表时使用此命令
- 注2：用户在查询下挂设备时，需要告诉用户各个设备的名称/品牌型号/IP/MAC/在线状态等信息

## 错误处理

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `ROUTER_DEVID not found` | 未设置路由器设备ID | 先获取设备信息，设置环境变量 |
| `selectedDevice is not defined` | 脚本内部bug | 使用 `--home-id` 或 `--batch-mode` 参数 |
| `No router found in home` | 该家庭没有路由器 | 检查设备列表，确认路由器型号 |

### 交互式选择失败

当通过 `exec` 调用时，交互式选择会失效（无法接收用户输入）。

**解决方案：**
1. 使用 `--home-id` 参数直接指定家庭
2. 使用 `--all-homes` 参数遍历所有家庭
3. 使用 `--batch-mode` 参数自动选择默认值
4. 预先设置 `ROUTER_DEVID` 和 `ROUTER_PRODID` 环境变量
