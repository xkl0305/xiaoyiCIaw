# V111.52.1 Personal OS Enterprise Online Guard

这版是对 V111.52.0 企业级核心治理层的校准补丁：默认不再把系统推回离线模式，而是使用 `always_connected_enterprise`。

## 核心变化

- 修复 `observability_event_bus.py` 里 JSONL 换行写入导致的 `SyntaxError`。
- 默认 profile 改成 `always_connected_enterprise`：`ONLINE_MODE=true`、`ALLOW_NETWORK=true`、`OFFLINE_MODE=false`。
- 在线 provider / connector 可保持常连，不再每次因为“在线”本身拦截。
- 真实副作用仍然走内部 proof：写文件、写记忆、端侧创建、provider 生成、图片生成、外部工具调用。
- 高风险动作仍要显式批准：删除、支付、发消息、删日程、改配置、shell/device 控制。
- 运行态密钥只生成在 `.openclaw/state/personal_os_enterprise/secrets`，不进入覆盖包。

## 覆盖

```bash
python3 scripts/apply_v111_52_1_personal_os_enterprise_online_guard.py
```

## 验收

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -S xiaoyi_persona_visual/diagnostics/verify_v111_52_1_personal_os_enterprise_online_guard.py
```
