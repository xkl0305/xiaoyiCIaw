# V111.52.8 LOCAL CAPABILITY RUNTIME FUSION

这版基于 V111.52.7 干净底座，新增本地能力运行层：

- local_capability_registry：本地 LLM/VLM/OCR/ASR/TTS/Embedding/Reranker/可选本地图像 provider 能力表
- capability_router：用户请求到本地能力的路由，不允许外部 API 回退
- local_model_registry：读取本地模型配置与环境变量
- local_runtime_probe / local_health_check：只探测本地路径、命令、127.0.0.1 端口，不做外网探测
- local_provider_base：本地 provider 接口模板
- local_capability_policy：缺能力 fail-closed，禁止偷切外部 provider

覆盖后执行：

```bash
python3 scripts/apply_v111_52_8_local_capability_runtime_fusion.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_8_local_capability_runtime_fusion.py
```

本版不动 V111.51 人格视觉主链，不动 V111.52 side_effect_proof/action_guard/send_guard，只把本地能力运行时融合进主架构。


## 本版还补齐的企业化骨架

- offline_model_cache：模型预拉取清单与离线缓存检查
- local_providers：LLM/VLM/OCR/ASR/TTS/Embedding/Image provider 本地适配器入口，缺配置时 fail-closed
- embodied_screen_agent：截图 → OCR/VLM → 状态提取 → 动作 dry-run → action_guard → 执行后验证的规划骨架
- data_governance：S0/S1/S2/S3 数据分级、TTL 与脱敏策略入口
- observability_dashboard + metrics_catalog：本地 SQLite WAL 事件账本的汇总视图与指标目录
- deployment/rootless：rootless、本地只读模型目录、无网络模板

注意：本包不内置大模型权重，也不会自动联网下载模型。模型接入需要你在本机按 profiles/local_capabilities.toml 配置本地路径或 127.0.0.1 本地服务。
