# V111.52.13 rootless local runtime

本目录只提供本地 / 私网 / rootless 运行模板，不内置模型权重，不联网下载模型。

约束：

- 模型目录只读挂载到 `/srv/models:ro`
- 数据目录单独挂载到 `/srv/data`
- secret 通过环境变量、`/run/secrets` 或 tmpfs 注入
- 默认只绑定 `127.0.0.1`
- 不允许外部 provider fallback
