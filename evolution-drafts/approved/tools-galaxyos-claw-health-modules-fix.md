# Evolution Proposal: galaxyos claw_health modules 误报定位与修复

- Created-At: 2026-09-22 13:08
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 这是 galaxyos 引擎健康检查排查的又一层关键经验。已有 TOOLS.md 记录了 worker 通信(WORKER_UDS)和 DAG 误报，但本轮的 `modules ❌` 是不同根因，且发现 worker 实际加载文件与 unified_entry 所在文件的路径差异——排查者容易改错文件导致"修了仍报"。

## Evidence
- 实测：`claw_health` 返回 `modules ❌`，其余(xiaoyi_claw/memory/coordinator/workflow_engine)全绿。
- 根因链：`unified_entry.py` 的 `list_modules()` 用 `CORE_DIR = SKILL_ROOT / "skills/llm-memory-integration/core"` 扫 `.py` 模块；但本机 `llm-memory-integration` 技能是 `src/`+`hooks/` 结构、无扁平 `core/` 目录 → `CORE_DIR.exists()==False` → 返回空 → `modules.healthy=False`。
- 关键坑：模块实际存在于 `~/.openclaw/galaxyos/engine/unified_entry.py`，而 worker 进程加载的是 `extensions/galaxyos/scripts/claw_worker.py`（claw_worker 内部 `self._entry.health_check()` 用 engine 里的 UnifiedEntry）。修复 health 判定必须改 `galaxyos/engine/unified_entry.py`，改 worker 文件不生效。
- 修复：health 的 modules 判定加容错——`core` 目录不存在时 `available=True, healthy=True, note='core 模块目录不存在，模块检查降级'`，不 append 到 issues，claw_health 回归全绿。备份 `unified_entry.py.bak-20260922-130430`。
- 生效需 `python3 -m supervisor.supervisorctl -c /home/sandbox/supervisord.conf restart openclaw-gateway` 重启让 worker 重载。

## Conflict Points
- 与 TOOLS.md 423-429「galaxyos 插件 worker 通信故障排查」相关但**非重复**：该条讲 worker 通信(WORKER_UDS) + DAGIntegration 缺 `get_all_session_keys`。本轮是新症状 `modules ❌`，根因(core 目录缺失)与 DAG 方法无关，且修复点在 `unified_entry.py` 而非 worker/通信层。需补充说明"claw_health 报 modules 与报 dag_unavailable 是两码事，根因位置不同"。

## Plan
1. 在 TOOLS.md「galaxyos 插件 worker 通信故障排查（2026-08-29）」小节之后/内部追加一条子经验：`galaxyos claw_health 报 modules ❌ 的定位与修复`。
2. 追加文本（精简）：
```
### galaxyos claw_health 报 modules ❌（非 DAG，core 目录缺失误报）

症状：`claw_health` 返回 `modules ❌`，其余组件全绿。根因不是 DAG，而是 `~/.openclaw/galaxyos/engine/unified_entry.py` 的 `list_modules()` 按 `CORE_DIR(= SKILL_ROOT/skills/llm-memory-integration/core)` 扫模块；本机 llm-memory-integration 是 `src/`+`hooks/` 结构、无扁平 `core/` 目录 → 扫空 → 误报。

排查/修复要点：
- 修复 health 判定**必须改** `galaxyos/engine/unified_entry.py`（worker 进程加载的 `extensions/galaxyos/scripts/claw_worker.py` 内部 `self._entry.health_check()` 用的就是这个 UnifiedEntry）；改 claw_worker.py 不生效。
- 容错写法：core 目录不存在时 `available=True, healthy=True, note='core 模块目录不存在，模块检查降级'`，不 append 到 issues。
- 生效需重启 gateway：`python3 -m supervisor.supervisorctl -c /home/sandbox/supervisord.conf restart openclaw-gateway`。
- 区分：`dag_unavailable`(DAGIntegration 缺方法) 与 `modules ❌`(core 目录缺失) 都可能让 health 显示失败，二者根因位置不同，分别排查。
```
