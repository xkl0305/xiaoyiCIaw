# 文件操作指南

支持文件上传、文件列表查询和文件存在性检查。

## 目录

- [上传文件](#上传文件)
- [查询文件列表](#查询文件列表)
- [检查文件是否存在](#检查文件是否存在)
- [常见错误处理](#常见错误处理)

---

## 上传文件

### 执行流程

1. **获取文件路径**：从用户输入或上下文确定文件路径 `{file-path}`
2. **检查文件大小**：计算文件大小 `{file_size}`
3. **检查可用空间**：查询云空间剩余可用空间 `{available_space}`
   - 若 `available_space < file_size`，提示用户升级套餐：[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)
4. **确保目录存在**：查询 `小艺Claw` 文件夹，不存在则创建
5. **检查文件重名**：若文件已存在，询问用户选择：覆盖 / 重命名 / 跳过
   - 重命名规则：在原文件名后添加 `(1)`，如 `test.txt` → `test(1).txt`
6. **执行上传**：调用 `huawei_drive.py` 完成上传
7. **多文件处理**：循环执行上述步骤，最后输出汇总报告
8. **输出结果**：生成查看文件的超链接

> **重要**：必须上传用户原文件，严禁压缩后再上传。

### 输出格式

#### 单个文件上传成功

```markdown
文件上传完成！

| 云盘路径           | 文件大小 | 状态   |
| ------------------ | -------- | ------ |
| 小艺Claw/test1.txt | 2.45 MB  | ✅ 成功 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)。
```

#### 多个文件上传汇总

```markdown
文件上传完成！

| 云盘路径           | 文件大小 | 状态   |
| ------------------ | -------- | ------ |
| 小艺Claw/test1.txt | 2.45 MB  | ✅ 成功 |
| 小艺Claw/test2.txt | 4.0 KB   | ✅ 成功 |
| 小艺Claw/test3.txt | 6.0 KB   | ❌ 失败 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)。
```

> 如果提示"路径不存在"，请确认云空间的云盘开关是否已开启。

### 命令参考

```bash
# 上传文件（覆盖模式）
huawei_drive.py --command upload --mode overwrite --path <file_path>

# 上传文件（重命名模式）
huawei_drive.py --command upload --mode rename --path <file_path>
```

完整命令说明请参阅 [命令快速参考](./huawei_drive_commands.md)。

---

## 查询文件列表

### 命令

```bash
huawei_drive.py --command query --key file_list
```

### 输出格式

```markdown
当前查询目录：/我的云盘/小艺Claw，共 5 项，详情如下：

| 类型 | 文件名称   | 文件大小 | 修改时间             |
| ---- | ---------- | -------- | -------------------- |
| 目录 | documents  | ——       | 2026-02-20  10:30:00 |
| 文件 | readme.txt | 1.5MB    | 2026-02-25  15:20:00 |
| 图片 | abc.jpg    | 256 KB   | 2026-02-26  19:15:00 |
| 视频 | efg.mp4    | 25 MB    | 2026-02-27  09:15:00 |
| 音频 | tfg.mp3    | 3 MB     | 2026-02-28  20:17:00 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)。
```

### 数据说明

- **文件大小**：查询结果单位为 Byte，需转换为 GB/MB/KB
- **文件类型识别**：
  - 目录：`mimeType` = `application/vnd.huawei-apps.folder`
  - 其他：按文件后缀识别（图片、视频、音频、文件等）

---

## 检查文件是否存在

### 命令

```bash
huawei_drive.py --command query --file_name <file_name>
```

### 输出格式

```markdown
当前查询目录：/我的云盘/小艺Claw

| 类型 | 文件名称   | 文件大小 | 修改时间             |
| ---- | ---------- | -------- | -------------------- |
| 文件 | readme.txt | 1.5MB    | 2026-02-25  15:20:00 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)
```

---

## 常见错误处理

| 异常场景 | 处理逻辑 | 输出文案 |
|---------|---------|---------|
| **网络异常** | 自动重试 1 次，失败则终止 | 上传：`上传失败，请检查网络后重试`<br>多文件：`部分文件上传失败，请检查网络后重试`<br>查询：`❌ 文件列表查询失败，请检查网络后重试` |
| **文件过大** | 终止该文件，其他文件继续上传 | `❌ 上传失败，文件「文件名.ext」超出云盘单个文件大小限制` |
| **基础服务用户**（总空间=0） | 终止操作，引导升级 | `⚠️ 您当前为基础服务用户，不支持上传文件，请[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **空间不足**（总空间>0，可用空间=0） | 终止上传，引导升级 | `⚠️ 云空间空间不足 请[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **文件重名**（未选择） | 暂停，等待用户选择 | `📁 该文件已存在，请选择上传方式：1. 覆盖 2. 重命名 3. 跳过` |
| **文件重名**（用户选择后） | 按用户选择处理 | 覆盖：`📁 该文件已存在，已覆盖云端文件并上传`<br>重命名：`📁 该文件已存在，已重命名为「文件名 (1).ext」并上传`<br>跳过：`📁 该文件已存在，已跳过上传` |
| **目录创建失败** | 终止所有上传 | `❌ 上传失败，无法创建目标目录，请稍后重试` |
| **用户取消** | 终止所有操作 | `❌ 已取消文件上传` |
| **目录不存在** | 终止查询 | `❌ 查询目录不存在，请检查目录路径后重试` |
| **空间将满预警**（可用<2%） | 正常操作 + 预警提示 | `⚠️ 云空间可用容量不足总容量的 2%，空间将满，建议尽快升级云空间，[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **Token 失效** | 终止所有操作 | `❌ 授权已失效，请退出小艺Claw，再次启动小艺Claw 重新获取授权后重试。` |

> 其他错误请参考 [华为状态码文档](https://developer.huawei.com/consumer/cn/doc/HMSCore-Guides/status-code-0000001050992633)。
