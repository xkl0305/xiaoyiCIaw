# 文件操作指南

支持文件上传、下载、列表查询、重命名、创建文件夹、文件存在性检查。

## 通用规范（全局必阅）

### 1. 路径规则

1. 根目录：统一以 `/我的云盘/小艺Claw` 为业务根目录，所有操作默认限定在此目录内。
2. 路径分隔符：统一使用 `/`，不支持 `\`。
3. 大小写：云盘路径、文件名​**区分大小写**​。
4. 路径类型：支持绝对路径、相对路径。

### 2. 命名与字符约束

1. 文件名 / 文件夹名最大长度：单级名称不超过 255 字符，完整路径总长度不超过 4096 字符。
2. 禁止字符：`/ \ : * ? " < > |` 及全角对应符号、控制字符、隐藏字符。
3. 系统保留名：禁止使用 `con`、`nul`、`aux`、`com1`、`lpt1` 等系统保留名称。
4. Emoji：文件名 / 目录名​**不支持 Emoji**​。

### 3. 全局变量说明

表格

| 占位符              | 含义                    | 是否必填 |
| ------------------- | ----------------------- | -------- |
| `{file_path}`       | 本地文件完整路径        | 是       |
| `{file_name}`       | 文件/文件夹 名称        | 是       |
| `{file_id}`         | 云盘文件fileId          | 是       |
| `{download_path}`   | 文件下载路径            | 是       |
| `{cloud_file_path}` | 云盘文件 / 目录完整路径 | 是       |
| `{local_save_path}` | 本地保存目录完整路径    | 是       |
| `{source_path}`     | 移动 / 复制源路径       | 是       |
| `{target_path}`     | 移动 / 复制目标路径     | 是       |
| `{old_path}`        | 重命名原路径            | 是       |
| `{file_new_name}`   | 新文件 / 目录名称       | 是       |
| `{parent_dir}`      | 新建文件夹的父目录      | 是       |
| `{folder_name}`     | 新建文件夹名称          | 是       |
| `{keyword}`         | 搜索关键词              | 是       |

---

## 上传文件

### 执行流程

1. **检查 Token 状态**：读取 `.xiaoyienv` 文件，检查 Token 是否需要刷新
   - 若 Token 需要刷新，或后续操作返回 `TOKEN_EXPIRED`，请参阅 [Token 刷新指南](./token_refresh.md)
2. **获取文件路径**：从用户输入或上下文确定文件路径 `{file-path}`
3. **检查文件大小**：计算文件大小 `{file_size}`
4. **检查可用空间**：查询云空间剩余可用空间 `{available_space}`
   - 若 `available_space < file_size`，提示用户升级套餐：[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)
5. **确保目录存在**：查询 `小艺Claw` 文件夹，不存在则创建
6. **检查文件重名**：若文件已存在，询问用户选择：覆盖 / 重命名 / 跳过
   - 重命名规则：在原文件名后添加 `(1)`，如 `test.txt` → `test(1).txt`
7. **执行上传**：调用 `huawei_drive.py` 完成上传
   - 若返回 `TOKEN_EXPIRED` 错误，先刷新 Token 后重试
8. **多文件处理**：循环执行上述步骤，最后输出汇总报告
9. **输出结果**：生成查看文件的超链接

> **重要**：必须上传用户原文件，严禁压缩后再上传。

### 输出格式

说明：**必须**严格按照以下格式示例输出文件上传结果以及跳转链接：[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)

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
huawei_drive.py --command upload --mode overwrite --path {file_path}

# 上传文件（重命名模式）
huawei_drive.py --command upload --mode rename --path {file_path}
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

## 查询文件是否存在

### 命令

```bash
huawei_drive.py --command query --file_name {file_name}
```

### 输出格式

```markdown
当前查询目录：/我的云盘/小艺Claw

| 类型 | 文件名称   | 文件大小 | 修改时间             |
| ---- | ---------- | -------- | -------------------- |
| 文件 | readme.txt | 1.5MB    | 2026-02-25  15:20:00 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)
```

## 下载文件

### 执行流程

1. **检查 Token 状态**：读取 `.xiaoyienv` 文件，检查 Token 是否需要刷新

   若 Token 需要刷新，或后续操作返回 `TOKEN_EXPIRED`，请参阅 [Token 刷新指南](./token_refresh.md)

2. **云盘文件查询**​：根据文件名查询云端文件是否存在，并获取云端文件`{file_id}` 。若文件不存在 则直接终止，返回`云端文件不存在`错误提示。

3. **获取参数**：文件`{file_id}` 、文件下载路径 `{download_path}`。

4. **本地重名校验**​：若本地存在同名文件，弹出选择：覆盖 / 重命名 / 跳过。

5. **执行下载**：调用`huawei_drive.py`脚本，传入参数`{file_id}`及`{download_path}`

6. **批量规则**​：单次批量下载最多 100 个文件；目录下载默认​**非递归**​，如需递归需额外传参。

