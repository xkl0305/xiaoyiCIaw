# 进化提案：沙箱清理脚本纳入正式文件备份治理

- **状态**：✅ approved（2026-09-23 用户确认）
- **进化项**：将 workspace 正式文件旧备份自动治理纳入 `cron_sandbox_cleanup.py`
- **修改文件**：`scripts/cron_sandbox_cleanup.py`

## 经验规则

1. **新增 `clean_workspace_backups()`**：扫描 `AGENTS/SOUL/MEMORY/USER/IDENTITY/TOOLS.md.bak-*`，按 mtime 排序每组保留最新 `BACKUP_KEEP=2` 个，其余删除。
2. **dry-run 支持**：`--dry-run` 时只预览备份待删清单，**不执行任何实际删除**（`auto_clean` 在 dry_run 时仅调用备份预览）。
3. **安全机制**：只匹配 6 个正式文件的 `.bak-*`，每组至少保留 2 个，不回滚能力真空。
4. **验证（2026-09-23 实测）**：语法 OK；dry-run 纯净；选择逻辑正确（造 3 个测试备份→只标最旧 1 个待删）；实跑无副作用，正式备份完好。

## 落盘位置

- `scripts/cron_sandbox_cleanup.py`（含 dry-run 分支、备份治理函数、接入 auto_clean）
- 备份：`scripts/cron_sandbox_cleanup.py.bak-20260923-103623`

## 关联

配套 cron「沙箱清理-每周检查」（每周日 12:00 自动执行本脚本，治理自动生效）。
