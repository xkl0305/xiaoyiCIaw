# Huawei Drive 命令快速参考

## 目录

- [查询命令](#查询命令)
- [上传命令](#上传命令)
- [文件夹命令](#文件夹命令)

---

## 查询命令

### 查询云空间详情

```bash
huawei_drive.py --command query --key space
```

**返回**：云盘总空间、已用空间、可用空间（单位：Byte）

### 查询可用空间

```bash
huawei_drive.py --command query --key available_space
```

**返回**：int 类型，云空间剩余可用空间（单位：Byte）

### 查询文件列表

```bash
huawei_drive.py --command query --key file_list
```

**返回**：`小艺Claw` 文件夹下的所有文件列表

### 检查文件是否存在

```bash
huawei_drive.py --command query --file_name <file_name>
```

**返回**：
- 成功：文件详细信息
- 失败：失败原因

### 检查文件夹是否存在

```bash
huawei_drive.py --command query_folder --file_name 小艺Claw
```

**返回**：文件夹存在性检查结果

---

## 上传命令

### 覆盖上传

```bash
huawei_drive.py --command upload --mode overwrite --path <file_path>
```

**说明**：上传文件到 `/root/小艺Claw` 目录，文件已存在则覆盖

### 重命名上传

```bash
huawei_drive.py --command upload --mode rename --path <file_path>
```

**说明**：上传文件到 `/root/小艺Claw` 目录，文件已存在则自动重命名（添加 `(1)` 后缀）

---

## 文件夹命令

### 创建文件夹

```bash
huawei_drive.py --command create --folder_name 小艺Claw
```

**说明**：在云盘根路径下创建 `小艺Claw` 文件夹

---

## 参数说明

| 参数 | 说明 | 示例 |
|-----|------|------|
| `--command` | 操作类型 | `query`, `upload`, `create`, `query_folder` |
| `--key` | 查询类型 | `space`, `available_space`, `file_list` |
| `--file_name` | 文件名 | `test.txt` |
| `--mode` | 上传模式 | `overwrite`（覆盖）, `rename`（重命名） |
| `--path` | 文件路径 | `/path/to/file.txt` |
| `--folder_name` | 文件夹名称 | `小艺Claw` |

