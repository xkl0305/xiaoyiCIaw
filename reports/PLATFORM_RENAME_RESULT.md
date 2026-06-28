# platform 顶层目录重命名结果

## 操作
- 将 platform/capability_registry/ 复制到 platform_layer/capability_registry/
- 更新 4 个 shim 文件中的 import: infrastructure/platform_adapter/capability_registry.py, infrastructure/capability_marketplace_v5.py, infrastructure/acquisition/capability_marketplace.py, governance/skill_profile_schema.py
- 删除 platform/ 下的 __init__.py 和 __pycache__ 以避免 Python 标准库 platform 冲突
- 保留 platform/ 下的原始文件但移除了 Python 包入口

## 验收
- `import platform; print(platform.system())` → Linux ✅
- `grep "from platform\.capability_registry"` → 0 命中 ✅
- `python -m compileall` (excl archive) → 0 errors ✅
