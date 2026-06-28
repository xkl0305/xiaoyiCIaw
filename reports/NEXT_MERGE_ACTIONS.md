# 下一轮融合操作建议

## 高优先级
1. **修复 archive/ wrapper 兼容性** (8 files with digit-leading module names)
   - 改为相对 import 或重命名模块名
2. **清理旧 platform/ 目录** - 确认无引用后删除剩余 .py 文件
3. **补全 SHIM_VALIDATION_RESULT.md 中失败路径** (若有)

## 中优先级
4. **将 legacy_readonly/ 内容整理到 archive/legacy_readonly/**
5. **UNFUSED_MODULES_REPORT.csv 中未融合模块** 评估是否纳入融合计划
6. **统一所有 shim 的 DeprecationWarning 格式**

## 低优先级
7. **FUSION_COVERAGE_MATRIX.json 数据精确化** - 目前基于文件路径估算
8. **移除所有 __pycache__ 目录** 
