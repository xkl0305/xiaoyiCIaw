# Token 刷新指南

## 目录

- [Token 存储说明](#token-存储说明)
- [刷新条件](#刷新条件)
- [刷新流程](#刷新流程)
- [错误处理](#错误处理)

---

## Token 存储说明

Token 信息存储在 `.xiaoyienv` 文件中：

| 键名 | 说明 |
|------|------|
| `108635313_login_token` | 登录 Token |
| `108635313_login_token_expire_time` | Token 过期时间（时间戳） |

---

## 刷新条件

满足以下任一条件时刷新 Token：

1. **兼容历史版本**：`.xiaoyienv` 中不存在 `108635313_login_token` 字段 → 跳过刷新，使用 `USER_CREDENTIAL_TEMP_DRIVE_TOKEN` 执行任务
2. **Token 已过期**：`108635313_login_token` 存在且当前时间 > `108635313_login_token_expire_time` → 调用 `huawei_id_tool` 刷新
3. **执行报错**：`huawei_drive.py` 返回 `TOKEN_EXPIRED` 错误 → 调用 `huawei_id_tool` 刷新

---

## 刷新流程

### 执行步骤

1. **检查 Token 状态**：读取 `.xiaoyienv` 中的 `108635313_login_token` 和 `108635313_login_token_expire_time`
2. **调用刷新工具**：

```
工具名称：huawei_id_tool
参数：
  - clientId: 108635313
  - skillName: huawei-drive
```

3. **验证刷新结果**：刷新成功后，重新读取 `.xiaoyienv` 验证 Token 已更新
4. **重试原操作**：使用新 Token 重新执行原 `huawei_drive.py` 命令

### 流程图

```
开始操作
    ↓
检查 Token 状态
    ↓
是否需要刷新？
    ├─ 否 → 直接执行 huawei_drive.py
    └─ 是 → 调用 huawei_id_tool 刷新 Token
             ↓
         刷新成功？
             ├─ 否 → 提示用户授权已失效，需重新启动小艺Work
             └─ 是 → 重新执行 huawei_drive.py
```

---

## 错误处理

| 场景 | 处理逻辑 | 输出文案 |
|------|---------|---------|
| **Token 刷新失败** | 终止操作，提示用户重新授权 | `❌ 授权已失效，请退出小艺Work，再次启动小艺Work重新获取授权后重试。` |
| **Token 刷新成功** | 重新执行原操作 | （继续执行，无需额外提示） |
| **刷新后仍报 TOKEN_EXPIRED** | 终止操作，提示用户重新授权 | `❌ 授权已失效，请退出小艺Work，再次启动小艺Work重新获取授权后重试。` |

---

## 最佳实践

1. **操作前检查**：在执行任何 `huawei_drive.py` 命令前，先检查 Token 状态
2. **单次刷新**：每个操作周期只刷新一次 Token，避免重复刷新
3. **及时重试**：刷新成功后立即重试原操作，不要延迟
4. **错误反馈**：刷新失败时清晰告知用户需要重新授权
