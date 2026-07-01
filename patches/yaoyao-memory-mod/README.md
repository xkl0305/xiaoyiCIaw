# yaoyao-memory 增强补丁

## 来源
GalaxyOS 模块 → yaoyao-memory pipeline 集成

## 已接入模块

| JS 文件 | GalaxyOS 来源 | 功能 |
|---------|-------------|------|
| hooks/recall-postprocess.js | memory_consolidation.detect_prediction_error | 矛盾检测（否定词冲突+降权） |
| hooks/auto-capture.js | emotion_memory | 情绪分析捕获 |
| hooks/capture-meta.js | hallucination_guard | 防幻觉模式检测 |
| core/search/intent.js | adaptive_rrf | 中文意图分类（8种）+ CJK检测 |
| utils/query-expander.js | rewriter | 拼写纠正 + 标点标准化 |

## 应用方式

```bash
cd /home/sandbox/.openclaw/extensions/yaoyao-memory
git apply /home/sandbox/.openclaw/workspace/patches/yaoyao-galaxyos-integration.patch
```

或者逐个对比替换 `dist/src/` 下的对应文件。
