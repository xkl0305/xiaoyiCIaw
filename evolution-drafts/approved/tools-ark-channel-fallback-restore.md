# 提案：ARK 通道静默退化修复固化（2026-10-27）

- **状态**：approved
- **进化项**：固化 `.xiaoyienv` 丢 SEEDREAM + TOOLS.md 兜底正则标题不匹配导致 ARK 静默退化单通道的根因与两步修复法
- **修改文件**：TOOLS.md（新增「ARK 通道静默退化修复」条目）
- **根因**：① `.xiaoyienv` 丢 SEEDREAM_API_URL/KEY/ENDPOINT_ID；② `_read_xiaoyi_env()` 兜底正则找 `### Seedream ARK 通道配置` 而实际标题是 `### Seedream 通道配置备份` → 匹配失败补不回 key
- **修复**：① 兜底正则改 `### Seedream[^\n]*通道配置`；② 从 TOOLS.md 备份补回 SEEDREAM 三键到 `.xiaoyienv`
- **验证**：双通道恢复(huawei_sse+ark)，ARK 直连出图成功
- **相关备份**：`.bak-envfix`