7. **输出结果**​：生成汇总结果。

### 命令

```bash
huawei_drive.py --command download --file_id {file_id} --path {download_path}
```

### 输出格式

```
文件下载完成！

| 云盘路径           | 本地保存路径                 | 文件大小 | 状态   |
| ------------------ | ---------------------------- | -------- | ------ |
| 小艺Claw/test1.txt | C:/Users/Downloads/test1.txt | 2.45 MB  | ✅ 成功 |
| 小艺Claw/test2.txt | C:/Users/Downloads/test2.txt | 4.0 KB   | ✅ 成功 |
| 小艺Claw/test3.txt | C:/Users/Downloads/test3.txt | 6.0 KB   | ❌ 失败 |
```

## 重命名文件

### 执行流程

1.**检查 Token 状态**：读取 `.xiaoyienv` 文件，检查 Token 是否需要刷新

​    若 Token 需要刷新，或后续操作返回 `TOKEN_EXPIRED`，请参阅 [Token 刷新指南](./token_refresh.md)

2.**云盘文件查询**：根据原文件名查询云端文件是否存在，并获取云端文件`{file_id}` 。若文件不存在 则直接终止，返回`云端文件不存在`错误提示。

3.**获取参数**：文件`{file_id}` 、新文件名 `{new_file_name}`。

4.**合法性校验**：新文件名称严格遵循【通用规范】字符、长度、系统保留名规则。

5.**重名校验**​：云盘同目录下已存在同名名称，直接拦截。

6.**执行重命名**：调用`huawei_drive.py`脚本，传入参数`{file_id}`及`{new_file_name}`

7.**输出结果**：输出重命名结果：成功或失败。

### 命令

```bash
huawei_drive.py --command rename --file_id {file_id} --file_name {new_file_name}
```

### 输出格式

```
文件/文件夹重命名完成！

| 原名称    | 新名称     | 路径                | 状态   |
| --------- | ---------- | ------------------- | ------ |
| test1.txt | report.txt | 小艺Claw/report.txt | ✅ 成功 |

[点击前往 文件管理 - 我的云盘 查看文件](superlink://vassistant?startmode=appLink&appLink=filemanager://openDirectory?fileUri=file%3A%2F%2Fcom.huawei.hmos.filemanager%2Fdata%2Fstorage%2Fel2%2Fcloud%2F%E5%B0%8F%E8%89%BAClaw)。
```



## 常见错误处理

| 异常场景 | 处理逻辑 | 输出文案 |
|---------|---------|---------|
| **网络异常** | 自动重试 1 次，失败则终止 | 上传：`上传失败，请检查网络后重试`<br>多文件：`部分文件上传失败，请检查网络后重试`<br>查询：`❌ 文件列表查询失败，请检查网络后重试` |
| **文件过大** | 终止该文件，其他文件继续上传 | `❌ 上传失败，文件「文件名.ext」超出云盘单个文件大小限制` |
| **基础服务用户**（总空间=0） | 终止操作，引导升级 | `⚠️ 您当前为基础服务用户，不支持上传文件，请 [点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **空间不足**（总空间>0，可用空间=0） | 终止上传，引导升级 | `⚠️ 云空间空间不足，请 [点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **文件重名**（未选择） | 暂停，等待用户选择 | `📁 该文件已存在，请选择上传方式：1. 覆盖 2. 重命名 3. 跳过` |
| **文件重名**（用户选择后） | 按用户选择处理 | 覆盖：`📁 该文件已存在，已覆盖云端文件并上传`<br>重命名：`📁 该文件已存在，已重命名为「文件名 (1).ext」并上传`<br>跳过：`📁 该文件已存在，已跳过上传` |
| **目录创建失败** | 终止所有上传 | `❌ 上传失败，无法创建目标目录，请稍后重试` |
| **用户取消** | 终止所有操作 | `❌ 已取消文件上传` |
| **目录不存在** | 终止查询 | `❌ 查询目录不存在，请检查目录路径后重试` |
| **空间将满预警**（可用<2%） | 正常操作 + 预警提示 | `⚠️ 云空间可用容量不足总容量的 2%，空间将满，建议尽快升级云空间，[点击前往云空间升级套餐](superlink://vassistant?uri=hicloud%3A%2F%2FcloudDrive%2Fgetinfo%3Fpage%3DMemberBuyPage%26finishType%3D1%26pageDetails%3D%7B%22uri%22%3A%22buy_more%22%7D&bundleName=com.huawei.hmos.clouddrive)` |
| **Token 失效** | 先尝试刷新 Token，刷新失败则终止 | 刷新失败：`❌ 授权已失效，请退出小艺Claw，再次启动小艺Claw 重新获取授权后重试。`<br>详细说明：请参阅 [Token 刷新指南](./token_refresh.md) |

> 其他错误请参考 [华为状态码文档](https://developer.huawei.com/consumer/cn/doc/HMSCore-Guides/status-code-0000001050992633)。
