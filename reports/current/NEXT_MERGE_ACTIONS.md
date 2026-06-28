# NEXT_MERGE_ACTIONS

1. 搜索 `MIGRATION_PLACEHOLDER = True`，决定补实现或废弃。
2. 运行项目测试集确认旧 import 与新 import 的行为一致。
3. 观察 `legacy_readonly/` 14-21 天后再清理。
